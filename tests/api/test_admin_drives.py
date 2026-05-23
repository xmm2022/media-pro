from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem, PoolObject, PoolObjectStatus, User, UserDriveAccount


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
    cookie: str | None,
    root_dir: str,
    drive_type: str = "115",
    enabled: bool = True,
    share_pool_enabled: bool = False,
    health_status: str = "unknown",
    openlist_mount_path: str | None = None,
) -> UserDriveAccount:
    cookie_encrypted = app.state.cookie_cipher.encrypt(cookie) if cookie is not None else None
    drive = UserDriveAccount(
        user_id=user_id,
        drive_type=drive_type,
        cookie_encrypted=cookie_encrypted,
        root_dir=root_dir,
        enabled=enabled,
        share_pool_enabled=share_pool_enabled,
        health_status=health_status,
        openlist_mount_path=openlist_mount_path,
    )
    session.add(drive)
    session.flush()
    return drive


def insert_media(session: Session, source_path: str, fingerprint: str) -> MediaItem:
    media = MediaItem(
        source_path=source_path,
        source_file_id=f"{fingerprint}-id",
        size=2048,
        fingerprint=fingerprint,
        openlist_path=source_path,
    )
    session.add(media)
    session.flush()
    return media


def test_admin_drives_endpoint_lists_and_filters_drive_accounts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-list.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-main",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=True,
            health_status="healthy",
        )
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-archive",
            root_dir="/Archive/alice",
            enabled=False,
            share_pool_enabled=False,
            health_status="cooldown",
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob-main",
            root_dir="/EmbyCache/bob",
            enabled=True,
            share_pool_enabled=False,
            health_status="healthy",
        )
        session.commit()

    with TestClient(app) as client:
        response = client.get("/api/admin/drives")
        user_filtered = client.get("/api/admin/drives", params={"user_id": 1})
        enabled_filtered = client.get("/api/admin/drives", params={"enabled": "true"})
        shared_filtered = client.get("/api/admin/drives", params={"share_pool_enabled": "true"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "user_id": 1,
            "drive_type": "115",
            "root_dir": "/EmbyCache/alice",
            "enabled": True,
            "share_pool_enabled": True,
            "health_status": "healthy",
            "last_checked_at": None,
            "cookie_preview": "UID=a...",
            "openlist_mount_path": None,
        },
        {
            "id": 2,
            "user_id": 1,
            "drive_type": "115",
            "root_dir": "/Archive/alice",
            "enabled": False,
            "share_pool_enabled": False,
            "health_status": "cooldown",
            "last_checked_at": None,
            "cookie_preview": "UID=a...",
            "openlist_mount_path": None,
        },
        {
            "id": 3,
            "user_id": 2,
            "drive_type": "115",
            "root_dir": "/EmbyCache/bob",
            "enabled": True,
            "share_pool_enabled": False,
            "health_status": "healthy",
            "last_checked_at": None,
            "cookie_preview": "UID=b...",
            "openlist_mount_path": None,
        },
    ]
    assert [item["id"] for item in user_filtered.json()] == [1, 2]
    assert [item["id"] for item in enabled_filtered.json()] == [1, 3]
    assert [item["id"] for item in shared_filtered.json()] == [1]


def test_admin_drive_patch_updates_operational_fields_and_cookie(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-patch.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-old",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=False,
            health_status="unknown",
        )
        session.commit()
        previous_encrypted_cookie = session.scalar(
            select(UserDriveAccount.cookie_encrypted).where(UserDriveAccount.id == 1)
        )

    with TestClient(app) as client:
        response = client.patch(
            "/api/admin/drives/1",
            json={
                "cookie": "UID=alice-new",
                "root_dir": "/EmbyCache/alice-new",
                "enabled": False,
                "share_pool_enabled": True,
                "health_status": "healthy",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "user_id": 1,
        "drive_type": "115",
        "root_dir": "/EmbyCache/alice-new",
        "enabled": False,
        "share_pool_enabled": True,
        "health_status": "healthy",
        "last_checked_at": None,
        "cookie_preview": "UID=a...",
        "openlist_mount_path": None,
    }

    with Session(engine) as session:
        drive = session.get(UserDriveAccount, 1)

    assert drive is not None
    assert drive.root_dir == "/EmbyCache/alice-new"
    assert drive.enabled is False
    assert drive.share_pool_enabled is True
    assert drive.health_status == "healthy"
    assert drive.cookie_encrypted != previous_encrypted_cookie
    assert app.state.cookie_cipher.decrypt(drive.cookie_encrypted) == "UID=alice-new"


def test_admin_drive_patch_rejects_unknown_drive(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-patch-missing.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url), raise_server_exceptions=False) as client:
        response = client.patch("/api/admin/drives/999", json={"enabled": False})

    assert response.status_code == 404
    assert response.json() == {"detail": "Drive not found"}


def test_admin_drive_patch_requires_at_least_one_change(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-patch-empty.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-old",
            root_dir="/EmbyCache/alice",
        )
        session.commit()

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.patch("/api/admin/drives/1", json={})

    assert response.status_code == 422


