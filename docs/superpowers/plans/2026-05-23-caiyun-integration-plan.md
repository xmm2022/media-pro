# Caiyun Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land caiyun (139 mobile cloud) as the second user-terminal drive in media-pro by introducing a `RapidCopyStrategy` abstraction, an `OpenListAdminClient` for OpenList-managed storages, and admin API + playback_resolver branches that dispatch by `drive_type`.

**Architecture:** 115 keeps its dedicated `rapid-copy` external service path (wrapped as `Rapid115Strategy`). caiyun (and future OpenList-backed drivers) route through OpenList `/api/fs/copy` via `OpenListCopyStrategy`. Strategy registry lives in `PlaybackResolver`, replacing four hand-constructed clients. `UserDriveAccount` gains `openlist_mount_path` and `cookie_encrypted` becomes nullable. caiyun's OAuth tokens stay in OpenList; media-pro records only the mount path.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic (with `batch_alter_table` for SQLite ALTER), Pydantic v2, httpx, pytest, respx, uv.

Spec: `docs/superpowers/specs/2026-05-23-caiyun-integration-design.md`

---

## File Map

**New files:**
- `alembic/versions/0003_caiyun_drive_fields.py` — migration: add `openlist_mount_path`, make `cookie_encrypted` nullable
- `src/gateway/integrations/openlist_admin_client.py` — OpenList admin/storage + fs/copy + fs/list wrapper
- `src/gateway/integrations/rapid_copy_strategy.py` — Protocol + Registry + shared dataclasses (`ProbeResult`)
- `src/gateway/integrations/rapid_copy_115_strategy.py` — wraps existing 115 clients
- `src/gateway/integrations/openlist_copy_strategy.py` — uses `OpenListAdminClient.fs_copy`
- `scripts/validate_caiyun_source_copy.py` — end-to-end smoke against real OpenList + 139 storage
- `tests/db/test_migration_0003_caiyun_drive_fields.py`
- `tests/integrations/test_openlist_admin_client.py`
- `tests/integrations/test_rapid_copy_strategy_registry.py`
- `tests/integrations/test_rapid_copy_115_strategy.py`
- `tests/integrations/test_openlist_copy_strategy.py`
- `tests/playback/test_playback_resolver_caiyun.py`
- `tests/api/test_admin_drives_caiyun.py`

**Modified files:**
- `src/gateway/models.py` — `UserDriveAccount.cookie_encrypted` nullable, add `openlist_mount_path`; add `SUPPORTED_DRIVE_TYPES`, `OPENLIST_BACKED_DRIVE_TYPES`
- `src/gateway/schemas.py` — `DriveAccountCreate.cookie` optional, add `caiyun` sub-object, add `mount_path`
- `src/gateway/config.py` — add `openlist_admin_token`
- `src/gateway/api/admin.py` — `create_drive` / `update_drive` / `delete_drive` / `_probe_drive` / `_build_drive_account_read` for caiyun branch
- `src/gateway/playback_resolver.py` — strategy registry dispatch, drop `== "115"` filter on target drive, keep `== "115"` filter on donor pool
- `src/gateway/api/playback.py` — construct `PlaybackResolver` via strategy registry
- `tests/api/test_admin_drives.py` — `insert_drive` helper accepts `cookie=None`
- `.env.example` — add `GATEWAY_OPENLIST_ADMIN_TOKEN`

---

## Task 1: Alembic migration 0003 — caiyun drive fields

**Files:**
- Create: `alembic/versions/0003_caiyun_drive_fields.py`
- Create: `tests/db/test_migration_0003_caiyun_drive_fields.py`
- Modify: `src/gateway/models.py`

- [ ] **Step 1: Write the migration**

Create `alembic/versions/0003_caiyun_drive_fields.py`:

```python
import sqlalchemy as sa
from alembic import op


revision = "0003_caiyun_drive_fields"
down_revision = "0002_pool_object_health_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_drive_accounts",
        sa.Column("openlist_mount_path", sa.String(length=255), nullable=True),
    )
    with op.batch_alter_table("user_drive_accounts") as batch_op:
        batch_op.alter_column(
            "cookie_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("user_drive_accounts") as batch_op:
        batch_op.alter_column(
            "cookie_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )
    op.drop_column("user_drive_accounts", "openlist_mount_path")
```

`batch_alter_table` is required because SQLite cannot DROP NOT NULL via plain ALTER COLUMN — alembic rewrites the table under the hood.

- [ ] **Step 2: Write the failing test**

