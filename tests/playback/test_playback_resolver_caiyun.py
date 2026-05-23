from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
)
from gateway.integrations.rapid_copy_strategy import ProbeResult, RapidCopyStrategyRegistry
from gateway.models import Base, MediaItem, PoolObject, User, UserDriveAccount
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver


class _StubCaiyunStrategy:
    drive_type = "caiyun"

    def __init__(self) -> None:
        self.source_calls: list[SourceCopyRequest] = []
        self.pool_calls: list[PoolCopyRequest] = []

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        self.source_calls.append(request)
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        self.pool_calls.append(request)
        raise NotImplementedError

    async def probe(self, drive) -> ProbeResult:
        return ProbeResult(ok=True)

    async def aclose(self) -> None:
        return None


class _StubOpenListClient:
    def __init__(self) -> None:
        self.stream_calls: list[str] = []

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        self.stream_calls.append(source_path)
        return StreamInfo(
            raw_url=f"http://openlist.local/raw{source_path}",
            content_length=1024,
            accepts_ranges=True,
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_caiyun_source_copy_routes_through_strategy_and_writes_pool_object(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'caiyun-resolver.db'}", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="alice")
        session.add(user)
        session.flush()
        drive = UserDriveAccount(
            user_id=user.id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/caiyun-alice",
            root_dir="/EmbyCache",
            enabled=True,
            share_pool_enabled=False,
            health_status="healthy",
            last_checked_at=datetime.now(timezone.utc),
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-movie-id",
            size=1024,
            fingerprint="fp-movie",
            openlist_path="/gd/Movies/Movie.2024.mkv",
        )
        session.add_all([drive, media])
        session.commit()
        user_id = user.id
        media_id = media.id

    registry = RapidCopyStrategyRegistry()
    strategy = _StubCaiyunStrategy()
    registry.register(strategy)
    openlist_client = _StubOpenListClient()
    resolver = PlaybackResolver(
        PlaybackService(total_budget_ms=2000),
        openlist_client,
        strategy_registry=registry,
        cookie_cipher=None,
    )

    with Session(engine) as session:
        decision = await resolver.resolve(session, user_id=user_id, media_id=media_id)
        pool_object = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id == user_id,
            )
        )

    assert decision.route == "source_copy"
    assert decision.stream_url == (
        "http://openlist.local/raw/caiyun-alice/EmbyCache/Movies/Movie.2024.mkv"
    )
    assert len(strategy.source_calls) == 1
    call = strategy.source_calls[0]
    assert call.target_cookie == ""
    assert call.target_path == "/caiyun-alice/EmbyCache/Movies/Movie.2024.mkv"
    assert call.source.openlist_path == "/gd/Movies/Movie.2024.mkv"
    assert call.source.source_path == "/Movies/Movie.2024.mkv"
    assert call.source.source_file_id == "gd-movie-id"
    assert call.source.fingerprint == "fp-movie"
    assert openlist_client.stream_calls == ["/caiyun-alice/EmbyCache/Movies/Movie.2024.mkv"]
    assert pool_object is not None
    assert pool_object.drive_type == "caiyun"
    assert pool_object.target_path == "/caiyun-alice/EmbyCache/Movies/Movie.2024.mkv"
