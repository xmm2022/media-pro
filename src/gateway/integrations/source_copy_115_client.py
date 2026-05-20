from __future__ import annotations

import asyncio
from pathlib import PurePosixPath
from typing import Any, Callable, Protocol

import httpx

from gateway.integrations.openlist_client import OpenListClient, OpenListObjectInfo
from gateway.integrations.rapid_copy_client import RapidCopyResult, SourceCopyRequest


class OneOneFiveClient(Protocol):
    user_key: str

    def fs_makedirs_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def upload_info(self) -> dict[str, object]: ...

    def upload_file_init(
        self,
        filename: str,
        filesize: int,
        filesha1: str,
        read_range_bytes_or_hash,
        pid: str,
    ) -> dict[str, object]: ...


class SourceCopy115Client:
    def __init__(
        self,
        openlist_client: OpenListClient,
        *,
        client_factory: Callable[[str], OneOneFiveClient] | None = None,
        range_client: httpx.Client | None = None,
    ) -> None:
        self._openlist_client = openlist_client
        self._client_factory = client_factory or self._build_client
        self._range_client = range_client or httpx.Client(follow_redirects=True, timeout=20.0)

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        source_path = request.source.openlist_path or request.source.preferred_path()
        source_info = await self._openlist_client.get_object_info(source_path)
        if not source_info.sha1:
            return RapidCopyResult(ok=False, error_code="missing_source_hash")
        if not source_info.raw_url:
            return RapidCopyResult(ok=False, error_code="missing_source_url")

        target = PurePosixPath(request.target_path)
        target_dir = str(target.parent) if str(target.parent) else "/"
        filename = target.name or source_info.name

        try:
            response = await asyncio.to_thread(
                self._upload_to_115,
                request.target_cookie,
                source_info,
                target_dir,
                filename,
            )
        except ValueError as exc:
            return RapidCopyResult(ok=False, error_code="invalid_target_path", detail=str(exc))
        except httpx.HTTPError as exc:
            return RapidCopyResult(ok=False, error_code="source_range_unavailable", detail=str(exc))
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

    def _upload_to_115(
        self,
        target_cookie: str,
        source_info: OpenListObjectInfo,
        target_dir: str,
        filename: str,
    ) -> dict[str, object]:
        client = self._client_factory(target_cookie)
        self._prime_user_key(client)
        target_dir_id = self._resolve_target_dir_id(client, target_dir)
        return client.upload_file_init(
            filename,
            source_info.size,
            source_info.sha1 or "",
            read_range_bytes_or_hash=lambda sign_check: self._read_range(source_info.raw_url, sign_check),
            pid=target_dir_id,
        )

    def _resolve_target_dir_id(self, client: OneOneFiveClient, target_dir: str) -> str:
        if target_dir in {"", ".", "/"}:
            return "0"

        mkdir_response = client.fs_makedirs_app({"path": target_dir})
        target_dir_id = self._extract_dir_id(mkdir_response)
        if target_dir_id:
            return target_dir_id

        target_dir_id = self._extract_dir_id(client.fs_dir_getid_app({"path": target_dir}))
        if target_dir_id:
            return target_dir_id

        raise ValueError(f"115 target directory id not found for path: {target_dir}")

    def _prime_user_key(self, client: OneOneFiveClient) -> None:
        upload_info = client.upload_info()
        user_key = self._extract_user_key(upload_info)
        if not user_key:
            raise ValueError("115 upload_info missing userkey")
        setattr(client, "user_key", user_key)

    def _read_range(self, raw_url: str, sign_check: str) -> bytes:
        range_header = sign_check if sign_check.startswith("bytes=") else f"bytes={sign_check}"
        with self._range_client.stream(
            "GET",
            raw_url,
            headers={"Range": range_header},
        ) as response:
            response.raise_for_status()
            if response.status_code != 206:
                raise httpx.HTTPStatusError(
                    f"source range request returned {response.status_code}",
                    request=response.request,
                    response=response,
                )
            return response.read()

    def _extract_dir_id(self, response: dict[str, object]) -> str | None:
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
