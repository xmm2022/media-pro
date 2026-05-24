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


def test_admin_auth_is_disabled_when_password_is_not_configured(tmp_path) -> None:
    client = TestClient(
        create_app(database_url=f"sqlite:///{tmp_path / 'auth-disabled.db'}", admin_password="")
    )

    page_response = client.get("/admin")
    api_response = client.get("/api/admin/users")
    session_response = client.get("/api/admin/session")

    assert page_response.status_code == 200
    assert api_response.status_code == 200
    assert api_response.json() == []
    assert session_response.status_code == 200
    assert session_response.json() == {"auth_enabled": False}


def test_admin_auth_protects_ui_and_api_when_password_is_configured(tmp_path) -> None:
    client = TestClient(
        create_app(
            database_url=f"sqlite:///{tmp_path / 'auth-enabled.db'}",
            admin_password="secret",
            cookie_secret="x" * 32,
        ),
        follow_redirects=False,
    )

    page_response = client.get("/admin")
    api_response = client.get("/api/admin/users")
    login_page_response = client.get("/admin/login")
    session_response = client.get("/api/admin/session")
    bad_login_response = client.post("/api/admin/login", json={"password": "wrong"})
    login_response = client.post("/api/admin/login", json={"password": "secret"})

    assert page_response.status_code == 303
    assert page_response.headers["location"] == "/admin/login"
    assert api_response.status_code == 401
    assert api_response.json() == {"detail": "admin authentication required"}
    assert login_page_response.status_code == 200
    assert "media-pro admin login" in login_page_response.text
    assert session_response.status_code == 200
    assert session_response.json() == {"auth_enabled": True}
    assert bad_login_response.status_code == 401
    assert login_response.status_code == 200
    assert login_response.json() == {"ok": True, "auth_enabled": True}
    assert "gateway_admin_session" in login_response.headers["set-cookie"]
    assert "HttpOnly" in login_response.headers["set-cookie"]

    authenticated_page_response = client.get("/admin")
    authenticated_api_response = client.get("/api/admin/users")

    assert authenticated_page_response.status_code == 200
    assert "media-pro admin" in authenticated_page_response.text
    assert authenticated_api_response.status_code == 200
    assert authenticated_api_response.json() == []


def test_admin_logout_clears_session_cookie(tmp_path) -> None:
    client = TestClient(
        create_app(
            database_url=f"sqlite:///{tmp_path / 'auth-logout.db'}",
            admin_password="secret",
            cookie_secret="x" * 32,
        ),
        follow_redirects=False,
    )
    login_response = client.post("/api/admin/login", json={"password": "secret"})

    logout_response = client.post("/api/admin/logout")
    protected_response = client.get("/api/admin/users")

    assert login_response.status_code == 200
    assert logout_response.status_code == 200
    assert logout_response.json() == {"ok": True}
    assert "gateway_admin_session" in logout_response.headers["set-cookie"]
    assert protected_response.status_code == 401
