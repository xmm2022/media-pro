from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
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
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver


class StubOpenListClient:
    async def get_stream_info(self, source_path: str) -> StreamInfo:
        assert source_path == "/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://drive.local/Movie.2024.mkv",
            content_length=2048,
            accepts_ranges=True,
        )


@pytest.mark.asyncio
async def test_playback_resolver_returns_real_source_stream_and_persists_record(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, media])
        session.commit()

        result = await PlaybackResolver(PlaybackService(), StubOpenListClient()).resolve(
            session,
            user_id=user.id,
            media_id=media.id,
        )
        routes = session.scalars(select(PlaybackRecord.route)).all()

    assert result.route == "source_stream"
    assert result.stream_url == "https://drive.local/Movie.2024.mkv"
    assert routes == [TransferRoute.SOURCE_STREAM]


@pytest.mark.asyncio
async def test_playback_resolver_ignores_local_paths_and_returns_openlist_stream(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-paths.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        donor = User(username="bob")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, donor, media])
        session.commit()

        session.add_all(
            [
                PoolObject(
                    media_id=media.id,
                    owner_user_id=user.id,
                    drive_type="115",
                    target_path="/EmbyCache/alice/Movie.2024.mkv",
                ),
                PoolObject(
                    media_id=media.id,
                    owner_user_id=donor.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movie.2024.mkv",
                ),
                UserDriveAccount(
                    user_id=user.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/alice",
                    enabled=True,
                ),
                UserDriveAccount(
                    user_id=donor.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/bob",
                    enabled=True,
                    share_pool_enabled=True,
                ),
            ]
        )
        session.commit()

        result = await PlaybackResolver(PlaybackService(), StubOpenListClient()).resolve(
            session,
            user_id=user.id,
            media_id=media.id,
        )

    assert result.route == "source_stream"
    assert result.stream_url == "https://drive.local/Movie.2024.mkv"


@pytest.mark.asyncio
async def test_playback_resolver_selects_first_share_enabled_ready_donor_with_real_url(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-donors.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        donor_one = User(username="bob")
        donor_two = User(username="carol")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, donor_one, donor_two, media])
        session.commit()

        session.add_all(
            [
                PoolObject(
                    media_id=media.id,
                    owner_user_id=donor_one.id,
                    drive_type="115",
                    target_path="https://target.local/bob.mkv",
                    status=PoolObjectStatus.READY,
                ),
                PoolObject(
                    media_id=media.id,
                    owner_user_id=donor_two.id,
                    drive_type="115",
                    target_path="https://target.local/carol.mkv",
                    status=PoolObjectStatus.READY,
                ),
                UserDriveAccount(
                    user_id=donor_one.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/bob",
                    enabled=True,
                    share_pool_enabled=False,
                ),
                UserDriveAccount(
                    user_id=donor_two.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/carol",
                    enabled=True,
                    share_pool_enabled=True,
                ),
            ]
        )
        session.commit()

        result = await PlaybackResolver(PlaybackService(), StubOpenListClient()).resolve(
            session,
            user_id=user.id,
            media_id=media.id,
        )

    assert result.route == "pool"
    assert result.stream_url == "https://target.local/carol.mkv"


@pytest.mark.asyncio
async def test_playback_resolver_ignores_non_ready_self_and_donor_candidates(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-status.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        donor = User(username="bob")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, donor, media])
        session.commit()

        session.add_all(
            [
                PoolObject(
                    media_id=media.id,
                    owner_user_id=user.id,
                    drive_type="115",
                    target_path="https://target.local/self.mkv",
                    status=PoolObjectStatus.SUSPECT,
                ),
                PoolObject(
                    media_id=media.id,
                    owner_user_id=donor.id,
                    drive_type="115",
                    target_path="https://target.local/donor.mkv",
                    status=PoolObjectStatus.COOLDOWN,
                ),
                UserDriveAccount(
                    user_id=donor.id,
                    cookie_encrypted="secret",
                    root_dir="/EmbyCache/bob",
                    enabled=True,
                    share_pool_enabled=True,
                ),
            ]
        )
        session.commit()

        result = await PlaybackResolver(PlaybackService(), StubOpenListClient()).resolve(
            session,
            user_id=user.id,
            media_id=media.id,
        )

    assert result.route == "source_stream"
    assert result.stream_url == "https://drive.local/Movie.2024.mkv"


@pytest.mark.asyncio
async def test_playback_resolver_rolls_back_when_persisting_record_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-rollback.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, media])
        session.commit()

        rollback_called = False

        def fail_commit() -> None:
            raise RuntimeError("commit failed")

        def track_rollback() -> None:
            nonlocal rollback_called
            rollback_called = True

        monkeypatch.setattr(session, "commit", fail_commit)
        monkeypatch.setattr(session, "rollback", track_rollback)

        with pytest.raises(RuntimeError, match="commit failed"):
            await PlaybackResolver(PlaybackService(), StubOpenListClient()).resolve(
                session,
                user_id=user.id,
                media_id=media.id,
            )

    assert rollback_called is True
