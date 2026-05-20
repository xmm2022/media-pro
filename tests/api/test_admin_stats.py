from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.models import Base

from gateway.main import create_app


def _create_empty_app(tmp_path: Path, database_name: str):
    database_url = f"sqlite:///{tmp_path / database_name}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return create_app(database_url=database_url)


def test_admin_stats_endpoint_returns_route_buckets(tmp_path: Path) -> None:
    client = TestClient(_create_empty_app(tmp_path, "route-stats.db"))

    response = client.get("/api/admin/stats")

    assert response.status_code == 200
    assert response.json() == {"self": 0, "pool": 0, "source_copy": 0, "source_stream": 0}


def test_admin_drive_stats_endpoint_returns_empty_buckets(tmp_path: Path) -> None:
    client = TestClient(_create_empty_app(tmp_path, "drive-stats.db"))

    response = client.get("/api/admin/drives/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "users": 0,
        "enabled": 0,
        "disabled": 0,
        "share_pool_enabled": 0,
        "by_drive_type": {},
        "by_health_status": {},
    }


def test_admin_pool_object_stats_endpoint_returns_empty_buckets(tmp_path: Path) -> None:
    client = TestClient(_create_empty_app(tmp_path, "pool-object-stats.db"))

    response = client.get("/api/admin/pool-objects/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "owners": 0,
        "media_items": 0,
        "by_status": {
            "ready": 0,
            "suspect": 0,
            "cooldown": 0,
            "disabled": 0,
            "stale": 0,
        },
        "by_drive_type": {},
        "cooldown_active": 0,
        "cooldown_expired": 0,
    }
