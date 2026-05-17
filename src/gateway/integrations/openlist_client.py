from dataclasses import dataclass

import httpx


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

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        response = await self._client.post("/api/fs/link", json={"path": source_path})
        response.raise_for_status()
        data = response.json()["data"]
        return StreamInfo(
            raw_url=data["url"],
            content_length=data.get("content_length"),
            accepts_ranges=data.get("accept_ranges") == "bytes",
        )
