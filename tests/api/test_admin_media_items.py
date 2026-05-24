from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem


def insert_media(
    session: Session,
    *,
    source_path: str,
    fingerprint: str,
    size: int,
) -> MediaItem:
    media = MediaItem(
        source_path=source_path,
        source_file_id=f"{fingerprint}-id",
        size=size,
        mtime=datetime(2026, 5, 25, 1, 2, tzinfo=timezone.utc),
        fingerprint=fingerprint,
        openlist_path=source_path,
    )
    session.add(media)
    session.flush()
    return media


def test_admin_media_items_endpoint_lists_and_filters_catalog(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'media-items.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        insert_media(
            session,
            source_path="/Movies/Avatar.2009.mkv",
            fingerprint="fp-avatar",
            size=4096,
        )
        insert_media(
            session,
            source_path="/TV/Show.S01E01.mkv",
            fingerprint="fp-show",
            size=2048,
        )
        insert_media(
            session,
            source_path="/Movies/Apollo.1995.mkv",
            fingerprint="fp-apollo",
            size=1024,
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/media-items")
        q_filtered = client.get("/api/admin/media-items", params={"q": "Movies"})
        fingerprint_filtered = client.get(
            "/api/admin/media-items",
            params={"fingerprint": "fp-show"},
        )
        limited = client.get("/api/admin/media-items", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert [item["source_path"] for item in response.json()] == [
        "/Movies/Avatar.2009.mkv",
        "/TV/Show.S01E01.mkv",
        "/Movies/Apollo.1995.mkv",
    ]
    assert response.json()[0] == {
        "id": 1,
        "source_path": "/Movies/Avatar.2009.mkv",
        "source_file_id": "fp-avatar-id",
        "size": 4096,
        "mtime": response.json()[0]["mtime"],
        "fingerprint": "fp-avatar",
        "openlist_path": "/Movies/Avatar.2009.mkv",
    }
    assert [item["id"] for item in q_filtered.json()] == [1, 3]
    assert [item["id"] for item in fingerprint_filtered.json()] == [2]
    assert [item["id"] for item in limited.json()] == [2]
