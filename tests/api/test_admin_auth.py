from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def _client(tmp_path: Path, *, admin_password: str = "") -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'auth.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(
        create_app(database_url=database_url, admin_password=admin_password)
    )


def test_admin_auth_is_disabled_when_password_is_not_configured(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        session = client.get("/api/admin/session")
        overview = client.get("/api/admin/overview")

    assert session.status_code == 200
    assert session.json() == {"auth_enabled": False, "authenticated": False}
    assert overview.status_code == 200


def test_admin_auth_protects_api_when_password_is_configured(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        no_cookie = client.get("/api/admin/overview")
        bad_login = client.post("/api/admin/login", json={"password": "wrong"})
        login = client.post("/api/admin/login", json={"password": "secret"})
        after_login = client.get("/api/admin/overview")

    assert no_cookie.status_code == 401
    assert bad_login.status_code == 401
    assert login.status_code == 200
    assert after_login.status_code == 200


def test_admin_logout_clears_session_cookie(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        login = client.post("/api/admin/login", json={"password": "secret"})
        logout = client.post("/api/admin/logout")
        after_logout = client.get("/api/admin/overview")

    assert login.status_code == 200
    assert logout.status_code == 200
    assert after_logout.status_code == 401
