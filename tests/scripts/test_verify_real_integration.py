from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.config import Settings
from gateway.integrations.openlist_client import CatalogRow, StreamInfo
from gateway.integrations.rapid_copy_client import RapidCopyResult
from gateway.models import (
    Base,
    MediaItem,
    PlaybackRecord,
    PoolObject,
    PoolObjectStatus,
    TransferRoute,
    User,
    UserDriveAccount,
)
from gateway.real_integration import run_real_integration_probe
from gateway.security import CookieCipher


class StubOpenListClient:
    async def get_stream_info(self, source_path: str) -> StreamInfo:
        assert source_path == "/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://drive.local/Movie.2024.mkv",
            content_length=2048,
            accepts_ranges=True,
        )

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        assert root_path == "/Movies"
        return [
            CatalogRow(
                path="/Movies/Movie.2024.mkv",
                size=2048,
                file_id="gd-1",
                mtime="2026-05-17T00:00:00Z",
            )
        ]

    async def aclose(self) -> None:
        return None


class StubRapidCopyClient:
    async def copy(
        self,
        donor_cookie: str,
        target_cookie: str,
        source_path: str,
        target_path: str,
    ) -> RapidCopyResult:
        assert donor_cookie == "UID=donor"
        assert target_cookie == "UID=target"
        assert source_path == "/Movies/Movie.2024.mkv"
        assert target_path == "/EmbyCache/probe/Movie.2024.mkv"
        return RapidCopyResult(ok=True, error_code=None, target_path=target_path, detail=None)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_real_integration_probe_returns_sync_playback_rapid_copy_and_stats(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'real-integration.db'}", future=True)
    Base.metadata.create_all(engine)
    app_settings = Settings(
        _env_file=None,
        cookie_secret="x" * 32,
        catalog_root_path="/Movies",
        openlist_probe_path="/Movies/Movie.2024.mkv",
        rapid_copy_donor_cookie="UID=donor",
        rapid_copy_target_cookie="UID=target",
        rapid_copy_source_path="/Movies/Movie.2024.mkv",
        rapid_copy_target_path="/EmbyCache/probe/Movie.2024.mkv",
    )

    with Session(engine) as session:
        summary = await run_real_integration_probe(
            session=session,
            app_settings=app_settings,
            openlist_client=StubOpenListClient(),
            rapid_copy_client=StubRapidCopyClient(),
        )
        probe_user = session.scalar(select(User).where(User.username == "probe-user"))
        drive = session.scalar(
            select(UserDriveAccount).where(UserDriveAccount.user_id == probe_user.id)
        )
        routes = session.scalars(select(PlaybackRecord.route)).all()

    assert summary["sync"] == {"created": 1, "updated": 0}
    assert summary["playback"] == {
        "route": "source_stream",
        "stream_url": "https://drive.local/Movie.2024.mkv",
    }
    assert summary["rapid_copy"] == {"ok": True, "error_code": None}
    assert summary["stats"] == {
        "self": 0,
        "pool": 0,
        "source_copy": 0,
        "source_stream": 1,
    }
    assert probe_user is not None
    assert drive is not None
    assert drive.root_dir == "/EmbyCache/probe"
    assert CookieCipher(app_settings.cookie_secret).decrypt(drive.cookie_encrypted) == "UID=target"
    assert routes == [TransferRoute.SOURCE_STREAM]


def test_readme_mentions_real_integration_probe_steps() -> None:
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text()

    assert "uv run python scripts/validate_openlist_stream.py" in readme
    assert "uv run python scripts/validate_rapid_copy.py" in readme
    assert "uv run python scripts/verify_real_integration.py" in readme


@pytest.mark.asyncio
async def test_run_real_integration_probe_isolates_playback_from_dirty_real_media_pool_state(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'real-integration-dirty.db'}", future=True)
    Base.metadata.create_all(engine)
    app_settings = Settings(
        _env_file=None,
        cookie_secret="x" * 32,
        catalog_root_path="/Movies",
        openlist_probe_path="/Movies/Movie.2024.mkv",
        rapid_copy_donor_cookie="UID=donor",
        rapid_copy_target_cookie="UID=target",
        rapid_copy_source_path="/Movies/Movie.2024.mkv",
        rapid_copy_target_path="/EmbyCache/probe/Movie.2024.mkv",
    )

    with Session(engine) as session:
        existing_user = User(username="probe-user", status="active")
        donor_user = User(username="dirty-donor", status="active")
        real_media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-existing",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([existing_user, donor_user, real_media])
        session.commit()

        session.add_all(
            [
                UserDriveAccount(
                    user_id=existing_user.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/probe",
                    enabled=True,
                    share_pool_enabled=True,
                ),
                UserDriveAccount(
                    user_id=donor_user.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/donor",
                    enabled=True,
                    share_pool_enabled=True,
                ),
                PoolObject(
                    media_id=real_media.id,
                    owner_user_id=existing_user.id,
                    drive_type="115",
                    target_path="https://target.local/self.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=real_media.id,
                    owner_user_id=donor_user.id,
                    drive_type="115",
                    target_path="https://target.local/donor.mkv",
                    status=PoolObjectStatus.READY,
                ),
            ]
        )
        session.commit()

        summary = await run_real_integration_probe(
            session=session,
            app_settings=app_settings,
            openlist_client=StubOpenListClient(),
            rapid_copy_client=StubRapidCopyClient(),
        )
        media_items = session.scalars(select(MediaItem).order_by(MediaItem.id)).all()
        routes = session.scalars(select(PlaybackRecord.route)).all()
        pool_objects = session.scalars(select(PoolObject).order_by(PoolObject.id)).all()

    assert summary["playback"] == {
        "route": "source_stream",
        "stream_url": "https://drive.local/Movie.2024.mkv",
    }
    assert len(media_items) == 2
    assert media_items[0].source_path == "/Movies/Movie.2024.mkv"
    assert media_items[1].source_path != "/Movies/Movie.2024.mkv"
    assert media_items[1].openlist_path == "/Movies/Movie.2024.mkv"
    assert routes[-1] == TransferRoute.SOURCE_STREAM
    assert len(pool_objects) == 2
    assert {pool.media_id for pool in pool_objects} == {real_media.id}


@pytest.mark.asyncio
async def test_run_real_integration_probe_rejects_placeholder_openlist_path_early(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'real-integration-placeholder.db'}", future=True)
    Base.metadata.create_all(engine)
    app_settings = Settings(
        _env_file=None,
        cookie_secret="x" * 32,
        catalog_root_path="/Movies",
        openlist_probe_path="/Movies/sample.mkv",
        rapid_copy_donor_cookie="UID=donor",
        rapid_copy_target_cookie="UID=target",
        rapid_copy_source_path="/Movies/Real.Movie.mkv",
        rapid_copy_target_path="/EmbyCache/probe/Real.Movie.mkv",
    )

    with Session(engine) as session:
        with pytest.raises(
            ValueError, match="GATEWAY_OPENLIST_PROBE_PATH must be set to a real media path"
        ):
            await run_real_integration_probe(
                session=session,
                app_settings=app_settings,
                openlist_client=StubOpenListClient(),
                rapid_copy_client=StubRapidCopyClient(),
            )
