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
async def test_rapid_copy_client_falls_back_when_error_field_is_empty_string() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(409, json={"error": ""})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "target_conflict"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_falls_back_when_error_field_is_null() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(409, json={"error": None})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "target_conflict"


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


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_returns_upstream_error_when_target_path_missing() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(200, json={})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "upstream_error"
    assert result.detail == "missing target_path in rapid-copy response"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_returns_upstream_error_when_target_path_is_null() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(200, json={"target_path": None})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "upstream_error"
    assert result.detail == "invalid target_path in rapid-copy response"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_returns_upstream_error_when_target_path_is_empty() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(200, json={"target_path": ""})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "upstream_error"
    assert result.detail == "invalid target_path in rapid-copy response"


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_handles_non_dict_json_error_payload() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(409, json=["bad-payload"])
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "target_conflict"
    assert result.detail is None


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_connect_error_to_service_unreachable() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        side_effect=httpx.ConnectError("rapid-copy offline")
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "service_unreachable"
    assert "rapid-copy offline" in result.detail


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_422_to_invalid_request() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(422, json={"detail": "bad source path"})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "invalid_request"
    assert result.detail == "bad source path"