Create `tests/db/test_migration_0003_caiyun_drive_fields.py`:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_0003_adds_openlist_mount_path_and_makes_cookie_encrypted_nullable(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "caiyun-migration.db"
    database_url = f"sqlite:///{database_path}"

    config = _alembic_config(database_url)
    command.upgrade(config, "0003_caiyun_drive_fields")

    engine = create_engine(database_url, future=True)
    columns = {column["name"]: column for column in inspect(engine).get_columns("user_drive_accounts")}
    assert "openlist_mount_path" in columns
    assert columns["openlist_mount_path"]["nullable"] is True
    assert columns["cookie_encrypted"]["nullable"] is True

    command.downgrade(config, "0002_pool_object_health_state")
    columns_after = {
        column["name"]: column for column in inspect(engine).get_columns("user_drive_accounts")
    }
    assert "openlist_mount_path" not in columns_after
    assert columns_after["cookie_encrypted"]["nullable"] is False
```

If `tests/db/__init__.py` does not exist, also create an empty file there (matches existing tests structure).

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/db/test_migration_0003_caiyun_drive_fields.py -v`

Expected: FAIL with "revision '0003_caiyun_drive_fields' not found" or similar — alembic doesn't know about the new revision yet, OR succeeds if alembic discovers the file (then fails on the model assertion below if `models.py` not updated).

If the test passes at this point, double-check `alembic/versions/0003_*.py` was actually created in the right place: `ls alembic/versions/`.

- [ ] **Step 4: Run test to verify the migration applies cleanly**

Run: `uv run pytest tests/db/test_migration_0003_caiyun_drive_fields.py -v`

Expected: PASS.

- [ ] **Step 5: Update the SQLAlchemy model**

Edit `src/gateway/models.py`:

Change `UserDriveAccount.cookie_encrypted` to nullable and add the new column. Find the existing block:

```python
class UserDriveAccount(Base):
    __tablename__ = "user_drive_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    drive_type: Mapped[str] = mapped_column(String(32), default="115")
    cookie_encrypted: Mapped[str] = mapped_column(Text)
    root_dir: Mapped[str] = mapped_column(String(255), default="/EmbyCache")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    share_pool_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Replace with:

```python
class UserDriveAccount(Base):
    __tablename__ = "user_drive_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    drive_type: Mapped[str] = mapped_column(String(32), default="115")
    cookie_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_dir: Mapped[str] = mapped_column(String(255), default="/EmbyCache")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    share_pool_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    openlist_mount_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Add the supported-driver constants near the top of `models.py`, after the `enum_values` helper:

```python
SUPPORTED_DRIVE_TYPES: frozenset[str] = frozenset({"115", "caiyun"})
OPENLIST_BACKED_DRIVE_TYPES: frozenset[str] = frozenset({"caiyun"})
```

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest tests -q`

Expected: all existing tests pass + the new migration test. If a 115 test fails because `cookie_encrypted` type changed in a fixture, fix the fixture inline. There should be zero such fixtures (the column was already free-form via cipher.encrypt), but if one breaks, log it and fix.

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/0003_caiyun_drive_fields.py \
        tests/db/test_migration_0003_caiyun_drive_fields.py \
        src/gateway/models.py
git commit -m "feat: caiyun migration + nullable cookie + supported driver constants"
```

---

## Task 2: OpenList admin client

**Files:**
- Create: `src/gateway/integrations/openlist_admin_client.py`
- Create: `tests/integrations/test_openlist_admin_client.py`
- Modify: `src/gateway/config.py`
- Modify: `.env.example`

- [ ] **Step 0: Lock down real OpenList admin API URLs (operator action)**

The local OpenList instance is running on `http://localhost:5246`. With the admin token in hand, curl-probe each endpoint once and verify the URL + payload shape match the assumptions below. If any URL differs in this OpenList version, adjust the client code in Step 4 inline.

```bash
TOKEN="<your-openlist-admin-token>"

# Storage CRUD
curl -sS -H "Authorization: $TOKEN" http://localhost:5246/api/admin/storage/list | head -c 500
curl -sS -H "Authorization: $TOKEN" -X POST -H "Content-Type: application/json" \
     -d '{"mount_path":"/_poc_probe","driver":"139Yun","addition":"{}"}' \
     http://localhost:5246/api/admin/storage/create | head -c 500
curl -sS -H "Authorization: $TOKEN" -X POST -H "Content-Type: application/json" \
     -d '{"mount_path":"/_poc_probe"}' \
     http://localhost:5246/api/admin/storage/delete | head -c 500

# fs operations
curl -sS -H "Authorization: $TOKEN" -X POST -H "Content-Type: application/json" \
     -d '{"path":"/"}' http://localhost:5246/api/fs/list | head -c 500
curl -sS -H "Authorization: $TOKEN" -X POST -H "Content-Type: application/json" \
     -d '{"src_dir":"/a","dst_dir":"/b","names":["x"]}' \
     http://localhost:5246/api/fs/copy | head -c 500
```

Record any deviation (e.g. POST vs GET, payload key differences) and apply to Step 4. Don't write the implementation until URLs are confirmed.

- [ ] **Step 1: Add admin token env var to config**

Edit `src/gateway/config.py`. Find the `Settings` class and add `openlist_admin_token`:

```python
class Settings(BaseSettings):
    app_name: str = "GD Source-First Playback Gateway"
    openlist_base_url: str = Field("http://localhost:5244")
    openlist_token: str = Field("")
    openlist_admin_token: str = Field("")
    rapid_copy_base_url: str = Field("http://localhost:9000")
    database_url: str = Field("sqlite:///./gateway.db")
    cookie_secret: str = Field("change-me-please")
    openlist_probe_path: str = Field("/Movies/sample.mkv")
    catalog_root_path: str = Field("/Movies")
    rapid_copy_donor_cookie: str = Field("")
    rapid_copy_target_cookie: str = Field("")
    rapid_copy_source_path: str = Field("/Movies/sample.mkv")
    rapid_copy_target_path: str = Field("/EmbyCache/sample.mkv")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="GATEWAY_")


settings = Settings()
```

Append to `.env.example`:

```
GATEWAY_OPENLIST_ADMIN_TOKEN=
```

- [ ] **Step 2: Write the failing tests**

Create `tests/integrations/test_openlist_admin_client.py`:

```python
import json

import httpx
import pytest
import respx

from gateway.integrations.openlist_admin_client import (
    OpenListAdminClient,
    OpenListAdminError,
    StorageRecord,
)


@pytest.mark.asyncio
@respx.mock
async def test_list_storages_returns_parsed_records() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "id": 1,
                            "mount_path": "/caiyun-a",
                            "driver": "139Yun",
                            "addition": json.dumps({"access_token": "tok"}),
                        },
                        {
                            "id": 2,
                            "mount_path": "/gd",
                            "driver": "GoogleDrive",
                            "addition": "{}",
                        },
                    ]
                }
            },
        )
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        records = await client.list_storages()
    finally:
        await client.aclose()
    assert records == [
        StorageRecord(id=1, mount_path="/caiyun-a", driver="139Yun", addition={"access_token": "tok"}),
        StorageRecord(id=2, mount_path="/gd", driver="GoogleDrive", addition={}),
    ]


@pytest.mark.asyncio
@respx.mock
async def test_create_storage_returns_storage_id() -> None:
    respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(200, json={"data": {"id": 7}})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        storage_id = await client.create_storage(
            driver="139Yun",
            mount_path="/caiyun-alice",
            addition={"access_token": "tok-a", "refresh_token": "rt-a"},
        )
    finally:
        await client.aclose()
    assert storage_id == 7


@pytest.mark.asyncio
@respx.mock
async def test_create_storage_raises_on_non_200() -> None:
    respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(400, json={"message": "duplicate mount_path"})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        with pytest.raises(OpenListAdminError) as exc_info:
            await client.create_storage(
                driver="139Yun",
                mount_path="/caiyun-alice",
                addition={"access_token": "tok"},
            )
    finally:
        await client.aclose()
    assert exc_info.value.status_code == 400
    assert "duplicate" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_delete_storage_by_mount_resolves_id_then_deletes() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"content": [{"id": 5, "mount_path": "/caiyun-alice", "driver": "139Yun", "addition": "{}"}]}},
        )
    )
    delete_route = respx.post("http://openlist.local/api/admin/storage/delete").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        await client.delete_storage_by_mount("/caiyun-alice")
    finally:
        await client.aclose()
    assert delete_route.called
    sent_body = json.loads(delete_route.calls.last.request.content)
    assert sent_body == {"id": 5}


@pytest.mark.asyncio
@respx.mock
async def test_fs_copy_returns_copy_result() -> None:
    respx.post("http://openlist.local/api/fs/copy").mock(
        return_value=httpx.Response(200, json={"data": {"task_id": "t-123"}, "code": 200})
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        result = await client.fs_copy(
            src_dir="/gd/Movies",
            dst_dir="/caiyun-alice/EmbyCache/Movies",
            names=["Movie.2024.mkv"],
        )
    finally:
        await client.aclose()
    assert result.ok is True
    assert result.task_id == "t-123"


@pytest.mark.asyncio
@respx.mock
async def test_fs_list_returns_items() -> None:
    respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {"name": "Movies", "is_dir": True, "size": 0},
                        {"name": "readme.txt", "is_dir": False, "size": 12},
                    ]
                }
            },
        )
    )
    client = OpenListAdminClient(base_url="http://openlist.local", admin_token="admin-token")
    try:
        items = await client.fs_list("/caiyun-alice")
    finally:
        await client.aclose()
    assert len(items) == 2
    assert items[0].name == "Movies"
    assert items[0].is_dir is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/integrations/test_openlist_admin_client.py -v`

Expected: FAIL with `ImportError` because `openlist_admin_client` does not exist.

- [ ] **Step 4: Write the implementation**

Create `src/gateway/integrations/openlist_admin_client.py`:

```python
"""OpenList admin/storage + fs/copy + fs/list wrapper.

Spec: docs/superpowers/specs/2026-05-23-caiyun-integration-design.md
section: 设计 / 6. OpenList admin client
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class StorageRecord:
    id: int
    mount_path: str
    driver: str
    addition: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CopyResult:
    ok: bool
    task_id: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FsItem:
    name: str
    is_dir: bool
    size: int


class OpenListAdminError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"openlist admin error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class OpenListAdminClient:
    def __init__(self, *, base_url: str, admin_token: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": admin_token},
            timeout=timeout,
        )

    async def list_storages(self) -> list[StorageRecord]:
        response = await self._client.get("/api/admin/storage/list")
        data = self._extract_data(response)
        items = data.get("content") or []
        return [self._parse_storage(item) for item in items]

    async def create_storage(
        self, *, driver: str, mount_path: str, addition: dict[str, Any]
    ) -> int:
        payload = {
            "mount_path": mount_path,
            "driver": driver,
            "addition": json.dumps(addition),
        }
        response = await self._client.post("/api/admin/storage/create", json=payload)
        data = self._extract_data(response)
        storage_id = data.get("id")
        if not isinstance(storage_id, int):
            raise OpenListAdminError(response.status_code, f"create returned no id: {response.text[:200]}")
        return storage_id

    async def update_storage(self, storage_id: int, *, addition: dict[str, Any]) -> None:
        payload = {"id": storage_id, "addition": json.dumps(addition)}
        response = await self._client.post("/api/admin/storage/update", json=payload)
        self._extract_data(response)

    async def delete_storage(self, storage_id: int) -> None:
        payload = {"id": storage_id}
        response = await self._client.post("/api/admin/storage/delete", json=payload)
        self._extract_data(response)

    async def delete_storage_by_mount(self, mount_path: str) -> None:
        storages = await self.list_storages()
        match = next((s for s in storages if s.mount_path == mount_path), None)
        if match is None:
            raise OpenListAdminError(404, f"storage with mount_path {mount_path} not found")
        await self.delete_storage(match.id)

    async def fs_copy(self, *, src_dir: str, dst_dir: str, names: list[str]) -> CopyResult:
        payload = {"src_dir": src_dir, "dst_dir": dst_dir, "names": names}
        response = await self._client.post("/api/fs/copy", json=payload)
        try:
            data = self._extract_data(response)
        except OpenListAdminError as exc:
            return CopyResult(ok=False, error=exc.message)
        return CopyResult(ok=True, task_id=self._optional_str(data.get("task_id")))

    async def fs_list(self, mount_path: str) -> list[FsItem]:
        payload = {"path": mount_path, "password": ""}
        response = await self._client.post("/api/fs/list", json=payload)
        data = self._extract_data(response)
        items = data.get("content") or []
        return [
            FsItem(
                name=str(item.get("name", "")),
                is_dir=bool(item.get("is_dir", False)),
                size=int(item.get("size") or 0),
            )
            for item in items
        ]

    async def aclose(self) -> None:
        await self._client.aclose()

    def _extract_data(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise OpenListAdminError(response.status_code, self._extract_message(response))
        try:
            body = response.json()
        except ValueError as exc:
            raise OpenListAdminError(response.status_code, f"invalid json: {exc}") from exc
        code = body.get("code")
        if isinstance(code, int) and code >= 400:
            raise OpenListAdminError(code, str(body.get("message") or "openlist error"))
        return body.get("data") or {}

    def _extract_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:200]
        return str(body.get("message") or body.get("error") or response.text[:200])

    def _parse_storage(self, item: dict[str, Any]) -> StorageRecord:
        addition = item.get("addition") or "{}"
        parsed_addition = json.loads(addition) if isinstance(addition, str) else dict(addition)
        return StorageRecord(
            id=int(item.get("id") or 0),
            mount_path=str(item.get("mount_path", "")),
            driver=str(item.get("driver", "")),
            addition=parsed_addition,
        )

    def _optional_str(self, value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/integrations/test_openlist_admin_client.py -v`

Expected: all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gateway/integrations/openlist_admin_client.py \
        tests/integrations/test_openlist_admin_client.py \
        src/gateway/config.py .env.example
git commit -m "feat: openlist admin client (storage CRUD + fs copy/list)"
```

---

## Task 3: RapidCopyStrategy Protocol + Registry + Rapid115Strategy

**Files:**
- Create: `src/gateway/integrations/rapid_copy_strategy.py`
- Create: `src/gateway/integrations/rapid_copy_115_strategy.py`
- Create: `tests/integrations/test_rapid_copy_strategy_registry.py`
- Create: `tests/integrations/test_rapid_copy_115_strategy.py`

- [ ] **Step 1: Write failing test for the registry**

Create `tests/integrations/test_rapid_copy_strategy_registry.py`:

```python
import pytest

from gateway.integrations.rapid_copy_strategy import (
    RapidCopyStrategyRegistry,
    UnsupportedDriveType,
)


class FakeStrategy:
    def __init__(self, drive_type: str) -> None:
        self.drive_type = drive_type


def test_registry_returns_strategy_for_registered_drive_type() -> None:
    registry = RapidCopyStrategyRegistry()
    strategy = FakeStrategy("115")
    registry.register(strategy)
    assert registry.get("115") is strategy


def test_registry_raises_for_unknown_drive_type() -> None:
    registry = RapidCopyStrategyRegistry()
    with pytest.raises(UnsupportedDriveType):
        registry.get("aliyun")


def test_registry_replaces_strategy_on_re_register() -> None:
    registry = RapidCopyStrategyRegistry()
    first = FakeStrategy("115")
    second = FakeStrategy("115")
    registry.register(first)
    registry.register(second)
    assert registry.get("115") is second
```

- [ ] **Step 2: Run test — verify it fails**

Run: `uv run pytest tests/integrations/test_rapid_copy_strategy_registry.py -v`

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement Protocol + Registry + shared dataclasses**

Create `src/gateway/integrations/rapid_copy_strategy.py`:

```python
"""RapidCopyStrategy protocol + registry.

Spec: docs/superpowers/specs/2026-05-23-caiyun-integration-design.md
section: 设计 / 1. RapidCopyStrategy 抽象层
"""
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
```

- [ ] **Step 4: Run registry test — verify pass**

Run: `uv run pytest tests/integrations/test_rapid_copy_strategy_registry.py -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Write failing test for `Rapid115Strategy`**

Create `tests/integrations/test_rapid_copy_115_strategy.py`:

```python
from dataclasses import dataclass

import pytest

from gateway.integrations.rapid_copy_115_strategy import Rapid115Strategy
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
    SourceObjectRef,
)
from gateway.models import UserDriveAccount


@dataclass
class _RecordingDrive:
    drive_type: str = "115"
    cookie_encrypted: str = "encrypted"
    root_dir: str = "/EmbyCache/alice"


class _StubPoolClient:
    def __init__(self) -> None:
        self.calls: list[PoolCopyRequest] = []

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        self.calls.append(request)
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None: ...


class _StubSourceClient:
    def __init__(self) -> None:
        self.calls: list[SourceCopyRequest] = []

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        self.calls.append(request)
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None: ...


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
    drive = _RecordingDrive()
    result = await strategy.probe(drive)
    assert result.ok is True
    assert health_client.calls == [("UID=plain", "/EmbyCache/alice")]
```

- [ ] **Step 6: Implement `Rapid115Strategy`**

Create `src/gateway/integrations/rapid_copy_115_strategy.py`:

```python
"""Rapid115Strategy: 115-specific implementation of RapidCopyStrategy.

Wraps existing PoolCopy115Client / SourceCopy115Client / Drive115HealthClient
behind the strategy interface so PlaybackResolver can dispatch by drive_type.

Spec: docs/superpowers/specs/2026-05-23-caiyun-integration-design.md
section: 设计 / 1. RapidCopyStrategy 抽象层
"""
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
        self._source_copy_client = source_copy_client
        if self._source_copy_client is None:
            raise ValueError("Rapid115Strategy requires a source_copy_client")
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
        if hasattr(self._source_copy_client, "aclose"):
            await self._source_copy_client.aclose()

    def _decrypt(self, value: str | None) -> str:
        if self._cookie_cipher is None:
            raise ValueError("Rapid115Strategy.probe requires cookie_cipher")
        return self._cookie_cipher.decrypt(value)
```

- [ ] **Step 7: Run all new tests — verify pass**

Run: `uv run pytest tests/integrations/test_rapid_copy_115_strategy.py tests/integrations/test_rapid_copy_strategy_registry.py -v`

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add src/gateway/integrations/rapid_copy_strategy.py \
        src/gateway/integrations/rapid_copy_115_strategy.py \
        tests/integrations/test_rapid_copy_strategy_registry.py \
        tests/integrations/test_rapid_copy_115_strategy.py
git commit -m "feat: rapid copy strategy abstraction + 115 wrapper"
```

---

## Task 4: OpenListCopyStrategy

**Files:**
- Create: `src/gateway/integrations/openlist_copy_strategy.py`
- Create: `tests/integrations/test_openlist_copy_strategy.py`

- [ ] **Step 1: Write failing tests**

Create `tests/integrations/test_openlist_copy_strategy.py`:

```python
from dataclasses import dataclass, field
from pathlib import PurePosixPath

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
    openlist_mount_path: str = "/caiyun-alice"
    root_dir: str = "/EmbyCache"
    cookie_encrypted: str | None = None


class _StubAdminClient:
    def __init__(self) -> None:
        self.copy_calls: list[tuple[str, str, list[str]]] = []
        self.list_calls: list[str] = []
        self.copy_responses: list[CopyResult] = []
        self.list_response: list[FsItem] = [FsItem(name="dummy", is_dir=False, size=1)]
        self.list_raises: Exception | None = None

    async def fs_copy(self, *, src_dir: str, dst_dir: str, names: list[str]) -> CopyResult:
        self.copy_calls.append((src_dir, dst_dir, names))
        if self.copy_responses:
            return self.copy_responses.pop(0)
        return CopyResult(ok=True, task_id="t-x")

    async def fs_list(self, mount_path: str):
        self.list_calls.append(mount_path)
        if self.list_raises is not None:
            raise self.list_raises
        return self.list_response

    async def aclose(self) -> None: ...


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
    drive = _Drive()
    result = await strategy.probe(drive)
    assert result.ok is True
    assert admin.list_calls == ["/caiyun-alice"]


@pytest.mark.asyncio
async def test_probe_returns_mount_missing_on_404() -> None:
    admin = _StubAdminClient()
    admin.list_raises = OpenListAdminError(404, "not found")
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")
    drive = _Drive()
    result = await strategy.probe(drive)
    assert result.ok is False
    assert result.error_code == "mount_missing"


@pytest.mark.asyncio
async def test_probe_returns_invalid_token_on_401() -> None:
    admin = _StubAdminClient()
    admin.list_raises = OpenListAdminError(401, "unauthorized")
    strategy = OpenListCopyStrategy(admin_client=admin, drive_type="caiyun")
    drive = _Drive()
    result = await strategy.probe(drive)
    assert result.ok is False
    assert result.error_code == "invalid_token"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integrations/test_openlist_copy_strategy.py -v`

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write the implementation**

Create `src/gateway/integrations/openlist_copy_strategy.py`:

```python
"""OpenListCopyStrategy: routes copy requests through OpenList /api/fs/copy.

Used for drive types in OPENLIST_BACKED_DRIVE_TYPES (currently caiyun).
Pool copy is intentionally not supported in MVP.

Spec: docs/superpowers/specs/2026-05-23-caiyun-integration-design.md
section: 设计 / 1. RapidCopyStrategy 抽象层
"""
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
        result = await self._admin_client.fs_copy(
            src_dir=str(source_path.parent),
            dst_dir=str(target_path.parent),
            names=[source_path.name],
        )
        if not result.ok:
            return RapidCopyResult(
                ok=False,
                error_code="openlist_copy_failed",
                detail=result.error,
            )
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        raise NotImplementedError("pool copy is not supported for OpenList-backed drivers in MVP")

    async def probe(self, drive: UserDriveAccount) -> ProbeResult:
        mount_path = drive.openlist_mount_path
        if not mount_path:
            return ProbeResult(ok=False, error_code="mount_missing", detail="drive has no mount_path")
        try:
            await self._admin_client.fs_list(mount_path)
        except OpenListAdminError as exc:
            if exc.status_code == 404:
                return ProbeResult(ok=False, error_code="mount_missing", detail=exc.message)
            if exc.status_code in (401, 403):
                return ProbeResult(ok=False, error_code="invalid_token", detail=exc.message)
            return ProbeResult(ok=False, error_code="openlist_http_error", detail=exc.message)
        except Exception as exc:  # pragma: no cover - defensive mapping
            return ProbeResult(ok=False, error_code="openlist_admin_failed", detail=str(exc))
        return ProbeResult(ok=True)

    async def aclose(self) -> None:
        await self._admin_client.aclose()
```

- [ ] **Step 4: Run tests — verify pass**

Run: `uv run pytest tests/integrations/test_openlist_copy_strategy.py -v`

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gateway/integrations/openlist_copy_strategy.py \
        tests/integrations/test_openlist_copy_strategy.py
git commit -m "feat: openlist copy strategy with caiyun probe error mapping"
```

---

## Task 5: PlaybackResolver dispatch + playback API construction

**Files:**
- Modify: `src/gateway/playback_resolver.py`
- Modify: `src/gateway/api/playback.py`
- Create: `tests/playback/test_playback_resolver_caiyun.py`

This task changes `PlaybackResolver`'s constructor surface. The existing playback_resolver tests use the old constructor; that's a known regression vector — make the new constructor backwards-compatible by accepting either the legacy keyword arguments or the new `strategy_registry`, then move tests to the new API in a follow-up if needed.

- [ ] **Step 1: Add `strategy_registry` parameter to `PlaybackResolver.__init__`**

Edit `src/gateway/playback_resolver.py`. Find the `__init__` method:

```python
    def __init__(
        self,
        playback_service: PlaybackService,
        openlist_client: OpenListClient,
        *,
        rapid_copy_client: RapidCopyClient | None = None,
        pool_copy_client: PoolCopy115Client | None = None,
        source_copy_client: SourceCopy115Client | None = None,
        drive_stream_client: Drive115StreamClient | None = None,
        cookie_cipher: CookieCipher | None = None,
        pool_service: PoolService | None = None,
        transfer_service: TransferService | None = None,
    ) -> None:
```

Replace with:

```python
    def __init__(
        self,
        playback_service: PlaybackService,
        openlist_client: OpenListClient,
        *,
        strategy_registry: "RapidCopyStrategyRegistry | None" = None,
        rapid_copy_client: RapidCopyClient | None = None,
        pool_copy_client: PoolCopy115Client | None = None,
        source_copy_client: SourceCopy115Client | None = None,
        drive_stream_client: Drive115StreamClient | None = None,
        cookie_cipher: CookieCipher | None = None,
        pool_service: PoolService | None = None,
        transfer_service: TransferService | None = None,
    ) -> None:
```

Add the import at the top of the file (with the other gateway imports):

```python
from gateway.integrations.rapid_copy_strategy import (
    RapidCopyStrategy,
    RapidCopyStrategyRegistry,
    UnsupportedDriveType,
)
```

In the body of `__init__`, after the existing assignments, append:

```python
        self._strategy_registry = strategy_registry
```

- [ ] **Step 2: Replace `== "115"` filter on target drive selection**

In `_load_target_drive` (search for `UserDriveAccount.drive_type == "115"`), change from:

```python
    def _load_target_drive(self, session: Session, *, user_id: int) -> UserDriveAccount | None:
        return session.scalar(
            select(UserDriveAccount)
            .where(
                UserDriveAccount.user_id == user_id,
                UserDriveAccount.drive_type == "115",
                UserDriveAccount.enabled.is_(True),
            )
            .order_by(UserDriveAccount.id.desc())
        )
```

To:

```python
    def _load_target_drive(self, session: Session, *, user_id: int) -> UserDriveAccount | None:
        drive_type_preference = case(
            (UserDriveAccount.drive_type == "115", 0),
            else_=1,
        )
        return session.scalar(
            select(UserDriveAccount)
            .where(
                UserDriveAccount.user_id == user_id,
                UserDriveAccount.enabled.is_(True),
            )
            .order_by(drive_type_preference, UserDriveAccount.id.desc())
        )
```

Add `case` to the SQLAlchemy import at the top:

```python
from sqlalchemy import case, select
```

- [ ] **Step 3: Replace hardcoded "115" in `_upsert_pool_object`**

Find `_upsert_pool_object`. Change the `PoolObject(...)` constructor's `drive_type="115"` to `drive_type=target_drive.drive_type`. Since `_upsert_pool_object` currently doesn't take a `target_drive` argument, thread it through:

```python
    def _upsert_pool_object(
        self,
        session: Session,
        *,
        media_id: int,
        owner_user_id: int,
        target_path: str,
        drive_type: str,
    ) -> PoolObject:
        pool_object = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id == owner_user_id,
            )
        )
        if pool_object is None:
            pool_object = PoolObject(
                media_id=media_id,
                owner_user_id=owner_user_id,
                drive_type=drive_type,
                target_path=target_path,
                status=PoolObjectStatus.READY,
            )
            session.add(pool_object)
            self._mark_pool_object_ready(pool_object)
            return pool_object

        pool_object.target_path = target_path
        self._mark_pool_object_ready(pool_object)
        return pool_object
```

Then update the two callsites of `_upsert_pool_object` (search for `_upsert_pool_object(`) to pass `drive_type=target_drive.drive_type`.

- [ ] **Step 4: Add strategy dispatch in copy branches**

In `resolve()`, where the existing code reads `await self._pool_copy_client.copy_from_pool(...)` / `await self._rapid_copy_client.copy_from_pool(...)` / `await self._source_copy_client.copy_from_source(...)` / `await self._rapid_copy_client.copy_from_source(...)`, replace each set of two branches with a single strategy call (after introducing a helper `_dispatch_strategy(target_drive)`):

```python
    def _dispatch_strategy(self, target_drive: UserDriveAccount):
        if self._strategy_registry is not None:
            try:
                return self._strategy_registry.get(target_drive.drive_type)
            except UnsupportedDriveType:
                return None
        return None
```

Then in `resolve()`, immediately after the `target_drive` is loaded but before the pool block:

```python
        strategy = self._dispatch_strategy(target_drive) if target_drive is not None else None
```

Replace the pool block invocation:

```python
                if self._pool_copy_client is not None:
                    donor_result = await self._pool_copy_client.copy_from_pool(pool_request)
                else:
                    donor_result = await self._rapid_copy_client.copy_from_pool(pool_request)
```

with:

```python
                if strategy is not None:
                    try:
                        donor_result = await strategy.copy_from_pool(pool_request)
                    except NotImplementedError:
                        donor_result = RapidCopyResult(
                            ok=False, error_code="pool_not_supported_for_drive_type"
                        )
                elif self._pool_copy_client is not None:
                    donor_result = await self._pool_copy_client.copy_from_pool(pool_request)
                else:
                    donor_result = await self._rapid_copy_client.copy_from_pool(pool_request)
```

Replace the source_copy block:

```python
                if self._source_copy_client is not None:
                    source_result = await self._source_copy_client.copy_from_source(source_request)
                else:
                    source_result = await self._rapid_copy_client.copy_from_source(source_request)
```

with:

```python
                if strategy is not None:
                    source_result = await strategy.copy_from_source(source_request)
                elif self._source_copy_client is not None:
                    source_result = await self._source_copy_client.copy_from_source(source_request)
                else:
                    source_result = await self._rapid_copy_client.copy_from_source(source_request)
```

- [ ] **Step 5: Run the full test suite to verify legacy resolver tests still pass**

Run: `uv run pytest tests -q`

Expected: all existing tests still pass. The dispatch logic is *additive* — legacy callers without `strategy_registry` still hit the old per-client branches.

If anything fails, the fix is on the resolver side. Do not change tests.

- [ ] **Step 6: Write failing test for caiyun source_copy via strategy**

Create `tests/playback/test_playback_resolver_caiyun.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyResult,
    SourceCopyRequest,
)
from gateway.integrations.rapid_copy_strategy import ProbeResult, RapidCopyStrategyRegistry
from gateway.models import Base, MediaItem, User, UserDriveAccount
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver


class _StubCaiyunStrategy:
    drive_type = "caiyun"

    def __init__(self) -> None:
        self.copy_calls: list[SourceCopyRequest] = []

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        self.copy_calls.append(request)
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        raise NotImplementedError

    async def probe(self, drive) -> ProbeResult:
        return ProbeResult(ok=True)

    async def aclose(self) -> None: ...


class _StubOpenListClient:
    async def get_stream_info(self, source_path: str) -> StreamInfo:
        return StreamInfo(
            raw_url=f"http://openlist.local/raw{source_path}",
            content_length=1024,
            accepts_ranges=True,
        )

    async def aclose(self) -> None: ...


@pytest.mark.asyncio
async def test_caiyun_source_copy_routes_through_strategy_and_writes_pool_object(tmp_path: Path) -> None:
    database_path = tmp_path / "caiyun-resolver.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
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
            source_file_id="fp-movie-id",
            size=1024,
            fingerprint="fp-movie",
            openlist_path="/gd/Movies/Movie.2024.mkv",
        )
        session.add_all([drive, media])
        session.commit()
        media_id = media.id
        user_id = user.id

    registry = RapidCopyStrategyRegistry()
    strategy = _StubCaiyunStrategy()
    registry.register(strategy)

    resolver = PlaybackResolver(
        PlaybackService(total_budget_ms=2000),
        _StubOpenListClient(),
        strategy_registry=registry,
        cookie_cipher=None,
    )

    with Session(engine) as session:
        decision = await resolver.resolve(session, user_id=user_id, media_id=media_id)

    assert decision.route == "source_copy"
    assert len(strategy.copy_calls) == 1
    call = strategy.copy_calls[0]
    assert call.source.openlist_path == "/gd/Movies/Movie.2024.mkv"
    assert call.target_path.startswith("/EmbyCache/")
```

Note: this test assumes `PlaybackResolver` can run with `cookie_cipher=None` when the chosen drive has `cookie_encrypted=None`. If `_decrypt_cookie` panics for None cipher and None cookie, modify `_decrypt_cookie` to return None early when both are None. The change:

```python
    def _decrypt_cookie(self, drive: UserDriveAccount | None) -> str | None:
        if drive is None or self._cookie_cipher is None:
            return None
        if drive.cookie_encrypted is None:
            return None
        return self._cookie_cipher.decrypt(drive.cookie_encrypted)
```

Apply this fix while implementing the test.

- [ ] **Step 7: Run the caiyun resolver test — verify pass**

Run: `uv run pytest tests/playback/test_playback_resolver_caiyun.py -v`

Expected: PASS. If the source_copy block has a guard like `can_attempt_source_copy = self._source_copy_client is not None or self._rapid_copy_client is not None` that excludes the strategy-only path, update that guard:

```python
        can_attempt_source_copy = (
            strategy is not None
            or self._source_copy_client is not None
            or self._rapid_copy_client is not None
        )
```

- [ ] **Step 8: Update `playback API` to construct via registry**

Edit `src/gateway/api/playback.py`. Replace `_resolve_playback_decision` body with:

```python
async def _resolve_playback_decision(
    *,
    media_id: int,
    user_id: int,
    request: Request,
    session: Session,
) -> PlaybackDecision:
    openlist_client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    pool_copy_client = PoolCopy115Client()
    source_copy_client = SourceCopy115Client(openlist_client)
    drive_stream_client = Drive115StreamClient()

    registry = RapidCopyStrategyRegistry()
    registry.register(
        Rapid115Strategy(
            pool_copy_client=pool_copy_client,
            source_copy_client=source_copy_client,
            health_client=Drive115HealthClient(),
            cookie_cipher=request.app.state.cookie_cipher,
        )
    )
    if settings.openlist_admin_token:
        registry.register(
            OpenListCopyStrategy(
                admin_client=OpenListAdminClient(
                    base_url=settings.openlist_base_url,
                    admin_token=settings.openlist_admin_token,
                ),
                drive_type="caiyun",
            )
        )

    resolver = PlaybackResolver(
        PlaybackService(total_budget_ms=2000),
        openlist_client,
        strategy_registry=registry,
        cookie_cipher=request.app.state.cookie_cipher,
        drive_stream_client=drive_stream_client,
    )
    try:
        try:
            return await resolver.resolve(session, user_id=user_id, media_id=media_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
    finally:
        await registry.aclose()
        await openlist_client.aclose()
```

Add the imports at the top of `playback.py`:

```python
from gateway.integrations.drive115_health_client import Drive115HealthClient
from gateway.integrations.openlist_admin_client import OpenListAdminClient
from gateway.integrations.openlist_copy_strategy import OpenListCopyStrategy
from gateway.integrations.rapid_copy_115_strategy import Rapid115Strategy
from gateway.integrations.rapid_copy_strategy import RapidCopyStrategyRegistry
```

- [ ] **Step 9: Run all playback tests to ensure both 115 and caiyun paths still pass**

Run: `uv run pytest tests/playback tests/api/test_playback_api.py -v`

Expected: all PASS.

- [ ] **Step 10: Run the full suite**

Run: `uv run pytest tests -q`

Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add src/gateway/playback_resolver.py \
        src/gateway/api/playback.py \
        tests/playback/test_playback_resolver_caiyun.py
git commit -m "feat: playback resolver dispatches via strategy registry"
```

---

## Task 6: Admin API caiyun branch

**Files:**
- Modify: `src/gateway/schemas.py`
- Modify: `src/gateway/api/admin.py`
- Modify: `tests/api/test_admin_drives.py` (helper only)
- Create: `tests/api/test_admin_drives_caiyun.py`

- [ ] **Step 1: Extend `DriveAccountCreate` schema**

Edit `src/gateway/schemas.py`. Replace `DriveAccountCreate`:

```python
class CaiyunDriveCredentials(BaseModel):
    access_token: str
    refresh_token: str = ""
    account_type: str = "personal"


class DriveAccountCreate(BaseModel):
    user_id: int
    drive_type: str
    cookie: str | None = None
    root_dir: str
    share_pool_enabled: bool = False
    caiyun: CaiyunDriveCredentials | None = None
    mount_path: str | None = None

    @model_validator(mode="after")
    def validate_credentials_match_drive_type(self) -> "DriveAccountCreate":
        if self.drive_type == "115":
            if not self.cookie:
                raise ValueError("cookie is required for drive_type=115")
        elif self.drive_type == "caiyun":
            if self.caiyun is None or not self.caiyun.access_token:
                raise ValueError("caiyun.access_token is required for drive_type=caiyun")
        else:
            raise ValueError(f"unsupported drive_type: {self.drive_type}")
        return self
```

Also update `DriveAccountRead` to include `openlist_mount_path` (nullable):

```python
class DriveAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    drive_type: str
    root_dir: str
    enabled: bool
    share_pool_enabled: bool
    health_status: str
    last_checked_at: datetime | None = None
    cookie_preview: str | None = None
    openlist_mount_path: str | None = None
```

Update `DriveAccountUpdate` to allow caiyun token updates:

```python
class DriveAccountUpdate(BaseModel):
    cookie: str | None = None
    caiyun: CaiyunDriveCredentials | None = None
    root_dir: str | None = None
    enabled: bool | None = None
    share_pool_enabled: bool | None = None
    health_status: str | None = None

    @model_validator(mode="after")
    def validate_has_changes(self) -> "DriveAccountUpdate":
        if any(
            value is not None
            for value in (
                self.cookie,
                self.caiyun,
                self.root_dir,
                self.enabled,
                self.share_pool_enabled,
                self.health_status,
            )
        ):
            return self
        raise ValueError("at least one field must be provided")
```

- [ ] **Step 2: Make `_build_drive_account_read` tolerate NULL cookie**

Edit `src/gateway/api/admin.py`. Replace `_build_drive_account_read`:

```python
def _build_drive_account_read(
    drive: UserDriveAccount,
    *,
    request: Request,
) -> DriveAccountRead:
    if drive.cookie_encrypted is not None:
        cookie = request.app.state.cookie_cipher.decrypt(drive.cookie_encrypted)
        cookie_preview = f"{cookie[:5]}..."
    else:
        cookie_preview = None
    return DriveAccountRead(
        id=drive.id,
        user_id=drive.user_id,
        drive_type=drive.drive_type,
        root_dir=drive.root_dir,
        enabled=drive.enabled,
        share_pool_enabled=drive.share_pool_enabled,
        health_status=drive.health_status,
        last_checked_at=drive.last_checked_at,
        cookie_preview=cookie_preview,
        openlist_mount_path=drive.openlist_mount_path,
    )
```

- [ ] **Step 3: Extend `create_drive` with caiyun branch**

Replace `create_drive`:

```python
@router.post("/drives", response_model=DriveAccountRead, status_code=status.HTTP_201_CREATED)
async def create_drive(
    payload: DriveAccountCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveAccountRead:
    if session.get(User, payload.user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.drive_type == "caiyun":
        return await _create_caiyun_drive(payload, request=request, session=session)

    drive = UserDriveAccount(
        user_id=payload.user_id,
        drive_type=payload.drive_type,
        cookie_encrypted=request.app.state.cookie_cipher.encrypt(payload.cookie or ""),
        root_dir=payload.root_dir,
        share_pool_enabled=payload.share_pool_enabled,
    )
    session.add(drive)
    session.commit()
    session.refresh(drive)
    return _build_drive_account_read(drive, request=request)


async def _create_caiyun_drive(
    payload: DriveAccountCreate,
    *,
    request: Request,
    session: Session,
) -> DriveAccountRead:
    mount_path = payload.mount_path or f"/caiyun-{payload.user_id}"
    assert payload.caiyun is not None
    addition = {
        "access_token": payload.caiyun.access_token,
        "refresh_token": payload.caiyun.refresh_token,
        "type": payload.caiyun.account_type,
    }
    admin_client = _build_openlist_admin_client()
    try:
        try:
            await admin_client.create_storage(
                driver="139Yun",
                mount_path=mount_path,
                addition=addition,
            )
        except OpenListAdminError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "openlist_admin_failed", "message": exc.message},
            ) from None
    finally:
        await admin_client.aclose()

    drive = UserDriveAccount(
        user_id=payload.user_id,
        drive_type="caiyun",
        cookie_encrypted=None,
        root_dir=payload.root_dir,
        share_pool_enabled=False,
        openlist_mount_path=mount_path,
    )
    session.add(drive)
    session.commit()
    session.refresh(drive)
    return _build_drive_account_read(drive, request=request)


def _build_openlist_admin_client() -> OpenListAdminClient:
    return OpenListAdminClient(
        base_url=settings.openlist_base_url,
        admin_token=settings.openlist_admin_token,
    )
```

Add imports at the top of `admin.py` (with existing imports):

```python
from gateway.integrations.openlist_admin_client import OpenListAdminClient, OpenListAdminError
```

- [ ] **Step 4: Extend `_probe_drive` with caiyun branch**

In `admin.py`, replace `_probe_drive`:

```python
async def _probe_drive(
    request: Request,
    drive: UserDriveAccount,
) -> DriveHealthResult:
    if drive.drive_type == "115":
        cookie = request.app.state.cookie_cipher.decrypt(drive.cookie_encrypted)
        return await Drive115HealthClient().probe(cookie, drive.root_dir)
    if drive.drive_type == "alist":
        return await _probe_alist_drive(drive.root_dir)
    if drive.drive_type == "caiyun":
        return await _probe_caiyun_drive(drive)
    return DriveHealthResult(
        ok=False,
        error_code="unsupported_drive_type",
        detail=f"Drive type is not probeable: {drive.drive_type}",
    )


async def _probe_caiyun_drive(drive: UserDriveAccount) -> DriveHealthResult:
    if not drive.openlist_mount_path:
        return DriveHealthResult(ok=False, error_code="mount_missing", detail="drive has no mount_path")
    admin_client = _build_openlist_admin_client()
    try:
        try:
            await admin_client.fs_list(drive.openlist_mount_path)
        except OpenListAdminError as exc:
            if exc.status_code == 404:
                return DriveHealthResult(ok=False, error_code="mount_missing", detail=exc.message)
            if exc.status_code in (401, 403):
                return DriveHealthResult(ok=False, error_code="invalid_token", detail=exc.message)
            return DriveHealthResult(ok=False, error_code="openlist_http_error", detail=exc.message)
        except httpx.HTTPError as exc:
            return DriveHealthResult(ok=False, error_code="openlist_admin_failed", detail=str(exc))
    finally:
        await admin_client.aclose()
    return DriveHealthResult(ok=True, error_code=None)
```

- [ ] **Step 5: Extend `update_drive` for caiyun**

Find `update_drive` and add caiyun token-update handling. After the existing `if payload.cookie is not None: drive.cookie_encrypted = ...` line, add:

```python
    if payload.caiyun is not None and drive.drive_type == "caiyun":
        if not drive.openlist_mount_path:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "drive_missing_mount_path", "message": "caiyun drive has no mount_path"},
            )
        addition = {
            "access_token": payload.caiyun.access_token,
            "refresh_token": payload.caiyun.refresh_token,
            "type": payload.caiyun.account_type,
        }
        admin_client = _build_openlist_admin_client()
        try:
            storages = await admin_client.list_storages()
            match = next(
                (s for s in storages if s.mount_path == drive.openlist_mount_path),
                None,
            )
            if match is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "mount_missing", "mount_path": drive.openlist_mount_path},
                )
            try:
                await admin_client.update_storage(match.id, addition=addition)
            except OpenListAdminError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "openlist_admin_failed", "message": exc.message},
                ) from None
        finally:
            await admin_client.aclose()
