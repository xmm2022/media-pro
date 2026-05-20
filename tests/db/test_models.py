import os
import sqlite3
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from gateway.models import (
    Base,
    MediaItem,
    PlaybackRecord,
    PoolObject,
    PoolObjectStatus,
    TransferRoute,
    User,
)


def test_model_enums_expose_expected_values() -> None:
    assert PoolObjectStatus.READY.value == "ready"
    assert PoolObjectStatus.COOLDOWN.value == "cooldown"
    assert TransferRoute.SOURCE_STREAM.value == "source_stream"


def test_model_enums_persist_declared_values() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        media = MediaItem(
            source_path="/media/file.mkv",
            source_file_id="file-1",
            size=123,
            fingerprint="fp-1",
            openlist_path="/open/file.mkv",
        )
        session.add_all([user, media])
        session.flush()

        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=user.id,
                drive_type="115",
                target_path="/target/file.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.add(
            PlaybackRecord(
                user_id=user.id,
                media_id=media.id,
                route=TransferRoute.SOURCE_STREAM,
                success=True,
                latency_ms=10,
            )
        )
        session.commit()

    with engine.connect() as connection:
        pool_status = connection.execute(text("SELECT status FROM pool_objects")).scalar_one()
        playback_route = connection.execute(text("SELECT route FROM playback_records")).scalar_one()

    assert pool_status == "ready"
    assert playback_route == "source_stream"


def test_alembic_upgrade_head_runs_from_repo_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "task3-alembic.db"
    env = os.environ.copy()
    env["GATEWAY_DATABASE_URL"] = f"sqlite:///{db_path}"

    result = subprocess.run(
        ["./.venv/bin/alembic", "upgrade", "head"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        pool_object_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info('pool_objects')").fetchall()
        }

    assert tables >= {
        "audit_logs",
        "media_items",
        "playback_records",
        "pool_objects",
        "transfer_jobs",
        "user_drive_accounts",
        "users",
    }
    assert pool_object_columns >= {
        "status",
        "last_verified_at",
        "last_success_at",
        "last_failure_at",
        "failure_count",
        "cooldown_until",
    }
