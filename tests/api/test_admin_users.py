from fastapi.testclient import TestClient

from gateway.main import create_app


def test_create_user_and_drive_account() -> None:
    client = TestClient(create_app())

    user_response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})
    assert user_response.status_code == 201

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
    assert drive_response.json()["share_pool_enabled"] is True
    assert drive_response.json()["cookie_preview"] == "UID=1..."
