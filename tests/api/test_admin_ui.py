from fastapi.testclient import TestClient

from gateway.main import create_app


def test_admin_ui_serves_minimal_management_page() -> None:
    client = TestClient(create_app())

    response = client.get("/admin")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "media-pro admin" in response.text
    assert "/api/admin/overview" in response.text
    assert "/api/admin/users" in response.text
    assert "/api/admin/drives" in response.text
    assert "/api/playback/" in response.text
