from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import (
    Base,
    MediaItem,
    PlaybackRecord,
    PoolObject,
    PoolObjectStatus,
    TransferRoute,
    User,
    UserDriveAccount,
)


def insert_user(session: Session, username: str) -> User:
    user = User(username=username, status="active")
    session.add(user)
    session.flush()
    return user


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


def insert_drive(
    session: Session,
    *,
    app,
    user_id: int,
    cookie: str,
    root_dir: str,
    enabled: bool = True,
    share_pool_enabled: bool = False,
    health_status: str = "unknown",
    last_checked_at: datetime | None = None,
) -> UserDriveAccount:
    drive = UserDriveAccount(
        user_id=user_id,
        drive_type="115",
        cookie_encrypted=app.state.cookie_cipher.encrypt(cookie),
        root_dir=root_dir,
        enabled=enabled,
        share_pool_enabled=share_pool_enabled,
        health_status=health_status,
        last_checked_at=last_checked_at,
    )
    session.add(drive)
    session.flush()
    return drive


def test_admin_overview_endpoint_returns_empty_sections(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-overview-empty.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)

    with TestClient(app) as client:
        response = client.get("/api/admin/overview")

    assert response.status_code == 200
    assert response.json() == {
        "routes": {"self": 0, "pool": 0, "source_copy": 0, "source_stream": 0},
        "drives": {
            "stats": {
                "total": 0,
                "users": 0,
                "enabled": 0,
                "disabled": 0,
                "share_pool_enabled": 0,
                "by_drive_type": {},
                "by_health_status": {},
            },
            "attention_total": 0,
            "probe_error_distribution": {},
            "stale_probe_count": 0,
            "stale_probe_threshold_hours": 24,
            "items": [],
        },
        "pool_objects": {
            "stats": {
                "total": 0,
                "owners": 0,
                "media_items": 0,
                "by_status": {
                    "ready": 0,
                    "suspect": 0,
                    "cooldown": 0,
                    "disabled": 0,
                    "stale": 0,
                },
                "by_drive_type": {},
                "cooldown_active": 0,
                "cooldown_expired": 0,
            },
            "attention_total": 0,
            "items": [],
        },
    }


def test_admin_overview_endpoint_returns_stats_and_limited_attention_items(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-overview.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        extra = insert_media(session, "/Clips/Extra.mkv", "fp-extra")
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-main",
            root_dir="/EmbyCache/alice",
            enabled=True,
            share_pool_enabled=True,
            health_status="healthy",
            last_checked_at=now,
        )
        insert_drive(
            session,
            app=app,
            user_id=alice.id,
            cookie="UID=alice-archive",
            root_dir="/Archive/alice",
            enabled=False,
            share_pool_enabled=False,
            health_status="healthy",
            last_checked_at=now - timedelta(hours=3),
        )
        insert_drive(
            session,
            app=app,
            user_id=bob.id,
            cookie="UID=bob-main",
            root_dir="/EmbyCache/bob",
            enabled=True,
            share_pool_enabled=False,
            health_status="invalid_cookie",
            last_checked_at=now - timedelta(minutes=30),
        )
        session.add_all(
            [
                PlaybackRecord(
                    user_id=alice.id,
                    media_id=movie.id,
                    route=TransferRoute.SELF,
                    success=True,
                    latency_ms=10,
                ),
                PlaybackRecord(
                    user_id=alice.id,
                    media_id=episode.id,
                    route=TransferRoute.SOURCE_STREAM,
                    success=True,
                    latency_ms=20,
                ),
                PlaybackRecord(
                    user_id=bob.id,
                    media_id=movie.id,
                    route=TransferRoute.SOURCE_STREAM,
                    success=False,
                    latency_ms=30,
                ),
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
                    status=PoolObjectStatus.COOLDOWN,
                    cooldown_until=now + timedelta(minutes=5),
                    failure_count=2,
                    last_failure_at=now,
                ),
                PoolObject(
                    media_id=extra.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Clips/Extra.mkv",
                    status=PoolObjectStatus.STALE,
                    failure_count=1,
                    last_failure_at=now - timedelta(minutes=10),
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
        response = client.get(
            "/api/admin/overview",
            params={
                "drive_limit": 2,
                "pool_object_limit": 2,
                "stale_probe_after_hours": 1,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["drives"]["items"][0]["last_checked_at"] is not None
    assert payload["drives"]["items"][1]["last_checked_at"] is not None
    assert payload["pool_objects"]["items"][0]["last_failure_at"] is not None
    assert payload["pool_objects"]["items"][0]["cooldown_until"] is not None
    assert payload["pool_objects"]["items"][1]["last_failure_at"] is not None

    assert payload == {
        "routes": {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 2},
        "drives": {
            "stats": {
                "total": 3,
                "users": 2,
                "enabled": 2,
                "disabled": 1,
                "share_pool_enabled": 1,
                "by_drive_type": {"115": 3},
                "by_health_status": {"healthy": 2, "invalid_cookie": 1},
            },
            "attention_total": 2,
            "probe_error_distribution": {"invalid_cookie": 1},
            "stale_probe_count": 1,
            "stale_probe_threshold_hours": 1,
            "items": [
                {
                    "id": 2,
                    "user_id": 1,
                    "drive_type": "115",
                    "root_dir": "/Archive/alice",
                    "enabled": False,
                    "share_pool_enabled": False,
                    "health_status": "healthy",
                    "last_checked_at": payload["drives"]["items"][0]["last_checked_at"],
                    "cookie_preview": "UID=a...",
                    "openlist_mount_path": None,
                    "openlist_storage_managed": True,
                },
                {
                    "id": 3,
                    "user_id": 2,
                    "drive_type": "115",
                    "root_dir": "/EmbyCache/bob",
                    "enabled": True,
                    "share_pool_enabled": False,
                    "health_status": "invalid_cookie",
                    "last_checked_at": payload["drives"]["items"][1]["last_checked_at"],
                    "cookie_preview": "UID=b...",
                    "openlist_mount_path": None,
                    "openlist_storage_managed": True,
                },
            ],
        },
        "pool_objects": {
            "stats": {
                "total": 4,
                "owners": 2,
                "media_items": 3,
                "by_status": {
                    "ready": 1,
                    "suspect": 0,
                    "cooldown": 1,
                    "disabled": 1,
                    "stale": 1,
                },
                "by_drive_type": {"115": 4},
                "cooldown_active": 1,
                "cooldown_expired": 0,
            },
            "attention_total": 3,
            "items": [
                {
                    "id": 2,
                    "media_id": 2,
                    "owner_user_id": 1,
                    "drive_type": "115",
                    "target_path": "/EmbyCache/alice/TV/Show.S01E01.mkv",
                    "status": "cooldown",
                    "last_verified_at": None,
                    "last_success_at": None,
                    "last_failure_at": payload["pool_objects"]["items"][0]["last_failure_at"],
                    "failure_count": 2,
                    "cooldown_until": payload["pool_objects"]["items"][0]["cooldown_until"],
                },
                {
                    "id": 3,
                    "media_id": 3,
                    "owner_user_id": 1,
                    "drive_type": "115",
                    "target_path": "/EmbyCache/alice/Clips/Extra.mkv",
                    "status": "stale",
                    "last_verified_at": None,
                    "last_success_at": None,
                    "last_failure_at": payload["pool_objects"]["items"][1]["last_failure_at"],
                    "failure_count": 1,
                    "cooldown_until": None,
                },
            ],
        },
    }
