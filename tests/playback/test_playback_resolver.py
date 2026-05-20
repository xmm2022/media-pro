from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
    SourceObjectRef,
)
from gateway.models import (
    Base,
    MediaItem,
    PlaybackRecord,
    PoolObject,
    PoolObjectStatus,
    TransferJob,
    TransferRoute,
    User,
    UserDriveAccount,
)
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver
from gateway.security import CookieCipher


class StubOpenListClient:
    def __init__(self, stream_urls: dict[str, str]) -> None:
        self.stream_urls = stream_urls
        self.calls: list[str] = []

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        self.calls.append(source_path)
        return StreamInfo(
            raw_url=self.stream_urls[source_path],
            content_length=2048,
            accepts_ranges=True,
        )


class StubRapidCopyClient:
    def __init__(
        self,
        *,
        pool_results: list[RapidCopyResult] | None = None,
        source_results: list[RapidCopyResult] | None = None,
    ) -> None:
        self.pool_results = pool_results or []
        self.source_results = source_results or []
        self.pool_calls: list[PoolCopyRequest] = []
        self.source_calls: list[SourceCopyRequest] = []

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        self.pool_calls.append(request)
        return self.pool_results.pop(0)

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        self.source_calls.append(request)
        return self.source_results.pop(0)


class StubSourceCopy115Client:
    def __init__(self, results: list[RapidCopyResult] | None = None) -> None:
        self.results = results or []
        self.calls: list[SourceCopyRequest] = []

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        self.calls.append(request)
        return self.results.pop(0)


class StubPoolCopy115Client:
    def __init__(self, results: list[RapidCopyResult] | None = None) -> None:
        self.results = results or []
        self.calls: list[PoolCopyRequest] = []

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        self.calls.append(request)
        return self.results.pop(0)


class StubDrive115StreamClient:
    def __init__(
        self,
        *,
        results: list[StreamInfo] | None = None,
        errors: list[BaseException] | None = None,
    ) -> None:
        self.results = results or []
        self.errors = errors or []
        self.calls: list[tuple[str, str]] = []

    async def get_stream_info(self, target_cookie: str, target_path: str) -> StreamInfo:
        self.calls.append((target_cookie, target_path))
        if self.errors:
            raise self.errors.pop(0)
        return self.results.pop(0)


def insert_user_with_drive(
    session: Session,
    *,
    username: str,
    cookie_cipher: CookieCipher,
    root_dir: str,
    share_pool_enabled: bool = False,
    enabled: bool = True,
) -> User:
    user = User(username=username, status="active")
    session.add(user)
    session.flush()
    session.add(
        UserDriveAccount(
            user_id=user.id,
            drive_type="115",
            cookie_encrypted=cookie_cipher.encrypt(f"UID={username}"),
            root_dir=root_dir,
            share_pool_enabled=share_pool_enabled,
            enabled=enabled,
            health_status="healthy",
        )
    )
    session.flush()
    return user


@pytest.mark.asyncio
async def test_playback_resolver_prefers_self_hit_and_persists_record(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'self-hit.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=user.id,
                drive_type="115",
                target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=StubRapidCopyClient(),
            drive_stream_client=StubDrive115StreamClient(
                results=[
                    StreamInfo(
                        raw_url="https://115.local/alice/movie.mkv",
                        content_length=2048,
                        accepts_ranges=True,
                        request_headers={"user-agent": ""},
                    )
                ]
            ),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=user.id, media_id=media.id)
        routes = session.scalars(select(PlaybackRecord.route)).all()

    assert result.route == "self"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert result.stream_headers == {"user-agent": ""}
    assert routes == [TransferRoute.SELF]


@pytest.mark.asyncio
async def test_playback_resolver_skips_self_pool_when_target_drive_is_disabled(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'self-disabled-drive.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
            enabled=False,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=user.id,
                drive_type="115",
                target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient(
                {
                    "/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv",
                    "/EmbyCache/alice/Movies/Movie.2024.mkv": "https://openlist.local/self-cache.mkv",
                }
            ),
            rapid_copy_client=StubRapidCopyClient(),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=user.id, media_id=media.id)
        routes = session.scalars(select(PlaybackRecord.route)).all()

    assert result.route == "source_stream"
    assert result.stream_url == "https://openlist.local/source.mkv"
    assert routes == [TransferRoute.SOURCE_STREAM]


