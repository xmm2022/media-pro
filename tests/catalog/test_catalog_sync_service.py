from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
from gateway.integrations.openlist_client import CatalogRow
from gateway.models import Base, MediaItem


class StubOpenListClient:
    def __init__(self) -> None:
        self._calls = 0

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        assert root_path == "/Movies"
        self._calls += 1
        if self._calls == 1:
            return [
                CatalogRow(
                    path="/Movies/Movie.2024.mkv",
                    size=2048,
                    file_id="gd-1",
                    mtime="2026-05-17T00:00:00Z",
                )
            ]
        return [
            CatalogRow(
                path="/Movies/Movie.2024.mkv",
                size=4096,
                file_id="gd-2",
                mtime="2026-05-18T00:00:00Z",
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
    assert media.size == 4096
    assert media.source_file_id == "gd-2"


class CommitFailureSession:
    def __init__(self) -> None:
        self.rollback_called = False

    def scalar(self, *_args, **_kwargs) -> None:
        return None

    def add(self, *_args, **_kwargs) -> None:
        return None

    def commit(self) -> None:
        raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollback_called = True


@pytest.mark.asyncio
async def test_catalog_sync_service_rolls_back_on_commit_failure() -> None:
    service = CatalogSyncService(CatalogService(), StubOpenListClient())
    session = CommitFailureSession()

    with pytest.raises(RuntimeError, match="commit failed"):
        await service.sync_root(session, "/Movies")

    assert session.rollback_called is True
