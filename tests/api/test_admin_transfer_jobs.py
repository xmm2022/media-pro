from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem, TransferJob, User


def insert_user(session: Session, username: str) -> User:
    user = User(username=username, status="active")
    session.add(user)
    session.flush()
    return user


def insert_media(session: Session, source_path: str, fingerprint: str) -> MediaItem:
    media = MediaItem(
        source_path=source_path,
        source_file_id=f"{fingerprint}-id",
        size=2048,
        fingerprint=fingerprint,
        openlist_path=source_path,
    )
    session.add(media)
    session.flush()
    return media


def test_admin_transfer_jobs_endpoint_lists_and_filters_attempts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'transfer-jobs.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        alice_id = alice.id
        session.add_all(
            [
                TransferJob(
                    media_id=movie.id,
                    donor_user_id=bob.id,
                    target_user_id=alice.id,
                    route_stage="try_pool",
                    idempotency_key="pool-1",
                    status="failed",
                    error_code="missing_donor_file",
                    attempt_no=1,
                ),
                TransferJob(
                    media_id=movie.id,
                    donor_user_id=None,
                    target_user_id=alice.id,
                    route_stage="try_source_copy",
                    idempotency_key="source-1",
                    status="succeeded",
                    error_code=None,
                    attempt_no=1,
                ),
                TransferJob(
                    media_id=episode.id,
                    donor_user_id=None,
                    target_user_id=bob.id,
                    route_stage="try_source_copy",
                    idempotency_key="source-2",
                    status="failed",
                    error_code="openlist_copy_failed",
                    attempt_no=2,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/transfer-jobs")
        status_filtered = client.get("/api/admin/transfer-jobs", params={"status": "failed"})
        stage_filtered = client.get(
            "/api/admin/transfer-jobs",
            params={"route_stage": "try_pool"},
        )
        target_filtered = client.get(
            "/api/admin/transfer-jobs",
            params={"target_user_id": alice_id},
        )
        limited = client.get("/api/admin/transfer-jobs", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "media_id": 1,
            "donor_user_id": 2,
            "target_user_id": 1,
            "route_stage": "try_pool",
            "idempotency_key": "pool-1",
            "status": "failed",
            "error_code": "missing_donor_file",
            "attempt_no": 1,
        },
        {
            "id": 2,
            "media_id": 1,
            "donor_user_id": None,
            "target_user_id": 1,
            "route_stage": "try_source_copy",
            "idempotency_key": "source-1",
            "status": "succeeded",
            "error_code": None,
            "attempt_no": 1,
        },
        {
            "id": 3,
            "media_id": 2,
            "donor_user_id": None,
            "target_user_id": 2,
            "route_stage": "try_source_copy",
            "idempotency_key": "source-2",
            "status": "failed",
            "error_code": "openlist_copy_failed",
            "attempt_no": 2,
        },
    ]
    assert [item["id"] for item in status_filtered.json()] == [1, 3]
    assert [item["id"] for item in stage_filtered.json()] == [1]
    assert [item["id"] for item in target_filtered.json()] == [1, 2]
    assert [item["id"] for item in limited.json()] == [2]
