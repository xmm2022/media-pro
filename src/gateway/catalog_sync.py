from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.catalog import CatalogEntry, CatalogService
from gateway.integrations.openlist_client import OpenListClient
from gateway.models import MediaItem


@dataclass(frozen=True, slots=True)
class CatalogSyncResult:
    inserted: int
    updated: int


class CatalogSyncService:
    def __init__(self, catalog_service: CatalogService, openlist_client: OpenListClient) -> None:
        self._catalog_service = catalog_service
        self._openlist_client = openlist_client

    async def sync(self, session: Session, *, root_path: str) -> CatalogSyncResult:
        rows = await self._openlist_client.list_catalog(root_path)
        inserted = 0
        updated = 0

        for row in rows:
            payload = self._catalog_service.to_media_item(
                CatalogEntry(
                    source_path=row.path,
                    source_file_id=row.file_id,
                    size=row.size,
                    mtime=row.mtime,
                )
            )
            media = session.scalar(
                select(MediaItem).where(MediaItem.source_path == row.path)
            )
            if media is None:
                session.add(MediaItem(**payload))
                inserted += 1
                continue

            for key, value in payload.items():
                setattr(media, key, value)
            updated += 1

        session.commit()
        return CatalogSyncResult(inserted=inserted, updated=updated)
