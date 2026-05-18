from dataclasses import dataclass

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


class OpenListClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token} if token else {},
            timeout=5.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _coerce_int(self, value: object) -> int | None:
        if value is None:
            return None
        return int(value)

    def _coerce_ranges(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() == "bytes"

    def _normalize_catalog_path(self, root_path: str, row: dict[str, object]) -> str:
        raw_path = row.get("path")
        if raw_path:
            return str(raw_path)
        raw_name = str(row.get("name") or "").strip("/")
        if not raw_name:
            raise ValueError("openlist catalog row missing path")
        return f"{root_path.rstrip('/')}/{raw_name}"

    def _normalize_mtime(self, row: dict[str, object]) -> str | None:
        for key in ("modified", "modified_at", "updated_at"):
            value = row.get(key)
            if value:
                return str(value)
        return None

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        response = await self._client.post("/api/fs/link", json={"path": source_path})
        response.raise_for_status()
        data = response.json().get("data") or {}
        raw_url = data.get("raw_url") or data.get("url")
        if not raw_url:
            raise ValueError("openlist stream response missing url")
        return StreamInfo(
            raw_url=str(raw_url),
            content_length=self._coerce_int(data.get("content_length")),
            accepts_ranges=self._coerce_ranges(data.get("accept_ranges")),
        )

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        response = await self._client.post("/api/fs/list", json={"path": root_path})
        response.raise_for_status()
        rows = response.json()["data"]["content"]
        return [
            CatalogRow(
                path=self._normalize_catalog_path(root_path, row),
                size=int(row.get("size") or 0),
                file_id=str(row["id"]) if row.get("id") is not None else None,
                mtime=self._normalize_mtime(row),
            )
            for row in rows
            if not row.get("is_dir", False)
        ]
