import json
from dataclasses import dataclass
from pathlib import PurePosixPath

import httpx


@dataclass(slots=True)
class CatalogRow:
    path: str
    size: int
    file_id: str | None
    mtime: str | None


@dataclass(slots=True)
class StreamInfo:
    raw_url: str
    content_length: int | None
    accepts_ranges: bool
    request_headers: dict[str, str] | None = None


@dataclass(slots=True)
class OpenListObjectInfo:
    path: str
    name: str
    size: int
    raw_url: str
    provider: str | None
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None


class OpenListClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token} if token else {},
            timeout=5.0,
        )

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        response = await self._client.post("/api/fs/link", json={"path": source_path})
        response.raise_for_status()
        data = response.json()["data"]
        return StreamInfo(
            raw_url=data.get("raw_url") or data["url"],
            content_length=self._to_int(data.get("content_length")),
            accepts_ranges=self._accepts_ranges(data.get("accept_ranges")),
        )

    async def get_object_info(self, source_path: str) -> OpenListObjectInfo:
        response = await self._client.post(
            "/api/fs/get",
            json={"path": source_path, "password": ""},
        )
        response.raise_for_status()
        data = response.json()["data"]
        hash_info = self._extract_hash_info(data)
        return OpenListObjectInfo(
            path=source_path,
            name=str(data.get("name") or PurePosixPath(source_path).name),
            size=self._to_int(data.get("size")) or 0,
            raw_url=data.get("raw_url") or data["url"],
            provider=self._to_optional_str(data.get("provider")),
            md5=hash_info.get("md5"),
            sha1=hash_info.get("sha1"),
            sha256=hash_info.get("sha256"),
        )

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        response = await self._client.post("/api/fs/list", json={"path": root_path})
        response.raise_for_status()
        rows = response.json()["data"]["content"]
        return [
            CatalogRow(
                path=self._build_catalog_path(root_path, row),
                size=self._to_int(row.get("size")) or 0,
                file_id=str(row["id"]) if row.get("id") is not None else None,
                mtime=row.get("modified") or row.get("modified_at"),
            )
            for row in rows
            if not row.get("is_dir", False)
        ]

    async def aclose(self) -> None:
        await self._client.aclose()

    def _accepts_ranges(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"bytes", "true", "1", "yes"}
        return False

    def _build_catalog_path(self, root_path: str, row: dict[str, object]) -> str:
        path = row.get("path")
        if isinstance(path, str) and path:
            return path
        name = row.get("name")
        if isinstance(name, str) and name:
            return str(PurePosixPath(root_path) / name)
        raise KeyError("catalog row missing path and name")

    def _to_int(self, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def _extract_hash_info(self, data: dict[str, object]) -> dict[str, str]:
        value = data.get("hash_info")
        if isinstance(value, dict):
            return {
                key: hash_value
                for key in ("md5", "sha1", "sha256")
                if isinstance((hash_value := value.get(key)), str) and hash_value
            }

        serialized = data.get("hashinfo")
        if isinstance(serialized, str) and serialized:
            try:
                decoded = json.loads(serialized)
            except json.JSONDecodeError:
                return {}
            if isinstance(decoded, dict):
                return {
                    key: hash_value
                    for key in ("md5", "sha1", "sha256")
                    if isinstance((hash_value := decoded.get(key)), str) and hash_value
                }
        return {}

    def _to_optional_str(self, value: object) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None
