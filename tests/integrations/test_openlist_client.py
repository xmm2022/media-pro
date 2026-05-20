import json

import httpx
import pytest
import respx

from gateway.integrations.openlist_client import CatalogRow, OpenListClient, OpenListObjectInfo


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_returns_stream_info() -> None:
    route = respx.post("http://openlist.local/api/fs/link").mock(
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

    assert route.called is True
    request = route.calls.last.request
    assert request.headers["Authorization"] == "token"
    assert json.loads(request.read()) == {"path": "/Movies/movie.mkv"}
    assert info.raw_url == "https://drive.local/movie.mkv"
    assert info.content_length == 1024
    assert info.accepts_ranges is True


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_lists_catalog_rows() -> None:
    route = respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "path": "/Movies",
                            "size": 0,
                            "id": "dir-1",
                            "modified": "2026-05-17T00:00:00Z",
                            "is_dir": True,
                        },
                        {
                            "path": "/Movies/Movie.2024.mkv",
                            "size": 2048,
                            "id": "gd-1",
                            "modified": "2026-05-17T00:00:00Z",
                            "is_dir": False,
                        },
                        {
                            "path": "/Movies/Clip.mp4",
                            "size": 512,
                            "modified": None,
                        },
                    ]
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    rows = await client.list_catalog("/Movies")

    assert route.called is True
    request = route.calls.last.request
    assert request.headers["Authorization"] == "token"
    assert json.loads(request.read()) == {"path": "/Movies"}
    assert len(rows) == 2
    assert rows[0].path == "/Movies/Movie.2024.mkv"
    assert rows[0].size == 2048
    assert rows[0].file_id == "gd-1"
    assert rows[0].mtime == "2026-05-17T00:00:00Z"
    assert rows[1].path == "/Movies/Clip.mp4"
    assert rows[1].size == 512
    assert rows[1].file_id is None
    assert rows[1].mtime is None


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_accepts_raw_url_and_boolean_range_flag() -> None:
    respx.post("http://openlist.local/api/fs/link").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "raw_url": "https://drive.local/raw.mkv",
                    "content_length": "2048",
                    "accept_ranges": True,
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    info = await client.get_stream_info("/Movies/raw.mkv")

    assert info.raw_url == "https://drive.local/raw.mkv"
    assert info.content_length == 2048
    assert info.accepts_ranges is True


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_builds_catalog_path_from_name_when_path_missing() -> None:
    route = respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "name": "Movie.2024.mkv",
                            "size": 2048,
                            "id": 12,
                            "modified_at": "2026-05-17T00:00:00Z",
                        }
                    ]
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    rows = await client.list_catalog("/Movies")

    assert route.called is True
    assert rows == [
        CatalogRow(
            path="/Movies/Movie.2024.mkv",
            size=2048,
            file_id="12",
            mtime="2026-05-17T00:00:00Z",
        )
    ]


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_returns_object_info_with_hashes() -> None:
    route = respx.post("http://openlist.local/api/fs/get").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "name": "Movie.2024.mkv",
                    "size": 2048,
                    "raw_url": "https://openlist.local/raw/movie.mkv",
                    "provider": "GoogleDrive",
                    "hash_info": {
                        "md5": "md5-value",
                        "sha1": "sha1-value",
                        "sha256": "sha256-value",
                    },
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    info = await client.get_object_info("/Movies/Movie.2024.mkv")

    assert route.called is True
    request = route.calls.last.request
    assert request.headers["Authorization"] == "token"
    assert json.loads(request.read()) == {"path": "/Movies/Movie.2024.mkv", "password": ""}
    assert info == OpenListObjectInfo(
        path="/Movies/Movie.2024.mkv",
        name="Movie.2024.mkv",
        size=2048,
        raw_url="https://openlist.local/raw/movie.mkv",
        provider="GoogleDrive",
        md5="md5-value",
        sha1="sha1-value",
        sha256="sha256-value",
    )
