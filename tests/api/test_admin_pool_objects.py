from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem, PoolObject, PoolObjectStatus, User


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


def test_admin_pool_objects_endpoint_lists_and_filters_health_state(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pool-objects.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.COOLDOWN,
                    last_failure_at=now,
                    failure_count=2,
                    cooldown_until=now + timedelta(minutes=5),
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.READY,
                    last_success_at=now,
                    failure_count=0,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.STALE,
                    last_failure_at=now - timedelta(hours=1),
                    failure_count=1,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/pool-objects")
        status_filtered = client.get("/api/admin/pool-objects", params={"status": "cooldown"})
        owner_filtered = client.get("/api/admin/pool-objects", params={"owner_user_id": 1})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "media_id": 1,
            "owner_user_id": 1,
            "drive_type": "115",
            "target_path": "/EmbyCache/alice/Movies/Movie.2024.mkv",
            "status": "cooldown",
            "last_verified_at": None,
            "last_success_at": None,
            "last_failure_at": response.json()[0]["last_failure_at"],
            "failure_count": 2,
            "cooldown_until": response.json()[0]["cooldown_until"],
        },
        {
            "id": 2,
            "media_id": 2,
            "owner_user_id": 1,
            "drive_type": "115",
            "target_path": "/EmbyCache/alice/TV/Show.S01E01.mkv",
            "status": "ready",
            "last_verified_at": None,
            "last_success_at": response.json()[1]["last_success_at"],
            "last_failure_at": None,
            "failure_count": 0,
            "cooldown_until": None,
        },
        {
            "id": 3,
            "media_id": 1,
            "owner_user_id": 2,
            "drive_type": "115",
            "target_path": "/EmbyCache/bob/Movies/Movie.2024.mkv",
            "status": "stale",
            "last_verified_at": None,
            "last_success_at": None,
            "last_failure_at": response.json()[2]["last_failure_at"],
            "failure_count": 1,
            "cooldown_until": None,
        },
    ]
    assert status_filtered.status_code == 200
    assert [item["id"] for item in status_filtered.json()] == [1]
    assert owner_filtered.status_code == 200
    assert [item["id"] for item in owner_filtered.json()] == [1, 2]


def test_admin_pool_object_recover_endpoint_resets_state(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'recover-pool-object.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    last_failure_at = datetime.now(timezone.utc)
    cooldown_until = last_failure_at + timedelta(minutes=5)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        session.add(
            PoolObject(
                media_id=movie.id,
                owner_user_id=alice.id,
                drive_type="115",
                target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.COOLDOWN,
                last_failure_at=last_failure_at,
                failure_count=3,
                cooldown_until=cooldown_until,
            )
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.post("/api/admin/pool-objects/1/recover")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["failure_count"] == 0
    assert response.json()["cooldown_until"] is None

    with Session(engine) as session:
        pool_object = session.scalar(select(PoolObject).where(PoolObject.id == 1))

    assert pool_object is not None
    assert pool_object.status == PoolObjectStatus.READY
    assert pool_object.failure_count == 0
    assert pool_object.cooldown_until is None
    assert pool_object.last_failure_at is not None


def test_admin_pool_object_recover_endpoint_rejects_unknown_id(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'recover-pool-object-missing.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.post("/api/admin/pool-objects/999/recover")

    assert response.status_code == 404
    assert response.json() == {"detail": "Pool object not found"}


def test_admin_pool_objects_bulk_recover_defaults_to_recoverable_statuses(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'bulk-recover-pool-objects.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.COOLDOWN,
                    failure_count=2,
                    cooldown_until=now + timedelta(minutes=5),
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.STALE,
                    failure_count=1,
                    last_failure_at=now,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie-copy.mkv",
                    status=PoolObjectStatus.SUSPECT,
                    failure_count=1,
                    last_failure_at=now,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/TV/Show-disabled.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=4,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie-ready.mkv",
                    status=PoolObjectStatus.READY,
                    failure_count=0,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.post("/api/admin/pool-objects/recover", json={"owner_user_id": 1})

    assert response.status_code == 200
    assert response.json()["matched"] == 3
    assert response.json()["updated"] == 3
    assert [item["status"] for item in response.json()["pool_objects"]] == ["ready", "ready", "ready"]

    with Session(engine) as session:
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
        PoolObjectStatus.DISABLED,
        PoolObjectStatus.READY,
    ]
    assert [pool_object.failure_count for pool_object in pool_objects] == [0, 0, 0, 4, 0]
    assert pool_objects[0].cooldown_until is None


def test_admin_pool_objects_bulk_disable_and_enable_support_owner_level_donor_control(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'bulk-disable-enable-pool-objects.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
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
                    failure_count=0,
                ),
                PoolObject(
                    media_id=episode.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/TV/Show.S01E01.mkv",
                    status=PoolObjectStatus.SUSPECT,
                    failure_count=2,
                    last_failure_at=now,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=alice.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movies/Movie-disabled.mkv",
                    status=PoolObjectStatus.DISABLED,
                    failure_count=3,
                ),
                PoolObject(
                    media_id=movie.id,
                    owner_user_id=bob.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                    failure_count=0,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        disable_response = client.post("/api/admin/pool-objects/disable", json={"owner_user_id": 1})
        enable_response = client.post("/api/admin/pool-objects/enable", json={"owner_user_id": 1})

    assert disable_response.status_code == 200
    assert disable_response.json()["matched"] == 3
    assert disable_response.json()["updated"] == 2
    assert [item["status"] for item in disable_response.json()["pool_objects"]] == [
        "disabled",
        "disabled",
        "disabled",
    ]

    assert enable_response.status_code == 200
    assert enable_response.json()["matched"] == 3
    assert enable_response.json()["updated"] == 3
    assert [item["status"] for item in enable_response.json()["pool_objects"]] == [
        "ready",
        "ready",
        "ready",
    ]

    with Session(engine) as session:
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert [pool_object.status for pool_object in pool_objects] == [
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
        PoolObjectStatus.READY,
    ]
    assert [pool_object.failure_count for pool_object in pool_objects] == [0, 0, 0, 0]


def test_admin_pool_objects_bulk_actions_require_at_least_one_selector(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'bulk-action-selector.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with TestClient(create_app(database_url=database_url), raise_server_exceptions=False) as client:
        response = client.post("/api/admin/pool-objects/disable", json={})

    assert response.status_code == 422
