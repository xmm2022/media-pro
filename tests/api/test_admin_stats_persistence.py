from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.api.admin import summarize_routes
from gateway.main import create_app
from gateway.models import Base, MediaItem, PlaybackRecord, TransferRoute, User


def test_summarize_routes_returns_all_buckets() -> None:
    summary = summarize_routes(["self", "source_stream", "source_stream"])

    assert summary == {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 2}


def test_summarize_routes_ignores_unknown_buckets() -> None:
    summary = summarize_routes(["self", "mystery", "source_stream"])

    assert summary == {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 1}


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
