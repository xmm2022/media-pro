from datetime import UTC, datetime

from gateway.catalog import CatalogEntry, CatalogService


def test_catalog_service_builds_weak_fingerprint() -> None:
    service = CatalogService()
    entry = CatalogEntry(
        source_path="/Movies/Movie.2024.mkv",
        source_file_id="gd-1",
        size=2048,
        mtime="2026-05-17T00:00:00Z",
    )

    item = service.to_media_item(entry)

    assert item["fingerprint"] == "2048:movie.2024:mkv"
    assert item["openlist_path"] == "/Movies/Movie.2024.mkv"
    assert item["mtime"] == datetime(2026, 5, 17, 0, 0, tzinfo=UTC)
    assert isinstance(item["mtime"], datetime)
    assert item["mtime"].tzinfo is UTC