```

Mark `update_drive` as `async`:

```python
@router.patch("/drives/{drive_id}", response_model=DriveAccountRead)
async def update_drive(
    drive_id: int,
    payload: DriveAccountUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveAccountRead:
```

(The rest of the function body is unchanged.)

- [ ] **Step 6: Extend `delete_drive` for caiyun**

Replace `delete_drive`:

```python
@router.delete("/drives/{drive_id}", response_model=DriveAccountDeleteResponse)
async def delete_drive(
    drive_id: int,
    session: Session = Depends(get_session),
) -> DriveAccountDeleteResponse:
    drive = session.get(UserDriveAccount, drive_id)
    if drive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drive not found")

    if drive.drive_type == "caiyun" and drive.openlist_mount_path:
        admin_client = _build_openlist_admin_client()
        try:
            try:
                await admin_client.delete_storage_by_mount(drive.openlist_mount_path)
            except OpenListAdminError as exc:
                if exc.status_code != 404:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={"error": "openlist_admin_failed", "message": exc.message},
                    ) from None
        finally:
            await admin_client.aclose()

    disabled_pool_objects = _disable_drive_pool_objects(
        session,
        drive=drive,
        root_dirs=[drive.root_dir],
    )
    user_id = drive.user_id
    session.delete(drive)
    session.commit()
    return DriveAccountDeleteResponse(
        drive_id=drive_id,
        user_id=user_id,
        disabled_pool_objects=disabled_pool_objects,
    )
