from pathlib import Path

import gateway.api.admin as admin_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import CatalogRow
from gateway.main import create_app
from gateway.models import Base, MediaItem


class StubOpenListClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

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

    async def aclose(self) -> None:
        return None


def test_admin_catalog_sync_endpoint_persists_media(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-catalog.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(admin_module, "OpenListClient", StubOpenListClient)

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.post("/api/admin/catalog/sync", json={"root_path": "/Movies"})

    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 0}

    with Session(engine) as session:
        media = session.execute(select(MediaItem)).scalar_one()

    assert media.fingerprint == "2048:movie.2024:mkv"
