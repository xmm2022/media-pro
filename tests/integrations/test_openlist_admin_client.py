import json

import httpx
import pytest
import respx

from gateway.integrations.openlist_admin_client import (
    CopyResult,
    FsItem,
    OpenListAdminClient,
    OpenListAdminError,
    StorageRecord,
)


@pytest.mark.asyncio
@respx.mock
async def test_list_storages_returns_parsed_records() -> None:
    route = respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "message": "success",
                "data": {
                    "content": [
                        {
                            "id": 1,
                            "mount_path": "/caiyun-a",
                            "driver": "139Yun",
                            "addition": json.dumps({"authorization": "tok"}),
                        },
                        {
                            "id": 2,
                            "mount_path": "/gd",
                            "driver": "GoogleDrive",
                            "addition": "{}",
                        },
                    ]
                },
            },
        )
    )

    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        records = await client.list_storages()
    finally:
        await client.aclose()

    assert route.called is True
    assert route.calls.last.request.headers["Authorization"] == "admin-token"
    assert records == [
        StorageRecord(
            id=1,
            mount_path="/caiyun-a",
            driver="139Yun",
            addition={"authorization": "tok"},
        ),
        StorageRecord(id=2, mount_path="/gd", driver="GoogleDrive", addition={}),
    ]


@pytest.mark.asyncio
@respx.mock
async def test_create_storage_returns_storage_id() -> None:
    route = respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {"id": 7}})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        storage_id = await client.create_storage(
            driver="139Yun",
            mount_path="/caiyun-alice",
            addition={"authorization": "tok-a", "type": "personal_new"},
        )
    finally:
        await client.aclose()

    assert storage_id == 7
    assert json.loads(route.calls.last.request.content) == {
        "mount_path": "/caiyun-alice",
        "driver": "139Yun",
        "addition": json.dumps({"authorization": "tok-a", "type": "personal_new"}),
    }


@pytest.mark.asyncio
@respx.mock
async def test_create_storage_raises_on_openlist_business_error() -> None:
    respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(
            200,
            json={"code": 400, "message": "duplicate mount_path", "data": None},
        )
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        with pytest.raises(OpenListAdminError) as exc_info:
            await client.create_storage(
                driver="139Yun",
                mount_path="/caiyun-alice",
                addition={"authorization": "tok"},
            )
    finally:
        await client.aclose()

    assert exc_info.value.status_code == 400
    assert "duplicate" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_update_storage_fetches_existing_record_and_posts_full_payload() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "content": [
                        {
                            "id": 5,
                            "mount_path": "/caiyun-alice",
                            "driver": "139Yun",
                            "order": 0,
                            "remark": "",
                            "webdav_policy": "302_redirect",
                            "addition": "{}",
                        }
                    ]
                },
            },
        )
    )
    update_route = respx.post("http://openlist.local/api/admin/storage/update").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {}})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        await client.update_storage(
            5,
            addition={"authorization": "tok-new", "type": "personal_new"},
        )
    finally:
        await client.aclose()

    sent_body = json.loads(update_route.calls.last.request.content)
    assert sent_body["id"] == 5
    assert sent_body["mount_path"] == "/caiyun-alice"
    assert sent_body["driver"] == "139Yun"
    assert sent_body["addition"] == json.dumps(
        {"authorization": "tok-new", "type": "personal_new"}
    )


@pytest.mark.asyncio
@respx.mock
async def test_delete_storage_posts_id_as_query_parameter() -> None:
    route = respx.post("http://openlist.local/api/admin/storage/delete", params={"id": "5"}).mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {}})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        await client.delete_storage(5)
    finally:
        await client.aclose()

    assert route.called is True


@pytest.mark.asyncio
@respx.mock
async def test_delete_storage_by_mount_resolves_id_then_deletes() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "content": [
                        {
                            "id": 5,
                            "mount_path": "/caiyun-alice",
                            "driver": "139Yun",
                            "addition": "{}",
                        }
                    ]
                },
            },
        )
    )
    delete_route = respx.post(
        "http://openlist.local/api/admin/storage/delete",
        params={"id": "5"},
    ).mock(return_value=httpx.Response(200, json={"code": 200, "data": {}}))
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        await client.delete_storage_by_mount("/caiyun-alice")
    finally:
        await client.aclose()

    assert delete_route.called is True


@pytest.mark.asyncio
@respx.mock
async def test_fs_copy_returns_copy_result() -> None:
    route = respx.post("http://openlist.local/api/fs/copy").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {"task_id": "t-123"}})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        result = await client.fs_copy(
            src_dir="/gd/Movies",
            dst_dir="/caiyun-alice/EmbyCache/Movies",
            names=["Movie.2024.mkv"],
        )
    finally:
        await client.aclose()

    assert json.loads(route.calls.last.request.content) == {
        "src_dir": "/gd/Movies",
        "dst_dir": "/caiyun-alice/EmbyCache/Movies",
        "names": ["Movie.2024.mkv"],
    }
    assert result == CopyResult(ok=True, task_id="t-123")


@pytest.mark.asyncio
@respx.mock
async def test_fs_copy_maps_openlist_business_error_to_result() -> None:
    respx.post("http://openlist.local/api/fs/copy").mock(
        return_value=httpx.Response(
            200,
            json={"code": 500, "message": "failed get src storage", "data": None},
        )
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        result = await client.fs_copy(
            src_dir="/missing",
            dst_dir="/caiyun-alice",
            names=["Movie.2024.mkv"],
        )
    finally:
        await client.aclose()

    assert result.ok is False
    assert result.error == "failed get src storage"


@pytest.mark.asyncio
@respx.mock
async def test_fs_list_returns_items() -> None:
    respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "content": [
                        {"name": "Movies", "is_dir": True, "size": 0},
                        {"name": "readme.txt", "is_dir": False, "size": 12},
                    ]
                },
            },
        )
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        items = await client.fs_list("/caiyun-alice")
    finally:
        await client.aclose()

    assert items == [
        FsItem(name="Movies", is_dir=True, size=0),
        FsItem(name="readme.txt", is_dir=False, size=12),
    ]