def test_admin_drive_patch_disables_matching_pool_objects_when_drive_is_disabled(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-disable-sync.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=True,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/Archive/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.patch("/api/admin/drives/1", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["enabled"] is False

    with Session(engine) as session:
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
    ]


def test_admin_drive_patch_reenables_matching_disabled_pool_objects_when_drive_is_reenabled(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-enable-sync.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            enabled=False,
            share_pool_enabled=False,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=3,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/Archive/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=4,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.patch("/api/admin/drives/1", json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["enabled"] is True

    with Session(engine) as session:
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.READY,
        PoolObjectStatus.DISABLED,
    ]
    assert [pool_object.failure_count for pool_object in pool_objects] == [0, 4]


def test_admin_drive_patch_root_dir_change_disables_old_root_pool_objects(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-root-sync.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            enabled=True,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.SUSPECT,
                    failure_count=2,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.patch("/api/admin/drives/1", json={"root_dir": "/NewCache/alice"})

    assert response.status_code == 200
    assert response.json()["root_dir"] == "/NewCache/alice"

    with Session(engine) as session:
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.DISABLED,
    ]


def test_admin_drive_delete_removes_drive_and_disables_matching_pool_objects(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-delete.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=True,
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob",
            root_dir="/EmbyCache/bob",
            enabled=True,
            share_pool_enabled=True,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/Archive/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.SUSPECT,
                    failure_count=2,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.delete("/api/admin/drives/1")
        remaining_drives = client.get("/api/admin/drives")

    assert response.status_code == 200
    assert response.json() == {
        "drive_id": 1,
        "user_id": 1,
        "disabled_pool_objects": 1,
    }
    assert remaining_drives.status_code == 200
    assert [item["id"] for item in remaining_drives.json()] == [2]

    with Session(engine) as session:
        drives = session.scalars(select(UserDriveAccount).order_by(UserDriveAccount.id)).all()
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [drive.id for drive in drives] == [2]
    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.SUSPECT,
        PoolObjectStatus.READY,
    ]


def test_admin_drive_delete_rejects_unknown_drive(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drive-delete-missing.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url), raise_server_exceptions=False) as client:
        response = client.delete("/api/admin/drives/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Drive not found"}


def test_admin_drives_bulk_disable_updates_selected_drives_and_pool_objects(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-bulk-disable.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-1",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=True,
        )
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-2",
            root_dir="/Archive/alice",
            enabled=False,
            share_pool_enabled=True,
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob-1",
            root_dir="/EmbyCache/bob",
            enabled=True,
            share_pool_enabled=False,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/Archive/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/disable", json={"user_id": 1})

    assert response.status_code == 200
    assert response.json() == {
        "matched": 2,
        "updated": 1,
        "deleted": 0,
        "updated_pool_objects": 2,
        "drive_ids": [1, 2],
    }

    with Session(engine) as session:
        drives = session.scalars(select(UserDriveAccount).order_by(UserDriveAccount.id)).all()
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [drive.enabled for drive in drives] == [False, False, True]
    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.READY,
    ]


def test_admin_drives_bulk_enable_updates_selected_drives_and_pool_objects(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-bulk-enable.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-1",
            root_dir="/EmbyCache/alice",
            enabled=False,
            share_pool_enabled=True,
        )
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-2",
            root_dir="/Archive/alice",
            enabled=True,
            share_pool_enabled=True,
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob-1",
            root_dir="/EmbyCache/bob",
            enabled=False,
            share_pool_enabled=False,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=3,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/Archive/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=2,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=4,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/enable", json={"user_id": 1})

    assert response.status_code == 200
    assert response.json() == {
        "matched": 2,
        "updated": 1,
        "deleted": 0,
        "updated_pool_objects": 2,
        "drive_ids": [1, 2],
    }

    with Session(engine) as session:
        drives = session.scalars(select(UserDriveAccount).order_by(UserDriveAccount.id)).all()
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [drive.enabled for drive in drives] == [True, True, False]
    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
        PoolObjectStatus.DISABLED,
    ]
    assert [pool_object.failure_count for pool_object in pool_objects] == [0, 0, 4]


def test_admin_drives_bulk_delete_removes_selected_drives_and_disables_pool_objects(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-bulk-delete.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-1",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=True,
        )
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-2",
            root_dir="/Archive/alice",
            enabled=True,
            share_pool_enabled=False,
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob-1",
            root_dir="/EmbyCache/bob",
            enabled=True,
            share_pool_enabled=True,
        )
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/Archive/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.SUSPECT,
                    failure_count=2,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.post("/api/admin/drives/delete", json={"user_id": 1})
        remaining = client.get("/api/admin/drives")

    assert response.status_code == 200
    assert response.json() == {
        "matched": 2,
        "updated": 0,
        "deleted": 2,
        "updated_pool_objects": 2,
        "drive_ids": [1, 2],
    }
    assert remaining.status_code == 200
    assert [item["id"] for item in remaining.json()] == [3]

    with Session(engine) as session:
        drives = session.scalars(select(UserDriveAccount).order_by(UserDriveAccount.id)).all()
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [drive.id for drive in drives] == [3]
    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.READY,
    ]


def test_admin_drives_bulk_actions_require_at_least_one_selector(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-drives-bulk-selector.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url), raise_server_exceptions=False) as client:
        response = client.post("/api/admin/drives/disable", json={})

    assert response.status_code == 422