@pytest.mark.asyncio
async def test_playback_resolver_uses_pool_copy_and_updates_target_pool(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pool-copy.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        donor_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=donor_user.id,
                drive_type="115",
                target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            pool_results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ],
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient(
                {
                    "/EmbyCache/alice/Movies/Movie.2024.mkv": "https://115.local/alice/movie.mkv",
                }
            ),
            rapid_copy_client=rapid_copy_client,
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        target_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == target_user.id,
            )
        )
        transfer_jobs = session.scalars(select(TransferJob)).all()

    assert result.route == "pool"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert rapid_copy_client.pool_calls == [
        PoolCopyRequest(
            donor_cookie="UID=bob",
            target_cookie="UID=alice",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert rapid_copy_client.source_calls == []
    assert target_pool is not None
    assert target_pool.target_path == "/EmbyCache/alice/Movies/Movie.2024.mkv"
    assert transfer_jobs[0].route_stage == "try_pool"
    assert transfer_jobs[0].status == "success"


@pytest.mark.asyncio
async def test_playback_resolver_prefers_native_pool_copy_client_when_available(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'native-pool-copy.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        donor_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=donor_user.id,
                drive_type="115",
                target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        pool_copy_client = StubPoolCopy115Client(
            results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ]
        )
        rapid_copy_client = StubRapidCopyClient(
            pool_results=[RapidCopyResult(ok=False, error_code="should_not_run")]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=rapid_copy_client,
            pool_copy_client=pool_copy_client,
            drive_stream_client=StubDrive115StreamClient(
                results=[
                    StreamInfo(
                        raw_url="https://115.local/alice/movie.mkv",
                        content_length=2048,
                        accepts_ranges=True,
                    )
                ]
            ),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)

    assert result.route == "pool"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert pool_copy_client.calls == [
        PoolCopyRequest(
            donor_cookie="UID=bob",
            target_cookie="UID=alice",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert rapid_copy_client.pool_calls == []


@pytest.mark.asyncio
async def test_playback_resolver_uses_source_copy_after_pool_miss(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'source-copy.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            source_results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ],
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient(
                {
                    "/EmbyCache/alice/Movies/Movie.2024.mkv": "https://115.local/alice/movie.mkv",
                }
            ),
            rapid_copy_client=rapid_copy_client,
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        transfer_jobs = session.scalars(select(TransferJob)).all()

    assert result.route == "source_copy"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert rapid_copy_client.pool_calls == []
    assert rapid_copy_client.source_calls == [
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(
                openlist_path="/Movies/Movie.2024.mkv",
                source_path="/Movies/Movie.2024.mkv",
                source_file_id="gd-1",
                fingerprint="2048:movie.2024:mkv",
            ),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert transfer_jobs[0].route_stage == "try_source_copy"
    assert transfer_jobs[0].status == "success"


@pytest.mark.asyncio
async def test_playback_resolver_falls_back_to_source_stream_when_copy_paths_fail(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'source-stream.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        donor_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=donor_user.id,
                drive_type="115",
                target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            pool_results=[RapidCopyResult(ok=False, error_code="rapid_copy_unsupported")],
            source_results=[RapidCopyResult(ok=False, error_code="rapid_copy_unsupported")],
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient(
                {
                    "/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv",
                }
            ),
            rapid_copy_client=rapid_copy_client,
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        transfer_jobs = session.scalars(select(TransferJob).order_by(TransferJob.route_stage)).all()
        routes = session.scalars(select(PlaybackRecord.route)).all()

    assert result.route == "source_stream"
    assert result.stream_url == "https://openlist.local/source.mkv"
    assert [job.route_stage for job in transfer_jobs] == ["try_pool", "try_source_copy"]
    assert [job.status for job in transfer_jobs] == ["failed", "failed"]
    assert routes == [TransferRoute.SOURCE_STREAM]


@pytest.mark.asyncio
async def test_playback_resolver_prefers_native_source_copy_client_when_available(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'native-source-copy.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()

        source_copy_client = StubSourceCopy115Client(
            results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            source_copy_client=source_copy_client,
            drive_stream_client=StubDrive115StreamClient(
                results=[
                    StreamInfo(
                        raw_url="https://115.local/alice/movie.mkv",
                        content_length=2048,
                        accepts_ranges=True,
                        request_headers={"user-agent": ""},
                    )
                ]
            ),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)

    assert result.route == "source_copy"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert result.stream_headers == {"user-agent": ""}
    assert source_copy_client.calls == [
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(
                openlist_path="/Movies/Movie.2024.mkv",
                source_path="/Movies/Movie.2024.mkv",
                source_file_id="gd-1",
                fingerprint="2048:movie.2024:mkv",
            ),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]


@pytest.mark.asyncio
async def test_playback_resolver_falls_back_to_source_stream_when_native_115_stream_fails(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'native-stream-fallback.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()

        source_copy_client = StubSourceCopy115Client(
            results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            source_copy_client=source_copy_client,
            drive_stream_client=StubDrive115StreamClient(errors=[FileNotFoundError("missing file")]),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        transfer_jobs = session.scalars(select(TransferJob)).all()
        routes = session.scalars(select(PlaybackRecord.route)).all()

    assert result.route == "source_stream"
    assert result.stream_url == "https://openlist.local/source.mkv"
    assert result.stream_headers is None
    assert transfer_jobs[0].route_stage == "try_source_copy"
    assert transfer_jobs[0].status == "success"
    assert routes == [TransferRoute.SOURCE_STREAM]


@pytest.mark.asyncio
async def test_playback_resolver_repairs_unstreamable_self_pool_via_source_copy(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'self-repair.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=user.id,
                drive_type="115",
                target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        source_copy_client = StubSourceCopy115Client(
            results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            source_copy_client=source_copy_client,
            drive_stream_client=StubDrive115StreamClient(
                errors=[FileNotFoundError("missing self object")],
                results=[
                    StreamInfo(
                        raw_url="https://115.local/alice/repaired.mkv",
                        content_length=2048,
                        accepts_ranges=True,
                    )
                ],
            ),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=user.id, media_id=media.id)
        target_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == user.id,
            )
        )

    assert result.route == "source_copy"
    assert result.stream_url == "https://115.local/alice/repaired.mkv"
    assert source_copy_client.calls == [
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(
                openlist_path="/Movies/Movie.2024.mkv",
                source_path="/Movies/Movie.2024.mkv",
                source_file_id="gd-1",
                fingerprint="2048:movie.2024:mkv",
            ),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert target_pool is not None
    assert target_pool.status == PoolObjectStatus.READY
    assert target_pool.failure_count == 0
    assert target_pool.cooldown_until is None


@pytest.mark.asyncio
async def test_playback_resolver_marks_self_pool_stale_when_repair_fails(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'self-stale.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=user.id,
                drive_type="115",
                target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            source_results=[RapidCopyResult(ok=False, error_code="quick_upload_failed")]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=rapid_copy_client,
            drive_stream_client=StubDrive115StreamClient(errors=[FileNotFoundError("missing self object")]),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=user.id, media_id=media.id)
        self_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == user.id,
            )
        )

    assert result.route == "source_stream"
    assert result.stream_url == "https://openlist.local/source.mkv"
    assert rapid_copy_client.source_calls == [
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(
                openlist_path="/Movies/Movie.2024.mkv",
                source_path="/Movies/Movie.2024.mkv",
                source_file_id="gd-1",
                fingerprint="2048:movie.2024:mkv",
            ),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert self_pool is not None
    assert self_pool.status == PoolObjectStatus.STALE
    assert self_pool.failure_count == 1
    assert self_pool.last_failure_at is not None


@pytest.mark.asyncio
async def test_playback_resolver_marks_donor_stale_when_pool_copy_reports_missing_donor_file(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'donor-stale.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        donor_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=donor_user.id,
                drive_type="115",
                target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            pool_results=[RapidCopyResult(ok=False, error_code="missing_donor_file")],
            source_results=[RapidCopyResult(ok=False, error_code="quick_upload_failed")],
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=rapid_copy_client,
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        donor_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == donor_user.id,
            )
        )

    assert result.route == "source_stream"
    assert result.stream_url == "https://openlist.local/source.mkv"
    assert donor_pool is not None
    assert donor_pool.status == PoolObjectStatus.STALE
    assert donor_pool.failure_count == 1
    assert donor_pool.last_failure_at is not None


@pytest.mark.asyncio
async def test_playback_resolver_skips_active_cooldown_donor_and_uses_next_ready_candidate(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'cooldown-skip.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)
    future_cooldown = datetime.now(timezone.utc) + timedelta(minutes=5)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        cooldown_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        ready_user = insert_user_with_drive(
            session,
            username="carol",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/carol",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add_all(
            [
                PoolObject(
                    media_id=media.id,
                    owner_user_id=cooldown_user.id,
                    drive_type="115",
                    target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.COOLDOWN,
                    failure_count=2,
                    cooldown_until=future_cooldown,
                ),
                PoolObject(
                    media_id=media.id,
                    owner_user_id=ready_user.id,
                    drive_type="115",
                    target_path="/EmbyCache/carol/Movies/Movie.2024.mkv",
                    status=PoolObjectStatus.READY,
                ),
            ]
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            pool_results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=rapid_copy_client,
            drive_stream_client=StubDrive115StreamClient(
                results=[
                    StreamInfo(
                        raw_url="https://115.local/alice/movie.mkv",
                        content_length=2048,
                        accepts_ranges=True,
                    )
                ]
            ),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        cooldown_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == cooldown_user.id,
            )
        )

    assert result.route == "pool"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert rapid_copy_client.pool_calls == [
        PoolCopyRequest(
            donor_cookie="UID=carol",
            target_cookie="UID=alice",
            source_path="/EmbyCache/carol/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert cooldown_pool is not None
    assert cooldown_pool.status == PoolObjectStatus.COOLDOWN
    assert cooldown_pool.cooldown_until is not None
    assert cooldown_pool.cooldown_until.replace(tzinfo=timezone.utc) == future_cooldown


@pytest.mark.asyncio
async def test_playback_resolver_recovers_expired_cooldown_before_selecting_donor(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'cooldown-recover.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)
    expired_cooldown = datetime.now(timezone.utc) - timedelta(minutes=1)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        donor_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=donor_user.id,
                drive_type="115",
                target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.COOLDOWN,
                failure_count=2,
                cooldown_until=expired_cooldown,
            )
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            pool_results=[
                RapidCopyResult(
                    ok=True,
                    error_code=None,
                    target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
                )
            ]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=rapid_copy_client,
            drive_stream_client=StubDrive115StreamClient(
                results=[
                    StreamInfo(
                        raw_url="https://115.local/alice/movie.mkv",
                        content_length=2048,
                        accepts_ranges=True,
                    )
                ]
            ),
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        donor_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == donor_user.id,
            )
        )

    assert result.route == "pool"
    assert result.stream_url == "https://115.local/alice/movie.mkv"
    assert rapid_copy_client.pool_calls == [
        PoolCopyRequest(
            donor_cookie="UID=bob",
            target_cookie="UID=alice",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert donor_pool is not None
    assert donor_pool.status == PoolObjectStatus.READY
    assert donor_pool.failure_count == 0
    assert donor_pool.cooldown_until is None


@pytest.mark.asyncio
async def test_playback_resolver_skips_source_copy_when_pool_copy_hits_target_blocking_error(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'target-blocking.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    cipher = CookieCipher("x" * 32)

    with Session(engine) as session:
        target_user = insert_user_with_drive(
            session,
            username="alice",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/alice",
        )
        donor_user = insert_user_with_drive(
            session,
            username="bob",
            cookie_cipher=cipher,
            root_dir="/EmbyCache/bob",
            share_pool_enabled=True,
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.flush()
        session.add(
            PoolObject(
                media_id=media.id,
                owner_user_id=donor_user.id,
                drive_type="115",
                target_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
                status=PoolObjectStatus.READY,
            )
        )
        session.commit()

        rapid_copy_client = StubRapidCopyClient(
            pool_results=[RapidCopyResult(ok=False, error_code="file_too_large_for_account")]
        )
        resolver = PlaybackResolver(
            PlaybackService(),
            StubOpenListClient({"/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv"}),
            rapid_copy_client=rapid_copy_client,
            cookie_cipher=cipher,
        )
        result = await resolver.resolve(session, user_id=target_user.id, media_id=media.id)
        donor_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media.id,
                PoolObject.owner_user_id == donor_user.id,
            )
        )
        transfer_jobs = session.scalars(select(TransferJob).order_by(TransferJob.route_stage)).all()

    assert result.route == "source_stream"
    assert result.stream_url == "https://openlist.local/source.mkv"
    assert rapid_copy_client.pool_calls == [
        PoolCopyRequest(
            donor_cookie="UID=bob",
            target_cookie="UID=alice",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    ]
    assert rapid_copy_client.source_calls == []
    assert donor_pool is not None
    assert donor_pool.status == PoolObjectStatus.READY
    assert [job.route_stage for job in transfer_jobs] == ["try_pool"]
    assert transfer_jobs[0].error_code == "file_too_large_for_account"
