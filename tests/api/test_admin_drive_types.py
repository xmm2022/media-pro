from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def _client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'drive-types.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(create_app(database_url=database_url))


def test_admin_drive_types_endpoint_returns_provider_capabilities(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/admin/drive-types")

    assert response.status_code == 200
    assert response.json() == [
        {
            "drive_type": "115",
            "label": "115",
            "description": "115 专用用户云盘，保留专用 rapid-copy、池内复用和直链播放能力。",
            "credential_type": "cookie",
            "default_root_dir": "/EmbyCache",
            "capabilities": {
                "can_stream": True,
                "can_source_copy": True,
                "can_pool_copy": True,
                "managed_by_openlist": False,
                "supports_health_probe": True,
                "supports_user_bind": True,
            },
            "credential_fields": [
                {
                    "name": "cookie",
                    "label": "115 Cookie",
                    "secret": True,
                    "required": True,
                    "help_text": "用于 115 专用链路，后端加密保存，接口不会回显明文。",
                }
            ],
        },
        {
            "drive_type": "caiyun",
            "label": "移动云盘 / 139",
            "description": "OpenList-backed 用户云盘，通过 OpenList storage 和 fs/copy 承接源盘复制。",
            "credential_type": "openlist_storage",
            "default_root_dir": "/EmbyCache",
            "capabilities": {
                "can_stream": True,
                "can_source_copy": True,
                "can_pool_copy": False,
                "managed_by_openlist": True,
                "supports_health_probe": True,
                "supports_user_bind": True,
            },
            "credential_fields": [
                {
                    "name": "access_token",
                    "label": "Access Token",
                    "secret": True,
                    "required": True,
                    "help_text": "写入 OpenList 139Yun storage 的 authorization 字段。",
                },
                {
                    "name": "refresh_token",
                    "label": "Refresh Token",
                    "secret": True,
                    "required": False,
                    "help_text": "写入 OpenList 139Yun storage 的 refresh_token 字段。",
                },
                {
                    "name": "account_type",
                    "label": "账号类型",
                    "secret": False,
                    "required": False,
                    "help_text": "默认 personal_new，对应当前 OpenList 139Yun driver 配置。",
                },
            ],
        },
    ]
