"""Rapid copy strategy protocol and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
)
from gateway.models import UserDriveAccount


@dataclass(frozen=True, slots=True)
class ProbeResult:
    ok: bool
    error_code: str | None = None
    detail: str | None = None


class UnsupportedDriveType(LookupError):
    pass


@runtime_checkable
class RapidCopyStrategy(Protocol):
    drive_type: str

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult: ...

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult: ...

    async def probe(self, drive: UserDriveAccount) -> ProbeResult: ...

    async def aclose(self) -> None: ...


class RapidCopyStrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, RapidCopyStrategy] = {}

    def register(self, strategy: RapidCopyStrategy) -> None:
        self._strategies[strategy.drive_type] = strategy

    def get(self, drive_type: str) -> RapidCopyStrategy:
        if drive_type not in self._strategies:
            raise UnsupportedDriveType(f"no strategy registered for drive_type={drive_type}")
        return self._strategies[drive_type]

    def known_drive_types(self) -> list[str]:
        return list(self._strategies.keys())

    async def aclose(self) -> None:
        for strategy in self._strategies.values():
            await strategy.aclose()
