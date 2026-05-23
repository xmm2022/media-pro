import json

import httpx
import pytest
import respx

from common.openlist_creds import CaiyunCredential, fetch_caiyun_credentials


@respx.mock
async def test_fetch_caiyun_credentials_filters_139_storages_and_parses_addition() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "id": 1,
                            "mount_path": "/caiyun-a",
                            "driver": "139Yun",
                            "addition": json.dumps({
                                "access_token": "tok-a",
                                "refresh_token": "rt-a",
                                "type": "personal",
                            }),
                        },
                        {
                            "id": 2,
                            "mount_path": "/gd",
                            "driver": "GoogleDrive",
                            "addition": "{}",
                        },
                    ]
                }
            },
        )
    )

    creds = await fetch_caiyun_credentials(
        base_url="http://openlist.local",
        admin_token="admin-token",
    )

    assert creds == [
        CaiyunCredential(
            mount_path="/caiyun-a",
            access_token="tok-a",
            refresh_token="rt-a",
            extra={"type": "personal"},
        ),
    ]


@respx.mock
async def test_fetch_caiyun_credentials_skips_entries_without_access_token() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "mount_path": "/caiyun-bad",
                            "driver": "139Yun",
                            "addition": json.dumps({"refresh_token": "rt"}),
                        }
                    ]
                }
            },
        )
    )

    creds = await fetch_caiyun_credentials(
        base_url="http://openlist.local",
        admin_token="admin-token",
    )

    assert creds == []
