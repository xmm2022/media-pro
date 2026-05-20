from pathlib import Path

import gateway.api.admin as admin_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.drive115_health_client import DriveHealthResult
from gateway.main import create_app
from gateway.models import Base, User, UserDriveAccount


def insert_user(session: Session, username: str) -> User:
    user = User(username=username, status="active")
    session.add(user)
    session.flush()
    return user


def insert_drive(
    session: Session,
    *,
    app,
    user_id: int,
    cookie: str,
    root_dir: str,
    drive_type: str = "115",
    enabled: bool = True,
    share_pool_enabled: bool = False,
    health_status: str = "unknown",
) -> UserDriveAccount:
    drive = UserDriveAccount(
        user_id=user_id,
        drive_type=drive_type,
        cookie_encrypted=app.state.cookie_cipher.encrypt(cookie),
        root_dir=root_dir,
        enabled=enabled,
        share_pool_enabled=share_pool_enabled,
        health_status=health_status,
    )
    session.add(drive)
    session.flush()
    return drive


def test_admin_drive_probe_endpoint_updates_drive_health_for_115_success(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-probe-115-success.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    class StubDrive115HealthClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def probe(self, target_cookie: str, root_dir: str) -> DriveHealthResult:
            assert target_cookie == "UID=alice"
            assert root_dir == "/EmbyCache/alice"
            return DriveHealthResult(ok=True, error_code=None)

    monkeypatch.setattr(admin_module, "Drive115HealthClient", StubDrive115HealthClient)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            drive_type="115",
            health_status="unknown",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/1/probe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["error_code"] is None
    assert payload["detail"] is None
    assert payload["drive"]["health_status"] == "healthy"
    assert payload["drive"]["last_checked_at"] is not None

    with Session(engine) as session:
        drive = session.scalar(select(UserDriveAccount).where(UserDriveAccount.id == 1))

    assert drive is not None
    assert drive.health_status == "healthy"
    assert drive.last_checked_at is not None


def test_admin_drive_probe_endpoint_persists_failed_115_probe(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-probe-115-fail.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    class StubDrive115HealthClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def probe(self, _target_cookie: str, _root_dir: str) -> DriveHealthResult:
            return DriveHealthResult(
                ok=False,
                error_code="invalid_cookie",
                detail="cookie expired",
            )

    monkeypatch.setattr(admin_module, "Drive115HealthClient", StubDrive115HealthClient)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            drive_type="115",
            health_status="unknown",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/1/probe")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "invalid_cookie"
    assert response.json()["detail"] == "cookie expired"
    assert response.json()["drive"]["health_status"] == "invalid_cookie"
    assert response.json()["drive"]["last_checked_at"] is not None

    with Session(engine) as session:
        drive = session.scalar(select(UserDriveAccount).where(UserDriveAccount.id == 1))

    assert drive is not None
    assert drive.health_status == "invalid_cookie"
    assert drive.last_checked_at is not None


def test_admin_drive_probe_endpoint_checks_alist_root_via_openlist(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-probe-alist.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    class StubOpenListClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def list_catalog(self, root_path: str):
            assert root_path == "/AList/alice"
            return []

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(admin_module, "OpenListClient", StubOpenListClient)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="not-used",
            root_dir="/AList/alice",
            drive_type="alist",
            health_status="unknown",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/1/probe")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["drive"]["health_status"] == "healthy"


def test_admin_drive_probe_endpoint_marks_unknown_drive_type_as_unsupported(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-probe-unsupported.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="token",
            root_dir="/Remote/alice",
            drive_type="dropbox",
            health_status="unknown",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/1/probe")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "unsupported_drive_type"
    assert response.json()["drive"]["health_status"] == "unsupported_drive_type"


def test_admin_drive_probe_endpoint_rejects_unknown_drive(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-probe-missing.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url), raise_server_exceptions=False) as client:
        response = client.post("/api/admin/drives/999/probe")

    assert response.status_code == 404
    assert response.json() == {"detail": "Drive not found"}


def test_admin_drives_bulk_probe_updates_selected_drives_and_returns_mixed_results(
    monkeypatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-bulk-probe.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    class StubDrive115HealthClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def probe(self, target_cookie: str, root_dir: str) -> DriveHealthResult:
            assert root_dir in {"/EmbyCache/alice", "/EmbyCache/bob"}
            if target_cookie == "UID=alice":
                return DriveHealthResult(ok=True, error_code=None)
            return DriveHealthResult(
                ok=False,
                error_code="invalid_cookie",
                detail="cookie expired",
            )

    monkeypatch.setattr(admin_module, "Drive115HealthClient", StubDrive115HealthClient)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            drive_type="115",
            enabled=True,
            health_status="unknown",
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob",
            root_dir="/EmbyCache/bob",
            drive_type="115",
            enabled=True,
            health_status="unknown",
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob-archive",
            root_dir="/Archive/bob",
            drive_type="115",
            enabled=False,
            health_status="cooldown",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/probe", json={"enabled": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched"] == 2
    assert payload["healthy"] == 1
    assert payload["unhealthy"] == 1
    assert payload["drive_ids"] == [1, 2]
    assert [item["drive"]["id"] for item in payload["results"]] == [1, 2]
    assert payload["results"][0]["ok"] is True
    assert payload["results"][0]["drive"]["health_status"] == "healthy"
    assert payload["results"][1]["ok"] is False
    assert payload["results"][1]["error_code"] == "invalid_cookie"
    assert payload["results"][1]["drive"]["health_status"] == "invalid_cookie"
    assert all(item["drive"]["last_checked_at"] is not None for item in payload["results"])

    with Session(engine) as session:
        drives = session.scalars(select(UserDriveAccount).order_by(UserDriveAccount.id)).all()

    assert [drive.health_status for drive in drives] == ["healthy", "invalid_cookie", "cooldown"]
    assert drives[0].last_checked_at is not None
    assert drives[1].last_checked_at is not None
    assert drives[2].last_checked_at is None


def test_admin_drives_bulk_probe_requires_selector(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-bulk-probe-empty.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url), raise_server_exceptions=False) as client:
        response = client.post("/api/admin/drives/probe", json={})

    assert response.status_code == 422
