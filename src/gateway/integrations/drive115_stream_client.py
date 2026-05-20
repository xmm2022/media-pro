from __future__ import annotations

import asyncio
from pathlib import PurePosixPath
from typing import Callable, Protocol

from gateway.integrations.openlist_client import StreamInfo


class OneOneFiveDownloadUrl(Protocol):
    headers: dict[str, str]

    def __str__(self) -> str: ...


class OneOneFiveClient(Protocol):
    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def fs_search(self, payload: dict[str, object]) -> dict[str, object]: ...

    def download_url(self, pickcode: str, *, app: str) -> OneOneFiveDownloadUrl: ...


class Drive115StreamClient:
    def __init__(
        self,
        *,
        client_factory: Callable[[str], OneOneFiveClient] | None = None,
    ) -> None:
        self._client_factory = client_factory or self._build_client

    async def get_stream_info(self, target_cookie: str, target_path: str) -> StreamInfo:
        return await asyncio.to_thread(self._resolve_stream_info, target_cookie, target_path)

    def _resolve_stream_info(self, target_cookie: str, target_path: str) -> StreamInfo:
        client = self._client_factory(target_cookie)
        target = PurePosixPath(target_path)
        parent_path = str(target.parent) if str(target.parent) else "/"
        file_name = target.name
        if not file_name:
            raise FileNotFoundError(f"115 target file name missing for path: {target_path}")

        parent_id = self._resolve_parent_id(client, parent_path)
        entry = self._find_file_entry(client, parent_id, file_name)
        pickcode = self._extract_pickcode(entry)
        if not pickcode:
            raise FileNotFoundError(f"115 pickcode missing for path: {target_path}")

        download_url = client.download_url(pickcode, app="chrome")
        return StreamInfo(
            raw_url=str(download_url),
            content_length=self._extract_size(entry),
            accepts_ranges=True,
            request_headers=dict(getattr(download_url, "headers", {})),
        )

    def _resolve_parent_id(self, client: OneOneFiveClient, parent_path: str) -> str:
        if parent_path in {"", ".", "/"}:
            return "0"
        response = client.fs_dir_getid_app({"path": parent_path})
        parent_id = self._extract_id(response)
        if not parent_id:
            raise FileNotFoundError(f"115 parent directory not found: {parent_path}")
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
            raise FileNotFoundError(f"115 search returned no file entries for {file_name}")

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if self._extract_name(entry) != file_name:
                continue
            if self._extract_parent_id(entry) != parent_id:
                continue
            return entry
        raise FileNotFoundError(f"115 file not found at target path: {file_name}")

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

    def _extract_size(self, entry: dict[str, object]) -> int | None:
        for key in ("s", "file_size", "size"):
            value = entry.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    def _build_client(self, target_cookie: str) -> OneOneFiveClient:
        from p115client import P115Client

        return P115Client(target_cookie, check_for_relogin=False)