```

- [ ] **Step 7: Update existing `insert_drive` test helper to tolerate None cookie**

Edit `tests/api/test_admin_drives.py`. Find the `insert_drive` function (top of file). Replace:

```python
def insert_drive(
    session: Session,
    *,
    app,
    user_id: int,
    cookie: str,
    root_dir: str,
    ...
```

with:

```python
def insert_drive(
    session: Session,
    *,
    app,
    user_id: int,
    cookie: str | None,
    root_dir: str,
    drive_type: str = "115",
    enabled: bool = True,
    share_pool_enabled: bool = False,
    health_status: str = "unknown",
    openlist_mount_path: str | None = None,
) -> UserDriveAccount:
    cookie_encrypted = app.state.cookie_cipher.encrypt(cookie) if cookie is not None else None
    drive = UserDriveAccount(
        user_id=user_id,
        drive_type=drive_type,
        cookie_encrypted=cookie_encrypted,
        root_dir=root_dir,
        enabled=enabled,
        share_pool_enabled=share_pool_enabled,
        health_status=health_status,
        openlist_mount_path=openlist_mount_path,
    )
    session.add(drive)
    session.flush()
    return drive
```

Update the existing test assertions that include `"cookie_preview"`. The shape of `DriveAccountRead` now has `cookie_preview: str | None` and `openlist_mount_path: str | None`. In `test_admin_drives_endpoint_lists_and_filters_drive_accounts` (and similar), each expected dict needs the extra key `"openlist_mount_path": None`. Add it inline to each expected object:

```python
{
    "id": 1,
    "user_id": 1,
    "drive_type": "115",
    "root_dir": "/EmbyCache/alice",
    "enabled": True,
    "share_pool_enabled": True,
    "health_status": "healthy",
    "last_checked_at": None,
    "cookie_preview": "UID=a...",
    "openlist_mount_path": None,
},
```

Apply the same `"openlist_mount_path": None` insert to every expected dict in `test_admin_drives.py` that previously listed `"cookie_preview"`.

- [ ] **Step 8: Write the caiyun admin API tests**

Create `tests/api/test_admin_drives_caiyun.py`:

```python
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, User, UserDriveAccount


def _bootstrap(tmp_path: Path, db_name: str) -> tuple[object, object]:
    database_url = f"sqlite:///{tmp_path / db_name}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app = create_app(database_url=database_url, cookie_secret="x" * 32)
    return engine, app


def _seed_user(engine, username: str) -> int:
    with Session(engine) as session:
        user = User(username=username, status="active")
        session.add(user)
        session.commit()
        return user.id


@respx.mock
def test_create_caiyun_drive_calls_openlist_then_persists_locally(tmp_path: Path, monkeypatch) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-create.db")
    user_id = _seed_user(engine, "alice")

    monkeypatch.setenv("GATEWAY_OPENLIST_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("GATEWAY_OPENLIST_BASE_URL", "http://openlist.local")
    from gateway.config import Settings
    new_settings = Settings()
    monkeypatch.setattr("gateway.api.admin.settings", new_settings)

    create_route = respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(200, json={"data": {"id": 99}})
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/admin/drives",
            json={
                "user_id": user_id,
                "drive_type": "caiyun",
                "root_dir": "/EmbyCache",
                "caiyun": {
                    "access_token": "tok-a",
                    "refresh_token": "rt-a",
                    "account_type": "personal",
                },
                "mount_path": "/caiyun-alice",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["drive_type"] == "caiyun"
    assert body["openlist_mount_path"] == "/caiyun-alice"
    assert body["cookie_preview"] is None
    assert create_route.called
    sent_body = json.loads(create_route.calls.last.request.content)
    assert sent_body["mount_path"] == "/caiyun-alice"
    assert sent_body["driver"] == "139Yun"
    assert "access_token" in sent_body["addition"]

    with Session(engine) as session:
        drive = session.scalars(select(UserDriveAccount)).one()
    assert drive.cookie_encrypted is None
    assert drive.openlist_mount_path == "/caiyun-alice"


@respx.mock
def test_create_caiyun_drive_returns_502_when_openlist_fails(tmp_path: Path, monkeypatch) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-create-fail.db")
    user_id = _seed_user(engine, "alice")

    monkeypatch.setenv("GATEWAY_OPENLIST_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("GATEWAY_OPENLIST_BASE_URL", "http://openlist.local")
    from gateway.config import Settings
    new_settings = Settings()
    monkeypatch.setattr("gateway.api.admin.settings", new_settings)

    respx.post("http://openlist.local/api/admin/storage/create").mock(
        return_value=httpx.Response(400, json={"message": "duplicate mount_path"})
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/admin/drives",
            json={
                "user_id": user_id,
                "drive_type": "caiyun",
                "root_dir": "/EmbyCache",
                "caiyun": {"access_token": "tok", "refresh_token": "rt", "account_type": "personal"},
                "mount_path": "/caiyun-alice",
            },
        )

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "openlist_admin_failed"

    with Session(engine) as session:
        drives = session.scalars(select(UserDriveAccount)).all()
    assert drives == []  # local table is unchanged


@respx.mock
def test_probe_caiyun_drive_returns_healthy_when_fs_list_returns_items(tmp_path: Path, monkeypatch) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-probe.db")
    user_id = _seed_user(engine, "alice")

    monkeypatch.setenv("GATEWAY_OPENLIST_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("GATEWAY_OPENLIST_BASE_URL", "http://openlist.local")
    from gateway.config import Settings
    new_settings = Settings()
    monkeypatch.setattr("gateway.api.admin.settings", new_settings)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/caiyun-alice",
            root_dir="/EmbyCache",
            enabled=True,
            share_pool_enabled=False,
            health_status="unknown",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

    respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(200, json={"data": {"content": [{"name": "x", "is_dir": False, "size": 1}]}})
    )

    with TestClient(app) as client:
        response = client.post(f"/api/admin/drives/{drive_id}/probe")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["drive"]["health_status"] == "healthy"


@respx.mock
def test_delete_caiyun_drive_calls_openlist_then_deletes_locally(tmp_path: Path, monkeypatch) -> None:
    engine, app = _bootstrap(tmp_path, "caiyun-delete.db")
    user_id = _seed_user(engine, "alice")

    monkeypatch.setenv("GATEWAY_OPENLIST_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("GATEWAY_OPENLIST_BASE_URL", "http://openlist.local")
    from gateway.config import Settings
    new_settings = Settings()
    monkeypatch.setattr("gateway.api.admin.settings", new_settings)

    with Session(engine) as session:
        drive = UserDriveAccount(
            user_id=user_id,
            drive_type="caiyun",
            cookie_encrypted=None,
            openlist_mount_path="/caiyun-alice",
            root_dir="/EmbyCache",
        )
        session.add(drive)
        session.commit()
        drive_id = drive.id

    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"content": [{"id": 5, "mount_path": "/caiyun-alice", "driver": "139Yun", "addition": "{}"}]}},
        )
    )
    delete_route = respx.post("http://openlist.local/api/admin/storage/delete").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )

    with TestClient(app) as client:
        response = client.delete(f"/api/admin/drives/{drive_id}")

    assert response.status_code == 200
    assert delete_route.called

    with Session(engine) as session:
        remaining = session.scalars(select(UserDriveAccount)).all()
    assert remaining == []
