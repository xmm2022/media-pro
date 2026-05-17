from fastapi.testclient import TestClient

from gateway.main import create_app


def test_admin_stats_endpoint_returns_route_buckets() -> None:
    client = TestClient(create_app())

    response = client.get("/api/admin/stats")

    assert response.status_code == 200
    assert set(response.json()) == {"self", "pool", "source_copy", "source_stream"}
