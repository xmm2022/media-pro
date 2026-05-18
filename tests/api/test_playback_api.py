from pathlib import Path

import gateway.api.playback as playback_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.main import create_app
from gateway.models import Base, MediaItem, User


class StubOpenListClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        assert source_path == "/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://drive.local/Movie.2024.mkv",
            content_length=2048,
            accepts_ranges=True,
        )

    async def aclose(self) -> None:
        return None


def test_playback_api_reads_media_from_database(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-api.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)

    with Session(engine) as session:
        user = User(username="alice")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, media])
        session.commit()
        user_id = user.id
        media_id = media.id

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get(f"/api/playback/{media_id}", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": user_id,
        "media_id": media_id,
        "route": "source_stream",
        "stream_url": "https://drive.local/Movie.2024.mkv",
    }


def test_playback_api_returns_404_when_media_is_missing(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-api-missing-media.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)

    with Session(engine) as session:
        user = User(username="alice")
        session.add(user)
        session.commit()
        user_id = user.id

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/playback/999", params={"user_id": user_id})

    assert response.status_code == 404
    assert response.json() == {"detail": "media 999 not found"}


def test_playback_api_returns_404_when_user_is_missing(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-api-missing-user.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)

    with Session(engine) as session:
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()
        media_id = media.id

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get(f"/api/playback/{media_id}", params={"user_id": 999})

    assert response.status_code == 404
    assert response.json() == {"detail": "user 999 not found"}
