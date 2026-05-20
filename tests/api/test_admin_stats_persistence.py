from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.api.admin import (
    count_stale_drive_probes,
    summarize_drive_probe_errors,
    summarize_drives,
    summarize_pool_objects,
    summarize_routes,
)
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


def test_summarize_routes_returns_all_buckets() -> None:
    summary = summarize_routes(["self", "source_stream", "source_stream"])

    assert summary == {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 2}


def test_summarize_routes_ignores_unknown_buckets() -> None:
    summary = summarize_routes(["self", "mystery", "source_stream"])

    assert summary == {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 1}


def test_summarize_drives_aggregates_drive_buckets() -> None:
    drives = [
        UserDriveAccount(
            user_id=1,
            drive_type="115",
            cookie_encrypted="x",
            root_dir="/a",
            enabled=True,
            share_pool_enabled=True,
            health_status="healthy",
        ),
        UserDriveAccount(
            user_id=1,
            drive_type="115",
            cookie_encrypted="y",
            root_dir="/b",
            enabled=False,
            share_pool_enabled=False,
            health_status="cooldown",
        ),
        UserDriveAccount(
            user_id=2,
            drive_type="alist",
            cookie_encrypted="z",
            root_dir="/c",
            enabled=True,
            share_pool_enabled=False,
            health_status="healthy",
        ),
    ]

    assert summarize_drives(drives) == {
        "total": 3,
        "users": 2,
        "enabled": 2,
        "disabled": 1,
        "share_pool_enabled": 1,
        "by_drive_type": {"115": 2, "alist": 1},
        "by_health_status": {"healthy": 2, "cooldown": 1},
    }


def test_summarize_drive_probe_errors_counts_only_checked_unhealthy_states() -> None:
    now = datetime.now(timezone.utc)
    drives = [
        UserDriveAccount(
            user_id=1,
            drive_type="115",
            cookie_encrypted="x",
            root_dir="/a",
            enabled=True,
            share_pool_enabled=True,
            health_status="healthy",
            last_checked_at=now,
        ),
        UserDriveAccount(
            user_id=1,
            drive_type="115",
            cookie_encrypted="y",
            root_dir="/b",
            enabled=True,
            share_pool_enabled=False,
            health_status="invalid_cookie",
            last_checked_at=now,
        ),
        UserDriveAccount(
            user_id=2,
            drive_type="alist",
            cookie_encrypted="z",
            root_dir="/c",
            enabled=False,
            share_pool_enabled=False,
            health_status="root_dir_unavailable",
            last_checked_at=now,
        ),
        UserDriveAccount(
            user_id=3,
            drive_type="115",
            cookie_encrypted="w",
            root_dir="/d",
            enabled=True,
            share_pool_enabled=False,
            health_status="unknown",
            last_checked_at=None,
        ),
    ]

    assert summarize_drive_probe_errors(drives) == {
        "invalid_cookie": 1,
        "root_dir_unavailable": 1,
    }


def test_count_stale_drive_probes_counts_unchecked_and_old_drives() -> None:
    now = datetime.now(timezone.utc)
    drives = [
        UserDriveAccount(
            user_id=1,
            drive_type="115",
            cookie_encrypted="x",
            root_dir="/a",
            enabled=True,
            share_pool_enabled=True,
            health_status="healthy",
            last_checked_at=now,
        ),
        UserDriveAccount(
            user_id=2,
            drive_type="115",
            cookie_encrypted="y",
            root_dir="/b",
            enabled=True,
            share_pool_enabled=False,
            health_status="invalid_cookie",
            last_checked_at=now - timedelta(hours=3),
        ),
        UserDriveAccount(
            user_id=3,
            drive_type="alist",
            cookie_encrypted="z",
            root_dir="/c",
            enabled=False,
            share_pool_enabled=False,
            health_status="unknown",
            last_checked_at=None,
        ),
    ]

    assert count_stale_drive_probes(
        drives,
        stale_probe_after_hours=2,
        now=now,
    ) == 2


def test_summarize_pool_objects_aggregates_status_and_cooldown_buckets() -> None:
    now = datetime.now(timezone.utc)
    pool_objects = [
        PoolObject(
            media_id=1,
            owner_user_id=1,
            drive_type="115",
            target_path="/a",
            status=PoolObjectStatus.READY,
        ),
        PoolObject(
            media_id=1,
            owner_user_id=1,
            drive_type="115",
            target_path="/b",
            status=PoolObjectStatus.COOLDOWN,
            cooldown_until=now + timedelta(minutes=5),
        ),
        PoolObject(
            media_id=2,
            owner_user_id=2,
            drive_type="alist",
            target_path="/c",
            status=PoolObjectStatus.COOLDOWN,
            cooldown_until=now - timedelta(minutes=5),
        ),
        PoolObject(
            media_id=3,
            owner_user_id=2,
            drive_type="115",
            target_path="/d",
            status=PoolObjectStatus.STALE,
        ),
    ]

    assert summarize_pool_objects(pool_objects, now=now) == {
        "total": 4,
        "owners": 2,
        "media_items": 3,
        "by_status": {
            "ready": 1,
            "suspect": 0,
            "cooldown": 2,
            "disabled": 0,
            "stale": 1,
        },
        "by_drive_type": {"115": 3, "alist": 1},
        "cooldown_active": 1,
        "cooldown_expired": 1,
    }


