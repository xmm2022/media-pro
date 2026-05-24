from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem, PlaybackRecord, TransferRoute, User


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


def test_admin_playback_records_endpoint_lists_and_filters_routes(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-records.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        alice_id = alice.id
        session.add_all(
            [
                PlaybackRecord(
                    user_id=alice.id,
                    media_id=movie.id,
                    route=TransferRoute.SELF,
                    success=True,
                    latency_ms=11,
                ),
                PlaybackRecord(
                    user_id=alice.id,
                    media_id=episode.id,
                    route=TransferRoute.SOURCE_COPY,
                    success=True,
                    latency_ms=22,
                ),
                PlaybackRecord(
                    user_id=bob.id,
                    media_id=movie.id,
                    route=TransferRoute.SOURCE_STREAM,
                    success=False,
                    latency_ms=33,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/playback-records")
        user_filtered = client.get(
            "/api/admin/playback-records",
            params={"user_id": alice_id},
        )
        route_filtered = client.get(
            "/api/admin/playback-records",
            params={"route": "source_stream"},
        )
        success_filtered = client.get(
            "/api/admin/playback-records",
            params={"success": "false"},
        )
        limited = client.get("/api/admin/playback-records", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "user_id": 1,
            "media_id": 1,
            "route": "self",
            "success": True,
            "latency_ms": 11,
        },
        {
            "id": 2,
            "user_id": 1,
            "media_id": 2,
            "route": "source_copy",
            "success": True,
            "latency_ms": 22,
        },
        {
            "id": 3,
            "user_id": 2,
            "media_id": 1,
            "route": "source_stream",
            "success": False,
            "latency_ms": 33,
        },
    ]
    assert [item["id"] for item in user_filtered.json()] == [1, 2]
    assert [item["id"] for item in route_filtered.json()] == [3]
    assert [item["id"] for item in success_filtered.json()] == [3]
    assert [item["id"] for item in limited.json()] == [2]
