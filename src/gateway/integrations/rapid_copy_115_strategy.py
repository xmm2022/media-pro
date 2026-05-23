"""115-specific rapid copy strategy wrapper."""

from __future__ import annotations

from typing import Protocol

from gateway.integrations.drive115_health_client import Drive115HealthClient, DriveHealthResult
from gateway.integrations.pool_copy_115_client import PoolCopy115Client
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
)
from gateway.integrations.rapid_copy_strategy import ProbeResult
from gateway.integrations.source_copy_115_client import SourceCopy115Client
from gateway.models import UserDriveAccount


class _CookieCipher(Protocol):
    def decrypt(self, value: str | None) -> str: ...


class _PoolClient(Protocol):
    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult: ...

    async def aclose(self) -> None: ...


class _SourceClient(Protocol):
    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult: ...

    async def aclose(self) -> None: ...


class _HealthClient(Protocol):
    async def probe(self, cookie: str, root_dir: str) -> DriveHealthResult: ...


class Rapid115Strategy:
    drive_type = "115"

    def __init__(
        self,
        *,
        pool_copy_client: _PoolClient | None = None,
        source_copy_client: _SourceClient | None = None,
        health_client: _HealthClient | None = None,
        cookie_cipher: _CookieCipher | None = None,
    ) -> None:
        self._pool_copy_client = pool_copy_client or PoolCopy115Client()
        if source_copy_client is None:
            raise ValueError("Rapid115Strategy requires a source_copy_client")
        self._source_copy_client = source_copy_client
        self._health_client = health_client or Drive115HealthClient()
        self._cookie_cipher = cookie_cipher

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        return await self._pool_copy_client.copy_from_pool(request)

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        return await self._source_copy_client.copy_from_source(request)

    async def probe(self, drive: UserDriveAccount) -> ProbeResult:
        cookie = self._decrypt(drive.cookie_encrypted)
        result = await self._health_client.probe(cookie, drive.root_dir)
        return ProbeResult(ok=result.ok, error_code=result.error_code, detail=result.detail)

    async def aclose(self) -> None:
        await self._pool_copy_client.aclose()
        await self._source_copy_client.aclose()

    def _decrypt(self, value: str | None) -> str:
        if self._cookie_cipher is None:
            raise ValueError("Rapid115Strategy.probe requires cookie_cipher")
        return self._cookie_cipher.decrypt(value)
