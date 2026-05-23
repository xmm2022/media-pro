from dataclasses import dataclass

import pytest

from gateway.integrations.openlist_admin_client import CopyResult, FsItem, OpenListAdminError
from gateway.integrations.openlist_copy_strategy import OpenListCopyStrategy
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    SourceCopyRequest,
    SourceObjectRef,
)


@dataclass
class _Drive:
    drive_type: str = "caiyun"
    openlist_mount_path: str | None = "/caiyun-alice"
    root_dir: str = "/EmbyCache"
    cookie_encrypted: str | None = None


class _StubAdminClient:
    def __init__(self) -> None:
        self.copy_calls: list[tuple[str, str, list[str]]] = []
        self.list_calls: list[str] = []
        self.copy_responses: list[CopyResult] = []
        self.list_response: list[FsItem] = [FsItem(name="dummy", is_dir=False, size=1)]
        self.list_raises: Exception | None = None
        self.closed = False

    async def fs_copy(self, *, src_dir: str, dst_dir: str, names: list[str]) -> CopyResult:
        self.copy_calls.append((src_dir, dst_dir, names))
        if self.copy_responses:
            return self.copy_responses.pop(0)
        return CopyResult(ok=True, task_id="t-x")

    async def fs_list(self, mount_path: str) -> list[FsItem]:
        self.list_calls.append(mount_path)
        if self.list_raises is not None:
            raise self.list_raises
        return self.list_response

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_strategy_drive_type_is_caiyun() -> None:
    strategy = OpenListCopyStrategy(admin_client=_StubAdminClient(), drive_type="caiyun")

    assert strategy.drive_type == "caiyun"


@pytest.mark.asyncio
async def test_copy_from_source_translates_to_fs_copy_payload() -> None:
    admin = _StubAdminClient()
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")
    request = SourceCopyRequest(
        target_cookie="",
        source=SourceObjectRef(openlist_path="/gd/Movies/Movie.2024.mkv"),
        target_path="/caiyun-alice/EmbyCache/Movies/Movie.2024.mkv",
    )

    result = await strategy.copy_from_source(request)

    assert result.ok is True
    assert result.target_path == request.target_path
    assert admin.copy_calls == [
        ("/gd/Movies", "/caiyun-alice/EmbyCache/Movies", ["Movie.2024.mkv"]),
    ]


@pytest.mark.asyncio
async def test_copy_from_source_returns_failure_when_fs_copy_returns_error() -> None:
    admin = _StubAdminClient()
    admin.copy_responses = [CopyResult(ok=False, error="storage full")]
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")
    request = SourceCopyRequest(
        target_cookie="",
        source=SourceObjectRef(openlist_path="/gd/Movies/Movie.2024.mkv"),
        target_path="/caiyun-alice/EmbyCache/Movies/Movie.2024.mkv",
    )

    result = await strategy.copy_from_source(request)

    assert result.ok is False
    assert result.error_code == "openlist_copy_failed"
    assert result.detail == "storage full"


@pytest.mark.asyncio
async def test_copy_from_pool_raises_not_implemented() -> None:
    strategy = OpenListCopyStrategy(admin_client=_StubAdminClient(), drive_type="caiyun")
    request = PoolCopyRequest(
        donor_cookie="",
        target_cookie="",
        source_path="/x",
        target_path="/y",
    )

    with pytest.raises(NotImplementedError):
        await strategy.copy_from_pool(request)


@pytest.mark.asyncio
async def test_probe_returns_healthy_when_fs_list_yields_items() -> None:
    admin = _StubAdminClient()
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")

    result = await strategy.probe(_Drive())

    assert result.ok is True
    assert admin.list_calls == ["/caiyun-alice"]


@pytest.mark.asyncio
async def test_probe_returns_mount_missing_on_404() -> None:
    admin = _StubAdminClient()
    admin.list_raises = OpenListAdminError(404, "not found")
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")

    result = await strategy.probe(_Drive())

    assert result.ok is False
    assert result.error_code == "mount_missing"
    assert result.detail == "not found"


@pytest.mark.asyncio
async def test_probe_returns_invalid_token_on_401() -> None:
    admin = _StubAdminClient()
    admin.list_raises = OpenListAdminError(401, "unauthorized")
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")

    result = await strategy.probe(_Drive())

    assert result.ok is False
    assert result.error_code == "invalid_token"


@pytest.mark.asyncio
async def test_probe_returns_mount_missing_when_drive_has_no_mount_path() -> None:
    strategy = OpenListCopyStrategy(admin_client=_StubAdminClient(), drive_type="caiyun")

    result = await strategy.probe(_Drive(openlist_mount_path=None))

    assert result.ok is False
    assert result.error_code == "mount_missing"


@pytest.mark.asyncio
async def test_aclose_closes_admin_client() -> None:
    admin = _StubAdminClient()
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")

    await strategy.aclose()

    assert admin.closed is True