def test_admin_stats_endpoint_returns_persisted_route_counts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'stats.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        media = MediaItem(
            source_path="/library/movie.mkv",
            source_file_id="file-1",
            size=123,
            fingerprint="fp-1",
            openlist_path="/open/movie.mkv",
        )
        session.add_all([user, media])
        session.flush()
        session.add_all(
            [
                PlaybackRecord(
                    user_id=user.id,
                    media_id=media.id,
                    route=TransferRoute.SELF,
                    success=True,
                    latency_ms=10,
                ),
                PlaybackRecord(
                    user_id=user.id,
                    media_id=media.id,
                    route=TransferRoute.SOURCE_STREAM,
                    success=True,
                    latency_ms=20,
                ),
                PlaybackRecord(
                    user_id=user.id,
                    media_id=media.id,
                    route=TransferRoute.SOURCE_STREAM,
                    success=False,
                    latency_ms=30,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/stats")

    assert response.status_code == 200
    assert response.json() == {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 2}


def test_admin_drive_stats_endpoint_returns_persisted_drive_counts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'drive-stats.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                User(username="alice"),
                User(username="bob"),
            ]
        )
        session.flush()
        session.add_all(
            [
                UserDriveAccount(
                    user_id=1,
                    drive_type="115",
                    cookie_encrypted="enc-1",
                    root_dir="/EmbyCache/alice",
                    enabled=True,
                    share_pool_enabled=True,
                    health_status="healthy",
                ),
                UserDriveAccount(
                    user_id=1,
                    drive_type="115",
                    cookie_encrypted="enc-2",
                    root_dir="/Archive/alice",
                    enabled=False,
                    share_pool_enabled=False,
                    health_status="cooldown",
                ),
                UserDriveAccount(
                    user_id=2,
                    drive_type="alist",
                    cookie_encrypted="enc-3",
                    root_dir="/Mount/bob",
                    enabled=True,
                    share_pool_enabled=False,
                    health_status="healthy",
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/drives/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total": 3,
        "users": 2,
        "enabled": 2,
        "disabled": 1,
        "share_pool_enabled": 1,
        "by_drive_type": {"115": 2, "alist": 1},
        "by_health_status": {"healthy": 2, "cooldown": 1},
    }


def test_admin_pool_object_stats_endpoint_returns_persisted_pool_counts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pool-object-stats.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        session.add_all(
            [
                User(username="alice"),
                User(username="bob"),
            ]
        )
        session.flush()
        media_one = MediaItem(
            source_path="/library/movie.mkv",
            source_file_id="file-1",
            size=123,
            fingerprint="fp-1",
            openlist_path="/open/movie.mkv",
        )
        media_two = MediaItem(
            source_path="/library/episode.mkv",
            source_file_id="file-2",
            size=456,
            fingerprint="fp-2",
            openlist_path="/open/episode.mkv",
        )
        session.add_all([media_one, media_two])
        session.flush()
        session.add_all(
            [
                PoolObject(
                    media_id=media_one.id,
                    owner_user_id=1,
                    drive_type="115",
                    target_path="/EmbyCache/alice/movie.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=media_two.id,
                    owner_user_id=1,
                    drive_type="115",
                    target_path="/EmbyCache/alice/episode.mkv",
                    status=PoolObjectStatus.COOLDOWN,
                    cooldown_until=now + timedelta(minutes=5),
                ),
                PoolObject(
                    media_id=media_one.id,
                    owner_user_id=2,
                    drive_type="alist",
                    target_path="/Mount/bob/movie.mkv",
                    status=PoolObjectStatus.COOLDOWN,
                    cooldown_until=now - timedelta(minutes=5),
                ),
                PoolObject(
                    media_id=media_two.id,
                    owner_user_id=2,
                    drive_type="115",
                    target_path="/EmbyCache/bob/episode.mkv",
                    status=PoolObjectStatus.STALE,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/pool-objects/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total": 4,
        "owners": 2,
        "media_items": 2,
        "by_status": {
            "ready": 1,
            "suspect": 0,
            "cooldown": 2,
            "disabled": 0,
            "stale": 1,
        },
        "by_drive_type": {"115": 3, "alist": 1},
        "cooldown_active": 1,
        "cooldown_expired": 1,
    }
