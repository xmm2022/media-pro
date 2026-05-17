from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, UserDriveAccount


def test_drive_account_is_persisted_with_encrypted_cookie(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'gateway.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    client = TestClient(create_app(database_url=database_url, cookie_secret="x" * 32))

    user_response = client.post("/api/admin/users", json={"username": "alice", "status": "active"})
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

    with Session(engine) as session:
        drive = session.execute(select(UserDriveAccount)).scalar_one()
        assert drive.cookie_encrypted != "UID=1; CID=2"
        assert drive.share_pool_enabled is True
