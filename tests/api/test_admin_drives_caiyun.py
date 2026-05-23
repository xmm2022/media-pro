import json
from pathlib import Path

import gateway.api.admin as admin_module
import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.config import Settings
from gateway.main import create_app
from gateway.models import Base, User, UserDriveAccount


def _bootstrap(tmp_path: Path, db_name: str) -> tuple[object, object]:
    database_url = f"sqlite:///{tmp_path / db_name}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)
    return engine, app


def _seed_user(engine, username: str) -> int:
    with Session(engine) as session:
        user = User(username=username, status="active")
        session.add(user)
        session.commit()
        return user.id


def _configure_openlist_settings(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_OPENLIST_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("GATEWAY_OPENLIST_BASE_URL", "http://openlist.local")
    monkeypatch.setattr(admin_module, "settings", Settings())


@respx.mock
def test_create_caiyun_drive_calls_openlist_then_persists_locally(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-create.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    create_route = respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {"id": 99}})
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/drives",
            json={
                "user_id": user_id,
                "drive_type": "caiyun",
                "root_dir": "/EmbyCache",
                "caiyun": {
                    "access_token": "tok-a",
                    "refresh_token": "rt-a",
                    "account_type": "personal_new",
                },
                "mount_path": "/caiyun-alice",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["drive_type"] == "caiyun"
    assert body["openlist_mount_path"] == "/caiyun-alice"
    assert body["openlist_storage_managed"] is True
    assert body["cookie_preview"] is None
    assert create_route.called is True
    sent_body = json.loads(create_route.calls.last.request.content)
    assert sent_body["mount_path"] == "/caiyun-alice"
    assert sent_body["driver"] == "139Yun"
    assert json.loads(sent_body["addition"]) == {
        "authorization": "tok-a",
        "refresh_token": "rt-a",
        "type": "personal_new",
    }

    with Session(engine) as session:
        drive = session.scalars(select(UserDriveAccount)).one()
    assert drive.cookie_encrypted is None
    assert drive.openlist_mount_path == "/caiyun-alice"
    assert drive.openlist_storage_managed is True
    assert drive.share_pool_enabled is False


@respx.mock
def test_create_caiyun_drive_can_adopt_existing_openlist_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-adopt-existing.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    list_route = respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "content": [
                        {
                            "id": 5,
                            "mount_path": "/yidon",
                            "driver": "139Yun",
                            "addition": "{}",
                        }
                    ]
                },
            },
        )
    )
    create_route = respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(500, json={"code": 500, "message": "should not create"})
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/drives",
            json={
                "user_id": user_id,
                "drive_type": "caiyun",
                "root_dir": "/",
                "mount_path": "/yidon",
                "adopt_existing": True,
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["drive_type"] == "caiyun"
    assert body["openlist_mount_path"] == "/yidon"
    assert body["openlist_storage_managed"] is False
    assert list_route.called is True
    assert create_route.called is False

    with Session(engine) as session:
        drive = session.scalars(select(UserDriveAccount)).one()
    assert drive.cookie_encrypted is None
    assert drive.openlist_mount_path == "/yidon"
    assert drive.openlist_storage_managed is False


@respx.mock
def test_create_caiyun_drive_adopt_existing_returns_404_when_mount_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-adopt-missing.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {"content": []}})
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/drives",
            json={
                "user_id": user_id,
                "drive_type": "caiyun",
                "root_dir": "/",
                "mount_path": "/missing-yidon",
                "adopt_existing": True,
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "error": "mount_missing",
        "mount_path": "/missing-yidon",
    }
    with Session(engine) as session:
        assert session.scalars(select(UserDriveAccount)).all() == []


@respx.mock
def test_create_caiyun_drive_returns_502_when_openlist_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-create-fail.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(
            200,
            json={"code": 400, "message": "duplicate mount_path", "data": None},
        )
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/admin/drives",
            json={
                "user_id": user_id,
                "drive_type": "caiyun",
                "root_dir": "/EmbyCache",
                "caiyun": {
                    "access_token": "tok",
                    "refresh_token": "rt",
                    "account_type": "personal_new",
                },
                "mount_path": "/caiyun-alice",
            },
        )

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "openlist_admin_failed"
    with Session(engine) as session:
        assert session.scalars(select(UserDriveAccount)).all() == []