```

- [ ] **Step 9: Run the new caiyun admin tests + full suite**

Run: `uv run pytest tests/api/test_admin_drives_caiyun.py -v`

Expected: 4 tests PASS.

Run: `uv run pytest tests -q`

Expected: all tests PASS. If any pre-existing test in `test_admin_drives.py` fails because of the `openlist_mount_path` key newly appearing in responses, finish updating its expected dicts inline.

- [ ] **Step 10: Commit**

```bash
git add src/gateway/schemas.py src/gateway/api/admin.py \
        tests/api/test_admin_drives.py tests/api/test_admin_drives_caiyun.py
git commit -m "feat: admin api caiyun create/probe/patch/delete"
```

---

## Task 7: End-to-end smoke validation

**Files:**
- Create: `scripts/validate_caiyun_source_copy.py`

This task is a manual smoke against the local OpenList + a real 139 storage. It does not gate the feature merge (TDD already proved each unit), but it surfaces real-world surprises (URL form differences, OpenList token quirks).

- [ ] **Step 1: Write the smoke script**

Create `scripts/validate_caiyun_source_copy.py`:

```python
"""End-to-end smoke for caiyun source_copy.

Prereqs:
- Local OpenList running at OPENLIST_BASE_URL
- One 139 storage mounted (mount_path passed via env)
- One GD storage with a small sample file (path passed via env)

Usage:
    GATEWAY_OPENLIST_BASE_URL=http://localhost:5246 \\
    GATEWAY_OPENLIST_ADMIN_TOKEN=<token> \\
    CAIYUN_MOUNT_PATH=/caiyun-test \\
    GD_SOURCE_PATH=/gd/sample.mkv \\
    CAIYUN_TARGET_SUBDIR=/EmbyCache \\
    uv run python scripts/validate_caiyun_source_copy.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import PurePosixPath

from gateway.integrations.openlist_admin_client import OpenListAdminClient


async def main() -> int:
    base_url = os.environ["GATEWAY_OPENLIST_BASE_URL"]
    admin_token = os.environ["GATEWAY_OPENLIST_ADMIN_TOKEN"]
    caiyun_mount = os.environ["CAIYUN_MOUNT_PATH"]
    gd_source = os.environ["GD_SOURCE_PATH"]
    target_subdir = os.environ.get("CAIYUN_TARGET_SUBDIR", "/EmbyCache")

    source = PurePosixPath(gd_source)
    target = PurePosixPath(caiyun_mount + target_subdir + "/" + source.name)

    admin = OpenListAdminClient(base_url=base_url, admin_token=admin_token)
    try:
        print(f"[smoke] copy {source} -> {target}")
        start = time.monotonic()
        result = await admin.fs_copy(
            src_dir=str(source.parent),
            dst_dir=str(target.parent),
            names=[source.name],
        )
        elapsed = time.monotonic() - start
        print(f"[smoke] result ok={result.ok} task_id={result.task_id} error={result.error} ({elapsed:.2f}s)")
        if not result.ok:
            return 1

        print(f"[smoke] verify target via fs_list {target.parent}")
        items = await admin.fs_list(str(target.parent))
        found = any(item.name == source.name for item in items)
        print(f"[smoke] target file present: {found}")
        return 0 if found else 2
    finally:
        await admin.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: Run the smoke (operator action)**

Pre-conditions:
- Local OpenList admin token in hand
- Source file under GD storage smaller than ~100 MB so the smoke doesn't drag

Run:
```bash
GATEWAY_OPENLIST_BASE_URL=http://localhost:5246 \
GATEWAY_OPENLIST_ADMIN_TOKEN=<your-token> \
CAIYUN_MOUNT_PATH=/caiyun-test \
GD_SOURCE_PATH=/gd/sample-100mb.mkv \
CAIYUN_TARGET_SUBDIR=/EmbyCache \
uv run python scripts/validate_caiyun_source_copy.py
```

Expected stdout:
```
[smoke] copy /gd -> /caiyun-test/EmbyCache
[smoke] result ok=True task_id=t-xxxx error=None (0.30s)
[smoke] verify target via fs_list /caiyun-test/EmbyCache
[smoke] target file present: True
```

If elapsed time > 5s for a 100 MB file, OpenList is doing client-relay (streaming) not server-side rapid copy. Capture the time + file size; record in the spec's risk section. The feature still works — just slower than ideal.

- [ ] **Step 3: Commit the smoke script**

```bash
git add scripts/validate_caiyun_source_copy.py
git commit -m "feat: caiyun source_copy smoke validation script"
```

---

## Final acceptance

After Task 1-7 are complete:

```bash
uv run pytest tests -q
```

Expected: all tests pass.

```bash
grep -nE 'drive_type == "115"' src/gateway/playback_resolver.py
```

Expected output: exactly one match — the line inside `_select_donor_bundle` (MVP keeps donor pool 115-only). If you find more, you missed one.

```bash
grep -nE 'drive_type="115"' src/gateway/playback_resolver.py
```

Expected output: empty. The hardcoded `_upsert_pool_object` value was removed in Task 5 Step 3.

Open the spec and confirm every "这阶段要做的事" bullet has a corresponding committed change. Spec at `docs/superpowers/specs/2026-05-23-caiyun-integration-design.md`.
