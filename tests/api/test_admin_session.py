from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def _client(tmp_path: Path, *, admin_password: str = "") -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'session.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(
        create_app(database_url=database_url, admin_password=admin_password)
    )


def test_session_reports_unauthenticated_when_auth_disabled(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": False, "authenticated": False}


def test_session_reports_unauthenticated_when_auth_enabled_no_cookie(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": True, "authenticated": False}


def test_session_reports_authenticated_after_valid_login(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        login = client.post("/api/admin/login", json={"password": "secret"})
        session = client.get("/api/admin/session")

    assert login.status_code == 200
    assert session.status_code == 200
    assert session.json() == {"auth_enabled": True, "authenticated": True}


def test_session_reports_unauthenticated_when_cookie_invalid(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        client.cookies.set("gateway_admin_session", "not-a-valid-token")
        response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": True, "authenticated": False}
