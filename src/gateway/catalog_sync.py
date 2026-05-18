from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.catalog import CatalogEntry, CatalogService
from gateway.integrations.openlist_client import OpenListClient
from gateway.models import MediaItem


@dataclass(slots=True)
class CatalogSyncSummary:
    created: int
    updated: int


class CatalogSyncService:
    def __init__(self, catalog_service: CatalogService, openlist_client: OpenListClient) -> None:
        self._catalog_service = catalog_service
        self._openlist_client = openlist_client

    async def sync_root(self, session: Session, root_path: str) -> CatalogSyncSummary:
        rows = await self._openlist_client.list_catalog(root_path)
        created = 0
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
            media = session.scalar(select(MediaItem).where(MediaItem.source_path == row.path))
            if media is None:
                session.add(MediaItem(**payload))
                created += 1
                continue
            for field_name, value in payload.items():
                setattr(media, field_name, value)
            updated += 1
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        return CatalogSyncSummary(created=created, updated=updated)
