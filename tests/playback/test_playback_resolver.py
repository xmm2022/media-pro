from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.models import Base, MediaItem, PlaybackRecord, PoolObject, TransferRoute, User, UserDriveAccount
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
