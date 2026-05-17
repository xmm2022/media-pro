import json

import httpx
import pytest
import respx

from gateway.integrations.rapid_copy_client import RapidCopyClient


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_unsupported_error() -> None:
    route = respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(409, json={"error": "rapid_copy_unsupported"})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert route.called is True
    request = route.calls.last.request
    assert json.loads(request.read()) == {
        "donor_cookie": "cookie-a",
        "target_cookie": "cookie-b",
        "source_path": "/Movies/movie.mkv",
        "target_path": "/EmbyCache/movie.mkv",
    }
    assert result.ok is False
    assert result.error_code == "rapid_copy_unsupported"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_success_response() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(
            200,
            json={"target_path": "/EmbyCache/movie.mkv"},
        )
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is True
    assert result.error_code is None
    assert result.target_path == "/EmbyCache/movie.mkv"
