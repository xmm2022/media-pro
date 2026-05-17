import httpx
import pytest
import respx

from gateway.integrations.openlist_client import OpenListClient


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_returns_stream_info() -> None:
    respx.post("http://openlist.local/api/fs/link").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "url": "https://drive.local/movie.mkv",
                    "content_length": 1024,
                    "accept_ranges": "bytes",
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    info = await client.get_stream_info("/Movies/movie.mkv")

    assert info.raw_url == "https://drive.local/movie.mkv"
    assert info.content_length == 1024
    assert info.accepts_ranges is True
