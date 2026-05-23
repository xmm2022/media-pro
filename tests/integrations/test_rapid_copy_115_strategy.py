from dataclasses import dataclass

import pytest

from gateway.integrations.rapid_copy_115_strategy import Rapid115Strategy
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
    SourceObjectRef,
)


@dataclass
class _RecordingDrive:
    drive_type: str = "115"
    cookie_encrypted: str = "encrypted"
    root_dir: str = "/EmbyCache/alice"


class _StubPoolClient:
    def __init__(self) -> None:
        self.calls: list[PoolCopyRequest] = []
        self.closed = False

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        self.calls.append(request)
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None:
        self.closed = True


class _StubSourceClient:
    def __init__(self) -> None:
        self.calls: list[SourceCopyRequest] = []
        self.closed = False

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        self.calls.append(request)
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None:
        self.closed = True


class _StubHealthClient:
    async def probe(self, cookie: str, root_dir: str):
        from gateway.integrations.drive115_health_client import DriveHealthResult

        return DriveHealthResult(ok=True, error_code=None)


@pytest.mark.asyncio
async def test_strategy_drive_type_is_115() -> None:
    strategy = Rapid115Strategy(
        pool_copy_client=_StubPoolClient(),
        source_copy_client=_StubSourceClient(),
        health_client=_StubHealthClient(),
    )

    assert strategy.drive_type == "115"


@pytest.mark.asyncio
async def test_copy_from_pool_delegates_to_pool_copy_client() -> None:
    pool_client = _StubPoolClient()
    strategy = Rapid115Strategy(
        pool_copy_client=pool_client,
        source_copy_client=_StubSourceClient(),
        health_client=_StubHealthClient(),
    )
    request = PoolCopyRequest(
        donor_cookie="donor",
        target_cookie="target",
        source_path="/Pool/movie.mkv",
        target_path="/EmbyCache/alice/Movies/movie.mkv",
    )

    result = await strategy.copy_from_pool(request)

    assert result.ok is True
    assert pool_client.calls == [request]


@pytest.mark.asyncio
async def test_copy_from_source_delegates_to_source_copy_client() -> None:
    source_client = _StubSourceClient()
    strategy = Rapid115Strategy(
        pool_copy_client=_StubPoolClient(),
        source_copy_client=source_client,
        health_client=_StubHealthClient(),
    )
    request = SourceCopyRequest(
        target_cookie="target",
        source=SourceObjectRef(openlist_path="/Movies/movie.mkv"),
        target_path="/EmbyCache/alice/Movies/movie.mkv",
    )

    result = await strategy.copy_from_source(request)

    assert result.ok is True
    assert source_client.calls == [request]


@pytest.mark.asyncio
async def test_probe_decrypts_cookie_and_calls_health_client() -> None:
    class _CapturingHealth:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def probe(self, cookie: str, root_dir: str):
            from gateway.integrations.drive115_health_client import DriveHealthResult

            self.calls.append((cookie, root_dir))
            return DriveHealthResult(ok=True, error_code=None)

    class _Cipher:
        def decrypt(self, value: str | None) -> str:
            assert value == "encrypted"
            return "UID=plain"

    health_client = _CapturingHealth()
    strategy = Rapid115Strategy(
        pool_copy_client=_StubPoolClient(),
        source_copy_client=_StubSourceClient(),
        health_client=health_client,
        cookie_cipher=_Cipher(),
    )

    result = await strategy.probe(_RecordingDrive())

    assert result.ok is True
    assert health_client.calls == [("UID=plain", "/EmbyCache/alice")]


@pytest.mark.asyncio
async def test_aclose_closes_wrapped_clients() -> None:
    pool_client = _StubPoolClient()
    source_client = _StubSourceClient()
    strategy = Rapid115Strategy(
        pool_copy_client=pool_client,
        source_copy_client=source_client,
        health_client=_StubHealthClient(),
    )

    await strategy.aclose()

    assert pool_client.closed is True
    assert source_client.closed is True
