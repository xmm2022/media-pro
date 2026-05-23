from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from gateway.models import (
    OPENLIST_BACKED_DRIVE_TYPES,
    SUPPORTED_DRIVE_TYPES,
    UserDriveAccount,
)


def _alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_0003_adds_openlist_mount_path_and_makes_cookie_encrypted_nullable(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "caiyun-migration.db"
    database_url = f"sqlite:///{database_path}"

    config = _alembic_config(database_url)
    command.upgrade(config, "0003_caiyun_drive_fields")

    engine = create_engine(database_url, future=True)
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("user_drive_accounts")
    }
    assert "openlist_mount_path" in columns
    assert columns["openlist_mount_path"]["nullable"] is True
    assert columns["cookie_encrypted"]["nullable"] is True

    command.downgrade(config, "0002_pool_object_health_state")
    columns_after = {
        column["name"]: column
        for column in inspect(engine).get_columns("user_drive_accounts")
    }
    assert "openlist_mount_path" not in columns_after
    assert columns_after["cookie_encrypted"]["nullable"] is False


def test_user_drive_account_model_exposes_caiyun_fields() -> None:
    assert SUPPORTED_DRIVE_TYPES == frozenset({"115", "caiyun"})
    assert OPENLIST_BACKED_DRIVE_TYPES == frozenset({"caiyun"})

    columns = UserDriveAccount.__table__.columns
    assert columns["cookie_encrypted"].nullable is True
    assert columns["openlist_mount_path"].nullable is True