@respx.mock
def test_probe_caiyun_drive_returns_healthy_when_fs_list_returns_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-probe.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/caiyun-alice",
            openlist_storage_managed=True,
            root_dir="/EmbyCache",
            enabled=True,
            share_pool_enabled=False,
            health_status="unknown",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

    route = respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "data": {"content": [{"name": "x", "is_dir": False, "size": 1}]},
            },
        )
    )

    with TestClient(app) as client:
        response = client.post(f"/api/admin/drives/{drive_id}/probe")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["drive"]["health_status"] == "healthy"
    assert json.loads(route.calls.last.request.content) == {
        "path": "/caiyun-alice",
        "password": "",
    }


@respx.mock
def test_probe_caiyun_drive_maps_openlist_errors(tmp_path: Path, monkeypatch) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-probe-fail.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/missing-caiyun",
            openlist_storage_managed=True,
            root_dir="/EmbyCache",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

    respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={"code": 404, "message": "storage not found", "data": None},
        )
    )

    with TestClient(app) as client:
        response = client.post(f"/api/admin/drives/{drive_id}/probe")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "mount_missing"
    assert response.json()["drive"]["health_status"] == "mount_missing"


@respx.mock
def test_patch_caiyun_drive_updates_openlist_tokens(tmp_path: Path, monkeypatch) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-patch.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/caiyun-alice",
            openlist_storage_managed=True,
            root_dir="/EmbyCache",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

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
    update_route = respx.post("http://openlist.local/api/admin/storage/update").mock(
        return_value=httpx.Response(200, json={"code": 200, "data": {}})
    )

    with TestClient(app) as client:
        response = client.patch(
            f"/api/admin/drives/{drive_id}",
            json={
                "caiyun": {
                    "access_token": "tok-new",
                    "refresh_token": "rt-new",
                    "account_type": "personal_new",
                }
            },
        )

    assert response.status_code == 200
    sent_body = json.loads(update_route.calls.last.request.content)
    assert sent_body["id"] == 5
    assert json.loads(sent_body["addition"]) == {
        "authorization": "tok-new",
        "refresh_token": "rt-new",
        "type": "personal_new",
    }


@respx.mock
def test_patch_caiyun_drive_rejects_token_update_for_adopted_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-patch-unmanaged.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/yidon",
            openlist_storage_managed=False,
            root_dir="/",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

    list_route = respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(500, json={"code": 500, "message": "should not list"})
    )
    update_route = respx.post("http://openlist.local/api/admin/storage/update").mock(
        return_value=httpx.Response(500, json={"code": 500, "message": "should not update"})
    )

    with TestClient(app) as client:
        response = client.patch(
            f"/api/admin/drives/{drive_id}",
            json={
                "caiyun": {
                    "access_token": "tok-new",
                    "refresh_token": "rt-new",
                    "account_type": "personal_new",
                }
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "error": "storage_unmanaged",
        "message": "adopted OpenList storage credentials are managed outside media-pro",
    }
    assert list_route.called is False
    assert update_route.called is False


@respx.mock
def test_delete_caiyun_drive_calls_openlist_then_deletes_locally(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-delete.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/caiyun-alice",
            openlist_storage_managed=True,
            root_dir="/EmbyCache",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

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

    with TestClient(app) as client:
        response = client.delete(f"/api/admin/drives/{drive_id}")

    assert response.status_code == 200
    assert delete_route.called is True
    with Session(engine) as session:
        assert session.scalars(select(UserDriveAccount)).all() == []


@respx.mock
def test_delete_caiyun_drive_keeps_adopted_openlist_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-delete-unmanaged.db")
    user_id = _seed_user(engine, "alice")
    _configure_openlist_settings(monkeypatch)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/yidon",
            openlist_storage_managed=False,
            root_dir="/",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

    list_route = respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(500, json={"code": 500, "message": "should not list"})
    )
    delete_route = respx.post("http://openlist.local/api/admin/storage/delete").mock(
        return_value=httpx.Response(500, json={"code": 500, "message": "should not delete"})
    )

    with TestClient(app) as client:
        response = client.delete(f"/api/admin/drives/{drive_id}")

    assert response.status_code == 200
    assert list_route.called is False
    assert delete_route.called is False
    with Session(engine) as session:
        assert session.scalars(select(UserDriveAccount)).all() == []
