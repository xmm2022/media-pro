import pytest

from gateway.integrations.drive115_stream_client import Drive115StreamClient
from gateway.integrations.openlist_client import StreamInfo


class StubP115Url(str):
    def __new__(cls, value: str, *, headers: dict[str, str] | None = None):
        instance = str.__new__(cls, value)
        instance.headers = headers or {}
        return instance


class StubP115Client:
    def __init__(self) -> None:
        self.dir_calls: list[dict[str, object]] = []
        self.search_calls: list[dict[str, object]] = []
        self.download_calls: list[tuple[str, str]] = []

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.dir_calls.append(payload)
        return {"id": "dir-123"}

    def fs_search(self, payload: dict[str, object]) -> dict[str, object]:
        self.search_calls.append(payload)
        return {
            "data": [
                {"n": "Movie.2024.mkv", "pc": "child-pickcode", "cid": "other-dir", "s": 1024},
                {"n": "Movie.2024.mkv", "pc": "pickcode-123", "cid": "dir-123", "s": 2048},
            ]
        }

    def download_url(self, pickcode: str, *, app: str) -> StubP115Url:
        self.download_calls.append((pickcode, app))
        return StubP115Url(
            "https://115.local/direct/movie.mkv",
            headers={"user-agent": ""},
        )


@pytest.mark.asyncio
async def test_drive115_stream_client_resolves_direct_file_stream_from_115_path() -> None:
    p115_client = StubP115Client()
    client = Drive115StreamClient(client_factory=lambda _cookie: p115_client)

    info = await client.get_stream_info("UID=alice", "/EmbyCache/alice/Movies/Movie.2024.mkv")

    assert info == StreamInfo(
        raw_url="https://115.local/direct/movie.mkv",
        content_length=2048,
        accepts_ranges=True,
        request_headers={"user-agent": ""},
    )
    assert p115_client.dir_calls == [{"path": "/EmbyCache/alice/Movies"}]
    assert p115_client.search_calls == [
        {
            "cid": "dir-123",
            "search_value": "Movie.2024.mkv",
            "limit": 32,
            "offset": 0,
            "fc": 2,
            "show_dir": 0,
        }
    ]
    assert p115_client.download_calls == [("pickcode-123", "chrome")]


@pytest.mark.asyncio
async def test_drive115_stream_client_raises_when_target_file_is_missing() -> None:
    class MissingFileClient(StubP115Client):
        def fs_search(self, payload: dict[str, object]) -> dict[str, object]:
            self.search_calls.append(payload)
            return {"data": []}

    client = Drive115StreamClient(client_factory=lambda _cookie: MissingFileClient())

    with pytest.raises(FileNotFoundError):
        await client.get_stream_info("UID=alice", "/EmbyCache/alice/Movies/Movie.2024.mkv")
