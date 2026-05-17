import httpx
import pytest
import respx

from gateway.integrations.rapid_copy_client import RapidCopyClient


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_unsupported_error() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(409, json={"error": "rapid_copy_unsupported"})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "rapid_copy_unsupported"
