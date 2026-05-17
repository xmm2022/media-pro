from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CatalogEntry:
    source_path: str
    source_file_id: str | None
    size: int
    mtime: str | None


class CatalogService:
    def normalize_name(self, source_path: str) -> tuple[str, str]:
        path = Path(source_path)
        return path.stem.lower(), path.suffix.lstrip(".").lower()

    def build_fingerprint(self, source_path: str, size: int) -> str:
        stem, extension = self.normalize_name(source_path)
        return f"{size}:{stem}:{extension}"

    def to_media_item(self, entry: CatalogEntry) -> dict[str, object]:
        return {
            "source_path": entry.source_path,
            "source_file_id": entry.source_file_id,
            "size": entry.size,
            "mtime": entry.mtime,
            "fingerprint": self.build_fingerprint(entry.source_path, entry.size),
            "openlist_path": entry.source_path,
        }
