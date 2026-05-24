from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def make_client(
    tmp_path: Path,
    database_name: str,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    database_url = f"sqlite:///{tmp_path / database_name}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(
        create_app(database_url=database_url),
        raise_server_exceptions=raise_server_exceptions,
    )


def test_create_user_and_drive_account(tmp_path: Path) -> None:
    client = make_client(tmp_path, "admin-users.db")

    user_response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})
    assert user_response.status_code == 201
    assert user_response.json() == {"id": 1, "username": "alice", "status": "active"}

    drive_response = client.post(
        "/api/admin/drives",
        json={
            "user_id": user_response.json()["id"],
            "drive_type": "115",
            "cookie": "UID=1; CID=2",
            "root_dir": "/EmbyCache/alice",
            "share_pool_enabled": True,
        },
    )

    assert drive_response.status_code == 201
    assert drive_response.json()["enabled"] is True
    assert drive_response.json()["share_pool_enabled"] is True
    assert drive_response.json()["health_status"] == "unknown"
    assert drive_response.json()["cookie_preview"] == "UID=1..."


def test_list_users_returns_users_in_id_order(tmp_path: Path) -> None:
    client = make_client(tmp_path, "admin-users-list.db")

    first_response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})
    second_response = client.post("/api/admin/users", json={"username": "bob", "status": "disabled"})

    response = client.get("/api/admin/users")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "username": "alice", "status": "active"},
        {"id": 2, "username": "bob", "status": "disabled"},
    ]


def test_create_drive_rejects_unknown_user(tmp_path: Path) -> None:
    client = make_client(tmp_path, "unknown-user.db")

    response = client.post(
        "/api/admin/drives",
        json={
            "user_id": 999,
            "drive_type": "115",
            "cookie": "UID=1; CID=2",
            "root_dir": "/EmbyCache/missing",
            "share_pool_enabled": False,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_create_user_rejects_duplicate_username(tmp_path: Path) -> None:
    client = make_client(tmp_path, "duplicate-user.db", raise_server_exceptions=False)

    first_response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})
    second_response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Username already exists"}


def test_create_user_initializes_schema_for_fresh_database(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    app = create_app(database_url=f"sqlite:///{db_path}")

    assert not db_path.exists()

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "alice", "status": "active"}


def test_create_user_initializes_schema_for_plain_testclient_fresh_database(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "plain-client-fresh.db"
    client = TestClient(create_app(database_url=f"sqlite:///{db_path}"))

    response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "alice", "status": "active"}


def test_create_app_instances_can_use_independent_databases(tmp_path: Path) -> None:
    first_client = make_client(tmp_path, "first.db")
    second_client = make_client(tmp_path, "second.db")

    first_response = first_client.post("/api/admin/users", json={"username": "alice", "status": "active"})
    second_response = second_client.post("/api/admin/users", json={"username": "bob", "status": "active"})

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == 1
    assert second_response.json()["id"] == 1
