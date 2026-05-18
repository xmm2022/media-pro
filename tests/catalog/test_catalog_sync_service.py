from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
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
                mtime="2026-05-17T00:00:00Z",
            )
        ]


@pytest.mark.asyncio
async def test_catalog_sync_service_upserts_media_items(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'catalog-sync.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    service = CatalogSyncService(CatalogService(), StubOpenListClient())

    with Session(engine) as session:
        first = await service.sync_root(session, "/Movies")
        second = await service.sync_root(session, "/Movies")
        media = session.execute(select(MediaItem)).scalar_one()

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 0
    assert second.updated == 1
    assert media.openlist_path == "/Movies/Movie.2024.mkv"
