from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.catalog_sync import CatalogSyncService
from gateway.catalog import CatalogService
from gateway.integrations.openlist_client import CatalogRow
from gateway.models import Base, MediaItem


class StubOpenListClient:
    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        assert root_path == "/Movies"
        return [
            CatalogRow(
                path="/Movies/Movie.2024.mkv",
                size=2048,
                file_id="gd-1",
                mtime="2026-05-18T00:00:00Z",
            ),
            CatalogRow(
                path="/Movies/Clip.mp4",
                size=512,
                file_id=None,
                mtime=None,
            ),
        ]


@pytest.mark.asyncio
async def test_catalog_sync_service_upserts_media_items(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'catalog-sync.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        result = await CatalogSyncService(CatalogService(), StubOpenListClient()).sync(
            session,
            root_path="/Movies",
        )
        rows = session.scalars(select(MediaItem).order_by(MediaItem.source_path)).all()

    assert result.inserted == 2
    assert result.updated == 0
    assert [row.source_path for row in rows] == ["/Movies/Clip.mp4", "/Movies/Movie.2024.mkv"]
    assert rows[1].fingerprint == "2048:movie.2024:mkv"
