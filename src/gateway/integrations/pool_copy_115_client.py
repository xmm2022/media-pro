from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Callable, Protocol

import httpx

from gateway.integrations.rapid_copy_client import PoolCopyRequest, RapidCopyResult


class OneOneFiveDownloadUrl(Protocol):
    headers: dict[str, str]

    def __str__(self) -> str: ...


class OneOneFiveClient(Protocol):
    user_key: str

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def fs_search(self, payload: dict[str, object]) -> dict[str, object]: ...

    def fs_supervision(self, pickcode: str) -> dict[str, object]: ...

    def download_url(self, pickcode: str, *, app: str) -> OneOneFiveDownloadUrl: ...

    def upload_info(self) -> dict[str, object]: ...

    def fs_makedirs_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def upload_file_init(
        self,
        filename: str,
        filesize: int,
        filesha1: str,
        read_range_bytes_or_hash,
        pid: str,
    ) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class DonorFileInfo:
    name: str
    size: int
    sha1: str
    raw_url: str
    request_headers: dict[str, str]


class PoolCopy115Client:
    def __init__(
        self,
        *,
        client_factory: Callable[[str], OneOneFiveClient] | None = None,
        range_client: httpx.Client | None = None,
    ) -> None:
        self._client_factory = client_factory or self._build_client
        self._range_client = range_client or httpx.Client(follow_redirects=True, timeout=20.0)

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        target = PurePosixPath(request.target_path)
        target_dir = str(target.parent) if str(target.parent) else "/"

        try:
            response = await asyncio.to_thread(
                self._copy_to_115,
                request.donor_cookie,
                request.target_cookie,
                request.source_path,
                target_dir,
            )
        except FileNotFoundError as exc:
            return RapidCopyResult(ok=False, error_code="missing_donor_file", detail=str(exc))
        except ValueError as exc:
            return RapidCopyResult(ok=False, error_code="invalid_target_path", detail=str(exc))
        except httpx.HTTPError as exc:
            return RapidCopyResult(ok=False, error_code="donor_range_unavailable", detail=str(exc))
        except Exception as exc:  # pragma: no cover - defensive mapping
            return RapidCopyResult(ok=False, error_code="quick_upload_failed", detail=str(exc))

        if not bool(response.get("state", False)):
            return RapidCopyResult(
                ok=False,
                error_code=self._extract_error_code(response),
                detail=self._extract_detail(response),
            )
        if not bool(response.get("reuse", False)):
            return RapidCopyResult(ok=False, error_code="quick_upload_unavailable")
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None:
        await asyncio.to_thread(self._range_client.close)

    def _copy_to_115(
        self,
        donor_cookie: str,
        target_cookie: str,
        source_path: str,
        target_dir: str,
    ) -> dict[str, object]:
        donor_client = self._client_factory(donor_cookie)
        target_client = self._client_factory(target_cookie)
        donor_file = self._resolve_donor_file(donor_client, source_path)
        self._prime_user_key(target_client)
        target_dir_id = self._resolve_target_dir_id(target_client, target_dir)
        return target_client.upload_file_init(
            donor_file.name,
            donor_file.size,
            donor_file.sha1,
            read_range_bytes_or_hash=lambda sign_check: self._read_range(
                donor_file.raw_url,
                donor_file.request_headers,
                sign_check,
            ),
            pid=target_dir_id,
        )

    def _resolve_donor_file(self, client: OneOneFiveClient, source_path: str) -> DonorFileInfo:
        source = PurePosixPath(source_path)
        parent_path = str(source.parent) if str(source.parent) else "/"
        file_name = source.name
        if not file_name:
            raise FileNotFoundError(f"115 donor file name missing for path: {source_path}")

        parent_id = self._resolve_parent_id(client, parent_path)
        entry = self._find_file_entry(client, parent_id, file_name)
        pickcode = self._extract_pickcode(entry)
        if not pickcode:
            raise FileNotFoundError(f"115 donor pickcode missing for path: {source_path}")

        supervision = client.fs_supervision(pickcode)
        data = supervision.get("data")
        if not isinstance(data, dict):
            raise FileNotFoundError(f"115 donor metadata missing for path: {source_path}")
        sha1 = data.get("file_sha1")
        if not isinstance(sha1, str) or not sha1:
            raise FileNotFoundError(f"115 donor sha1 missing for path: {source_path}")

        download_url = client.download_url(pickcode, app="chrome")
        return DonorFileInfo(
            name=self._extract_name(entry) or file_name,
            size=self._extract_size(data) or self._extract_size(entry) or 0,
            sha1=sha1,
            raw_url=str(download_url),
            request_headers=dict(getattr(download_url, "headers", {})),
        )

    def _resolve_parent_id(self, client: OneOneFiveClient, parent_path: str) -> str:
        if parent_path in {"", ".", "/"}:
            return "0"
        response = client.fs_dir_getid_app({"path": parent_path})
        parent_id = self._extract_id(response)
        if not parent_id:
            raise FileNotFoundError(f"115 donor parent directory not found: {parent_path}")
        return parent_id

    def _find_file_entry(self, client: OneOneFiveClient, parent_id: str, file_name: str) -> dict[str, object]:
        response = client.fs_search(
            {
                "cid": parent_id,
                "search_value": file_name,
                "limit": 32,
                "offset": 0,
                "fc": 2,
                "show_dir": 0,
            }
        )
        entries = response.get("data")
        if not isinstance(entries, list):
            raise FileNotFoundError(f"115 donor search returned no file entries for {file_name}")

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if self._extract_name(entry) != file_name:
                continue
            if self._extract_parent_id(entry) != parent_id:
                continue
            return entry
        raise FileNotFoundError(f"115 donor file not found: {file_name}")

    def _resolve_target_dir_id(self, client: OneOneFiveClient, target_dir: str) -> str:
        if target_dir in {"", ".", "/"}:
            return "0"

        mkdir_response = client.fs_makedirs_app({"path": target_dir})
        target_dir_id = self._extract_id(mkdir_response)
        if target_dir_id:
            return target_dir_id

        target_dir_id = self._extract_id(client.fs_dir_getid_app({"path": target_dir}))
        if target_dir_id:
            return target_dir_id

        raise ValueError(f"115 target directory id not found for path: {target_dir}")

    def _prime_user_key(self, client: OneOneFiveClient) -> None:
        upload_info = client.upload_info()
        user_key = self._extract_user_key(upload_info)
        if not user_key:
            raise ValueError("115 upload_info missing userkey")
        setattr(client, "user_key", user_key)

    def _read_range(self, raw_url: str, base_headers: dict[str, str], sign_check: str) -> bytes:
        range_header = sign_check if sign_check.startswith("bytes=") else f"bytes={sign_check}"
        headers = dict(base_headers)
        headers["Range"] = range_header
        with self._range_client.stream("GET", raw_url, headers=headers) as response:
            response.raise_for_status()
            if response.status_code != 206:
                raise httpx.HTTPStatusError(
                    f"donor range request returned {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response.read()

    def _extract_id(self, response: dict[str, object]) -> str | None:
        for key in ("id", "cid", "file_id"):
            value = response.get(key)
            if value is not None:
                return str(value)
        data = response.get("data")
        if isinstance(data, dict):
            for key in ("id", "cid", "file_id"):
                value = data.get(key)
                if value is not None:
                    return str(value)
        return None

    def _extract_name(self, entry: dict[str, object]) -> str | None:
        for key in ("n", "file_name", "name"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _extract_parent_id(self, entry: dict[str, object]) -> str | None:
        for key in ("cid", "pid", "parent_id"):
            value = entry.get(key)
            if value is not None:
                return str(value)
        return None

    def _extract_pickcode(self, entry: dict[str, object]) -> str | None:
        for key in ("pc", "pick_code", "pickcode"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _extract_size(self, data: dict[str, object]) -> int | None:
        for key in ("s", "file_size", "size"):
            value = data.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    def _extract_user_key(self, response: dict[str, object]) -> str | None:
        value = response.get("userkey")
        if isinstance(value, str) and value:
            return value
        data = response.get("data")
        if isinstance(data, dict):
            value = data.get("userkey")
            if isinstance(value, str) and value:
                return value
        return None

    def _extract_error_code(self, response: dict[str, object]) -> str:
        status_code = response.get("statuscode")
        if status_code is not None:
            if str(status_code) == "10005":
                return "file_too_large_for_account"
            if str(status_code) == "702":
                return "source_range_signature_invalid"
        for key in ("error", "errno", "status"):
            value = response.get(key)
            if value is None:
                continue
            if isinstance(value, str) and value:
                return value
            return str(value)
        return "quick_upload_failed"

    def _extract_detail(self, response: dict[str, object]) -> str | None:
        for key in ("statusmsg", "message", "msg", "error"):
            value = response.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    def _build_client(self, target_cookie: str) -> OneOneFiveClient:
        from p115client import P115Client

        return P115Client(target_cookie, check_for_relogin=False)
