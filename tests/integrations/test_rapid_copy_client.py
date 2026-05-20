import json

import httpx
import pytest
import respx

from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyClient,
    SourceObjectRef,
    SourceCopyRequest,
)


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_unsupported_error() -> None:
    route = respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(409, json={"error": "rapid_copy_unsupported"})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy_from_pool(
        PoolCopyRequest(
            donor_cookie="cookie-a",
            target_cookie="cookie-b",
            source_path="/Movies/movie.mkv",
            target_path="/EmbyCache/movie.mkv",
        )
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
    result = await client.copy_from_pool(
        PoolCopyRequest(
            donor_cookie="cookie-a",
            target_cookie="cookie-b",
            source_path="/Movies/movie.mkv",
            target_path="/EmbyCache/movie.mkv",
        )
    )

    assert result.ok is True
    assert result.error_code is None
    assert result.target_path == "/EmbyCache/movie.mkv"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_connect_error_to_unreachable() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        side_effect=httpx.ConnectError("rapid-copy offline")
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy_from_pool(
        PoolCopyRequest(
            donor_cookie="cookie-a",
            target_cookie="cookie-b",
            source_path="/Movies/movie.mkv",
            target_path="/EmbyCache/movie.mkv",
        )
    )

    assert result.ok is False
    assert result.error_code == "unreachable"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_source_copy_payload_without_donor_cookie() -> None:
    route = respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(
            200,
            json={"target_path": "/EmbyCache/movie.mkv"},
        )
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy_from_source(
        SourceCopyRequest(
            target_cookie="cookie-b",
            source=SourceObjectRef(
                openlist_path="/Movies/movie.mkv",
                source_path="/library/Movie/movie.mkv",
                source_file_id="gd-1",
                fingerprint="2048:movie:mkv",
            ),
            target_path="/EmbyCache/movie.mkv",
        )
    )

    assert result.ok is True
    request = route.calls.last.request
    assert json.loads(request.read()) == {
        "target_cookie": "cookie-b",
        "source_path": "/Movies/movie.mkv",
        "target_path": "/EmbyCache/movie.mkv",
    }
