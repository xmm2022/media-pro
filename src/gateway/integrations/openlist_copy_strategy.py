"""OpenList-backed rapid copy strategy."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol

from gateway.integrations.openlist_admin_client import CopyResult, FsItem, OpenListAdminError
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
)
from gateway.integrations.rapid_copy_strategy import ProbeResult
from gateway.models import UserDriveAccount


class _AdminClient(Protocol):
    async def fs_copy(self, *, src_dir: str, dst_dir: str, names: list[str]) -> CopyResult: ...

    async def fs_list(self, mount_path: str) -> list[FsItem]: ...

    async def aclose(self) -> None: ...


class OpenListCopyStrategy:
    def __init__(self, *, admin_client: _AdminClient, drive_type: str) -> None:
        self._admin_client = admin_client
        self.drive_type = drive_type

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        source_path = PurePosixPath(request.source.preferred_path())
        target_path = PurePosixPath(request.target_path)
        try:
            result = await self._admin_client.fs_copy(
                src_dir=str(source_path.parent),
                dst_dir=str(target_path.parent),
                names=[source_path.name],
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            return RapidCopyResult(
                ok=False,
                error_code="openlist_copy_failed",
                detail=str(exc),
            )

        if not result.ok:
            return RapidCopyResult(
                ok=False,
                error_code="openlist_copy_failed",
                detail=result.error,
            )
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        raise NotImplementedError(
            "pool copy is not supported for OpenList-backed drivers in MVP"
        )

    async def probe(self, drive: UserDriveAccount) -> ProbeResult:
        mount_path = drive.openlist_mount_path
        if not mount_path:
            return ProbeResult(
                ok=False,
                error_code="mount_missing",
                detail="drive has no mount_path",
            )
        try:
            await self._admin_client.fs_list(mount_path)
        except OpenListAdminError as exc:
            if exc.status_code == 404:
                return ProbeResult(ok=False, error_code="mount_missing", detail=exc.message)
            if exc.status_code in {401, 403}:
                return ProbeResult(ok=False, error_code="invalid_token", detail=exc.message)
            return ProbeResult(
                ok=False,
                error_code="openlist_http_error",
                detail=exc.message,
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            return ProbeResult(
                ok=False,
                error_code="openlist_admin_failed",
                detail=str(exc),
            )
        return ProbeResult(ok=True)

    async def aclose(self) -> None:
        await self._admin_client.aclose()
