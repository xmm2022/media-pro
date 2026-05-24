# NextEmby-like Foundation APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the first clean-room product foundation for the NextEmby-like泛云盘 direction: update public positioning, expose provider capabilities, and add admin read APIs for media, transfer attempts, and playback diagnostics.

**Architecture:** Keep the current FastAPI monolith and SQLAlchemy models. Add read-only admin endpoints and Pydantic response models on top of existing tables, with provider metadata kept as explicit catalog data in `gateway.api.admin` until it is large enough to split into its own module.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2, pytest, uv.

---

## Scope

This plan implements the first foundation slice from `docs/superpowers/specs/2026-05-25-media-pro-nextemby-like-positioning-design.md`.

Included:

- README positioning refresh.
- `GET /api/admin/drive-types`.
- `GET /api/admin/media-items`.
- `GET /api/admin/transfer-jobs`.
- `GET /api/admin/playback-records`.
- Focused API tests for each endpoint.

Excluded from this plan:

- Admin UI rewrite.
- User center and user login.
- Provider strategy refactor beyond read-only capability metadata.
- Database schema changes.

## File Structure

- Modify `README.md`: update the first screen and current-stage language to the new泛云盘 product positioning.
- Modify `src/gateway/schemas.py`: add response models for drive capabilities, media items, transfer jobs, and playback records.
- Modify `src/gateway/api/admin.py`: add read-only endpoints and query helpers.
- Create `tests/api/test_admin_drive_types.py`: verifies provider metadata contract.
- Create `tests/api/test_admin_media_items.py`: verifies media item listing and filtering.
- Create `tests/api/test_admin_transfer_jobs.py`: verifies transfer job listing and filtering.
- Create `tests/api/test_admin_playback_records.py`: verifies playback record listing and filtering.

---

### Task 1: README Product Positioning

**Files:**
- Modify: `README.md`
- Test: shell checks only

- [ ] **Step 1: Write the documentation expectation check**

Run:

```bash
rg -n "泛云盘媒体缓存|NextEmby-like|GD Source-First Playback Gateway" README.md
```

Expected before implementation: the command finds `GD Source-First Playback Gateway` and does not find the new positioning phrases.

- [ ] **Step 2: Replace the README title and first product section**

In `README.md`, replace the title and opening paragraphs through the `## 当前阶段` heading body with this content:

```markdown
# media-pro

一个面向 Emby / Jellyfin 的 NextEmby-like 泛云盘媒体缓存与播放网关。

`media-pro` 的目标不是做单一云盘脚本，也不是 115 专用工具，而是把媒体源、用户云盘、缓存池和播放诊断整合成一个小团队可用的正式产品。管理员配置 OpenList / GD 等媒体源和用户策略，用户绑定自己的云盘账号；播放时系统按 `self -> pool -> source_copy -> source_stream` 决策，优先使用用户已有缓存，其次复用池内缓存，再尝试从媒体源复制到用户云盘，最后回源直连播放。

当前代码基于 FastAPI、SQLAlchemy、SQLite、OpenList、rapid-copy 和可扩展 provider 策略构建。已有能力覆盖 115、139/caiyun、OpenList/GD 媒体源、基础管理后台、管理员登录保护、systemd 部署和测试集。后续方向是继续模仿 NextEmby 的产品体验，但保持 clean-room 实现，不复制 `/root/nextemby` 的私有/反编译源码。

## 当前阶段

当前仓库处于 NextEmby-like 泛云盘产品化的基础阶段：

- 已经具备本地启动、接口联调、数据库持久化、基础播放决策、最小管理页和运维验证能力
- 已经具备可选的管理员登录保护；设置 `GATEWAY_ADMIN_PASSWORD` 后会保护 `/admin` 和 `/api/admin/*`
- 已经具备 115 专用链路和 139/caiyun OpenList-backed 链路的基础实现
- 正在补齐 provider 能力描述、播放诊断、转存历史、媒体列表、正式管理后台和用户中心
- 更适合当前阶段作为自用/小团队技术产品，而不是公开运营系统
```

Keep the existing `## MVP Route Order` section after this replacement.

- [ ] **Step 3: Update the implemented/missing capability bullets**

In `README.md`, under `## 当前已经实现`, ensure the list includes these bullets:

```markdown
- provider strategy registry 基础结构
- 139/caiyun OpenList-backed drive 录入、probe、source_copy 基础能力
- systemd 部署模板和部署说明
```

Under `## 当前还没有实现`, ensure the list includes:

```markdown
- 用户中心、用户登录和用户自助绑定云盘
- 正式产品级管理后台
- provider capability API 与播放/转存诊断读模型
```

Remove duplicated bullets about production logging/monitoring if they appear twice.

- [ ] **Step 4: Verify README positioning**

Run:

```bash
rg -n "NextEmby-like|泛云盘|GD Source-First Playback Gateway" README.md
```

Expected: output includes `NextEmby-like` and `泛云盘`; output no longer includes `# GD Source-First Playback Gateway`.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update product positioning"
```

---

### Task 2: Drive Type Capability API

**Files:**
- Modify: `src/gateway/schemas.py`
- Modify: `src/gateway/api/admin.py`
- Create: `tests/api/test_admin_drive_types.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/api/test_admin_drive_types.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def _client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'drive-types.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(create_app(database_url=database_url))


def test_admin_drive_types_endpoint_returns_provider_capabilities(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/admin/drive-types")

    assert response.status_code == 200
    assert response.json() == [
        {
            "drive_type": "115",
            "label": "115",
            "description": "115 专用用户云盘，保留专用 rapid-copy、池内复用和直链播放能力。",
            "credential_type": "cookie",
            "default_root_dir": "/EmbyCache",
            "capabilities": {
                "can_stream": True,
                "can_source_copy": True,
                "can_pool_copy": True,
                "managed_by_openlist": False,
                "supports_health_probe": True,
                "supports_user_bind": True,
            },
            "credential_fields": [
                {
                    "name": "cookie",
                    "label": "115 Cookie",
                    "secret": True,
                    "required": True,
                    "help_text": "用于 115 专用链路，后端加密保存，接口不会回显明文。",
                }
            ],
        },
        {
            "drive_type": "caiyun",
            "label": "移动云盘 / 139",
            "description": "OpenList-backed 用户云盘，通过 OpenList storage 和 fs/copy 承接源盘复制。",
            "credential_type": "openlist_storage",
            "default_root_dir": "/EmbyCache",
            "capabilities": {
                "can_stream": True,
                "can_source_copy": True,
                "can_pool_copy": False,
                "managed_by_openlist": True,
                "supports_health_probe": True,
                "supports_user_bind": True,
            },
            "credential_fields": [
                {
                    "name": "access_token",
                    "label": "Access Token",
                    "secret": True,
                    "required": True,
                    "help_text": "写入 OpenList 139Yun storage 的 authorization 字段。",
                },
                {
                    "name": "refresh_token",
                    "label": "Refresh Token",
                    "secret": True,
                    "required": False,
                    "help_text": "写入 OpenList 139Yun storage 的 refresh_token 字段。",
                },
                {
                    "name": "account_type",
                    "label": "账号类型",
                    "secret": False,
                    "required": False,
                    "help_text": "默认 personal_new，对应当前 OpenList 139Yun driver 配置。",
                },
            ],
        },
    ]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/api/test_admin_drive_types.py -q
```

Expected: FAIL with `404 Not Found` for `/api/admin/drive-types`.

- [ ] **Step 3: Add capability response schemas**

In `src/gateway/schemas.py`, after `DriveProbeBulkResponse`, add:

```python
class CredentialFieldRead(BaseModel):
    name: str
    label: str
    secret: bool
    required: bool
    help_text: str | None = None


class DriveTypeCapabilitiesRead(BaseModel):
    can_stream: bool
    can_source_copy: bool
    can_pool_copy: bool
    managed_by_openlist: bool
    supports_health_probe: bool
    supports_user_bind: bool


class DriveTypeRead(BaseModel):
    drive_type: str
    label: str
    description: str
    credential_type: str
    default_root_dir: str
    capabilities: DriveTypeCapabilitiesRead
    credential_fields: list[CredentialFieldRead]
```

- [ ] **Step 4: Add the drive type catalog and endpoint**

In `src/gateway/api/admin.py`, extend the schema imports:

```python
from gateway.schemas import (
    CatalogSyncRequest,
    CatalogSyncResponse,
    AdminOverviewRead,
    CredentialFieldRead,
    DriveAccountBulkActionRequest,
    DriveAccountBulkActionResponse,
    DriveAccountCreate,
    DriveAccountDeleteResponse,
    DriveProbeBulkResponse,
    DriveProbeRead,
    DriveAccountRead,
    DriveStatsRead,
    DriveAccountUpdate,
    DriveTypeCapabilitiesRead,
    DriveTypeRead,
    PoolObjectBulkActionRequest,
    PoolObjectBulkActionResponse,
    PoolObjectRead,
    PoolObjectStatsRead,
    UserCreate,
    UserRead,
)
```

Below `router = APIRouter(prefix="/api/admin", tags=["admin"])`, add:

```python
DRIVE_TYPE_CATALOG: tuple[DriveTypeRead, ...] = (
    DriveTypeRead(
        drive_type="115",
        label="115",
        description="115 专用用户云盘，保留专用 rapid-copy、池内复用和直链播放能力。",
        credential_type="cookie",
        default_root_dir="/EmbyCache",
        capabilities=DriveTypeCapabilitiesRead(
            can_stream=True,
            can_source_copy=True,
            can_pool_copy=True,
            managed_by_openlist=False,
            supports_health_probe=True,
            supports_user_bind=True,
        ),
        credential_fields=[
            CredentialFieldRead(
                name="cookie",
                label="115 Cookie",
                secret=True,
                required=True,
                help_text="用于 115 专用链路，后端加密保存，接口不会回显明文。",
            )
        ],
    ),
    DriveTypeRead(
        drive_type="caiyun",
        label="移动云盘 / 139",
        description="OpenList-backed 用户云盘，通过 OpenList storage 和 fs/copy 承接源盘复制。",
        credential_type="openlist_storage",
        default_root_dir="/EmbyCache",
        capabilities=DriveTypeCapabilitiesRead(
            can_stream=True,
            can_source_copy=True,
            can_pool_copy=False,
            managed_by_openlist=True,
            supports_health_probe=True,
            supports_user_bind=True,
        ),
        credential_fields=[
            CredentialFieldRead(
                name="access_token",
                label="Access Token",
                secret=True,
                required=True,
                help_text="写入 OpenList 139Yun storage 的 authorization 字段。",
            ),
            CredentialFieldRead(
                name="refresh_token",
                label="Refresh Token",
                secret=True,
                required=False,
                help_text="写入 OpenList 139Yun storage 的 refresh_token 字段。",
            ),
            CredentialFieldRead(
                name="account_type",
                label="账号类型",
                secret=False,
                required=False,
                help_text="默认 personal_new，对应当前 OpenList 139Yun driver 配置。",
            ),
        ],
    ),
)
```

After the existing stats endpoints, add:

```python
@router.get("/drive-types", response_model=list[DriveTypeRead])
def list_drive_types() -> list[DriveTypeRead]:
    return list(DRIVE_TYPE_CATALOG)
```

- [ ] **Step 5: Run the focused test**

Run:

```bash
uv run pytest tests/api/test_admin_drive_types.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gateway/schemas.py src/gateway/api/admin.py tests/api/test_admin_drive_types.py
git commit -m "feat: expose drive type capabilities"
```

---

### Task 3: Admin Media Items Read API

**Files:**
- Modify: `src/gateway/schemas.py`
- Modify: `src/gateway/api/admin.py`
- Create: `tests/api/test_admin_media_items.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/api/test_admin_media_items.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem


def insert_media(
    session: Session,
    *,
    source_path: str,
    fingerprint: str,
    size: int,
) -> MediaItem:
    media = MediaItem(
        source_path=source_path,
        source_file_id=f"{fingerprint}-id",
        size=size,
        mtime=datetime(2026, 5, 25, 1, 2, tzinfo=timezone.utc),
        fingerprint=fingerprint,
        openlist_path=source_path,
    )
    session.add(media)
    session.flush()
    return media


def test_admin_media_items_endpoint_lists_and_filters_catalog(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'media-items.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        insert_media(
            session,
            source_path="/Movies/Avatar.2009.mkv",
            fingerprint="fp-avatar",
            size=4096,
        )
        insert_media(
            session,
            source_path="/TV/Show.S01E01.mkv",
            fingerprint="fp-show",
            size=2048,
        )
        insert_media(
            session,
            source_path="/Movies/Apollo.1995.mkv",
            fingerprint="fp-apollo",
            size=1024,
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/media-items")
        q_filtered = client.get("/api/admin/media-items", params={"q": "Movies"})
        fingerprint_filtered = client.get(
            "/api/admin/media-items",
            params={"fingerprint": "fp-show"},
        )
        limited = client.get("/api/admin/media-items", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert [item["source_path"] for item in response.json()] == [
        "/Movies/Avatar.2009.mkv",
        "/TV/Show.S01E01.mkv",
        "/Movies/Apollo.1995.mkv",
    ]
    assert response.json()[0] == {
        "id": 1,
        "source_path": "/Movies/Avatar.2009.mkv",
        "source_file_id": "fp-avatar-id",
        "size": 4096,
        "mtime": response.json()[0]["mtime"],
        "fingerprint": "fp-avatar",
        "openlist_path": "/Movies/Avatar.2009.mkv",
    }
    assert [item["id"] for item in q_filtered.json()] == [1, 3]
    assert [item["id"] for item in fingerprint_filtered.json()] == [2]
    assert [item["id"] for item in limited.json()] == [2]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/api/test_admin_media_items.py -q
```

Expected: FAIL with `404 Not Found` for `/api/admin/media-items`.

- [ ] **Step 3: Add the media item response schema**

In `src/gateway/schemas.py`, after `CatalogSyncResponse`, add:

```python
class MediaItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_path: str
    source_file_id: str | None
    size: int
    mtime: datetime | None = None
    fingerprint: str
    openlist_path: str
```

- [ ] **Step 4: Add the endpoint**

In `src/gateway/api/admin.py`, add `MediaItem` to the model imports:

```python
from gateway.models import MediaItem, PlaybackRecord, PoolObject, PoolObjectStatus, User, UserDriveAccount
```

Add `MediaItemRead` to the schema imports.

Below `list_users`, add:

```python
@router.get("/media-items", response_model=list[MediaItemRead])
def list_media_items(
    q: str | None = None,
    fingerprint: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[MediaItemRead]:
    statement = select(MediaItem).order_by(MediaItem.id).offset(offset).limit(limit)
    if q:
        statement = statement.where(MediaItem.source_path.contains(q))
    if fingerprint:
        statement = statement.where(MediaItem.fingerprint == fingerprint)
    media_items = session.scalars(statement).all()
    return [MediaItemRead.model_validate(media_item) for media_item in media_items]
```

- [ ] **Step 5: Run focused and nearby tests**

Run:

```bash
uv run pytest tests/api/test_admin_media_items.py tests/api/test_admin_catalog_sync.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gateway/schemas.py src/gateway/api/admin.py tests/api/test_admin_media_items.py
git commit -m "feat: add admin media item listing"
```

---

### Task 4: Admin Transfer Jobs Read API

**Files:**
- Modify: `src/gateway/schemas.py`
- Modify: `src/gateway/api/admin.py`
- Create: `tests/api/test_admin_transfer_jobs.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/api/test_admin_transfer_jobs.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem, TransferJob, User


def insert_user(session: Session, username: str) -> User:
    user = User(username=username, status="active")
    session.add(user)
    session.flush()
    return user


def insert_media(session: Session, source_path: str, fingerprint: str) -> MediaItem:
    media = MediaItem(
        source_path=source_path,
        source_file_id=f"{fingerprint}-id",
        size=2048,
        fingerprint=fingerprint,
        openlist_path=source_path,
    )
    session.add(media)
    session.flush()
    return media


def test_admin_transfer_jobs_endpoint_lists_and_filters_attempts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'transfer-jobs.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                TransferJob(
                    media_id=movie.id,
                    donor_user_id=bob.id,
                    target_user_id=alice.id,
                    route_stage="try_pool",
                    idempotency_key="pool-1",
                    status="failed",
                    error_code="missing_donor_file",
                    attempt_no=1,
                ),
                TransferJob(
                    media_id=movie.id,
                    donor_user_id=None,
                    target_user_id=alice.id,
                    route_stage="try_source_copy",
                    idempotency_key="source-1",
                    status="succeeded",
                    error_code=None,
                    attempt_no=1,
                ),
                TransferJob(
                    media_id=episode.id,
                    donor_user_id=None,
                    target_user_id=bob.id,
                    route_stage="try_source_copy",
                    idempotency_key="source-2",
                    status="failed",
                    error_code="openlist_copy_failed",
                    attempt_no=2,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/transfer-jobs")
        status_filtered = client.get("/api/admin/transfer-jobs", params={"status": "failed"})
        stage_filtered = client.get(
            "/api/admin/transfer-jobs",
            params={"route_stage": "try_pool"},
        )
        target_filtered = client.get(
            "/api/admin/transfer-jobs",
            params={"target_user_id": alice.id},
        )
        limited = client.get("/api/admin/transfer-jobs", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "media_id": 1,
            "donor_user_id": 2,
            "target_user_id": 1,
            "route_stage": "try_pool",
            "idempotency_key": "pool-1",
            "status": "failed",
            "error_code": "missing_donor_file",
            "attempt_no": 1,
        },
        {
            "id": 2,
            "media_id": 1,
            "donor_user_id": None,
            "target_user_id": 1,
            "route_stage": "try_source_copy",
            "idempotency_key": "source-1",
            "status": "succeeded",
            "error_code": None,
            "attempt_no": 1,
        },
        {
            "id": 3,
            "media_id": 2,
            "donor_user_id": None,
            "target_user_id": 2,
            "route_stage": "try_source_copy",
            "idempotency_key": "source-2",
            "status": "failed",
            "error_code": "openlist_copy_failed",
            "attempt_no": 2,
        },
    ]
    assert [item["id"] for item in status_filtered.json()] == [1, 3]
    assert [item["id"] for item in stage_filtered.json()] == [1]
    assert [item["id"] for item in target_filtered.json()] == [1, 2]
    assert [item["id"] for item in limited.json()] == [2]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/api/test_admin_transfer_jobs.py -q
```

Expected: FAIL with `404 Not Found` for `/api/admin/transfer-jobs`.

- [ ] **Step 3: Add the transfer job response schema**

In `src/gateway/schemas.py`, after `PoolObjectStatsRead`, add:

```python
class TransferJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int
    donor_user_id: int | None
    target_user_id: int
    route_stage: str
    idempotency_key: str
    status: str
    error_code: str | None
    attempt_no: int
```

- [ ] **Step 4: Add the endpoint**

In `src/gateway/api/admin.py`, add `TransferJob` to the model imports and `TransferJobRead` to schema imports.

Below `list_pool_objects`, add:

```python
@router.get("/transfer-jobs", response_model=list[TransferJobRead])
def list_transfer_jobs(
    media_id: int | None = None,
    donor_user_id: int | None = None,
    target_user_id: int | None = None,
    route_stage: str | None = None,
    status_name: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[TransferJobRead]:
    statement = select(TransferJob).order_by(TransferJob.id).offset(offset).limit(limit)
    if media_id is not None:
        statement = statement.where(TransferJob.media_id == media_id)
    if donor_user_id is not None:
        statement = statement.where(TransferJob.donor_user_id == donor_user_id)
    if target_user_id is not None:
        statement = statement.where(TransferJob.target_user_id == target_user_id)
    if route_stage is not None:
        statement = statement.where(TransferJob.route_stage == route_stage)
    if status_name is not None:
        statement = statement.where(TransferJob.status == status_name)
    jobs = session.scalars(statement).all()
    return [TransferJobRead.model_validate(job) for job in jobs]
```

- [ ] **Step 5: Run focused and nearby tests**

Run:

```bash
uv run pytest tests/api/test_admin_transfer_jobs.py tests/api/test_admin_overview.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gateway/schemas.py src/gateway/api/admin.py tests/api/test_admin_transfer_jobs.py
git commit -m "feat: add admin transfer job listing"
```

---

### Task 5: Admin Playback Records Read API

**Files:**
- Modify: `src/gateway/schemas.py`
- Modify: `src/gateway/api/admin.py`
- Create: `tests/api/test_admin_playback_records.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/api/test_admin_playback_records.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.main import create_app
from gateway.models import Base, MediaItem, PlaybackRecord, TransferRoute, User


def insert_user(session: Session, username: str) -> User:
    user = User(username=username, status="active")
    session.add(user)
    session.flush()
    return user


def insert_media(session: Session, source_path: str, fingerprint: str) -> MediaItem:
    media = MediaItem(
        source_path=source_path,
        source_file_id=f"{fingerprint}-id",
        size=2048,
        fingerprint=fingerprint,
        openlist_path=source_path,
    )
    session.add(media)
    session.flush()
    return media


def test_admin_playback_records_endpoint_lists_and_filters_routes(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-records.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        alice = insert_user(session, "alice")
        bob = insert_user(session, "bob")
        movie = insert_media(session, "/Movies/Movie.2024.mkv", "fp-movie")
        episode = insert_media(session, "/TV/Show.S01E01.mkv", "fp-episode")
        session.add_all(
            [
                PlaybackRecord(
                    user_id=alice.id,
                    media_id=movie.id,
                    route=TransferRoute.SELF,
                    success=True,
                    latency_ms=11,
                ),
                PlaybackRecord(
                    user_id=alice.id,
                    media_id=episode.id,
                    route=TransferRoute.SOURCE_COPY,
                    success=True,
                    latency_ms=22,
                ),
                PlaybackRecord(
                    user_id=bob.id,
                    media_id=movie.id,
                    route=TransferRoute.SOURCE_STREAM,
                    success=False,
                    latency_ms=33,
                ),
            ]
        )
        session.commit()

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get("/api/admin/playback-records")
        user_filtered = client.get(
            "/api/admin/playback-records",
            params={"user_id": alice.id},
        )
        route_filtered = client.get(
            "/api/admin/playback-records",
            params={"route": "source_stream"},
        )
        success_filtered = client.get(
            "/api/admin/playback-records",
            params={"success": "false"},
        )
        limited = client.get("/api/admin/playback-records", params={"limit": 1, "offset": 1})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "user_id": 1,
            "media_id": 1,
            "route": "self",
            "success": True,
            "latency_ms": 11,
        },
        {
            "id": 2,
            "user_id": 1,
            "media_id": 2,
            "route": "source_copy",
            "success": True,
            "latency_ms": 22,
        },
        {
            "id": 3,
            "user_id": 2,
            "media_id": 1,
            "route": "source_stream",
            "success": False,
            "latency_ms": 33,
        },
    ]
    assert [item["id"] for item in user_filtered.json()] == [1, 2]
    assert [item["id"] for item in route_filtered.json()] == [3]
    assert [item["id"] for item in success_filtered.json()] == [3]
    assert [item["id"] for item in limited.json()] == [2]
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run pytest tests/api/test_admin_playback_records.py -q
```

Expected: FAIL with `404 Not Found` for `/api/admin/playback-records`.

- [ ] **Step 3: Add the playback record response schema**

In `src/gateway/schemas.py`, after `TransferJobRead`, add:

```python
class PlaybackRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    media_id: int
    route: str
    success: bool
    latency_ms: int
```

- [ ] **Step 4: Add the endpoint**

In `src/gateway/api/admin.py`, add `TransferRoute` to model imports and `PlaybackRecordRead` to schema imports.

Below `admin_stats`, add:

```python
@router.get("/playback-records", response_model=list[PlaybackRecordRead])
def list_playback_records(
    user_id: int | None = None,
    media_id: int | None = None,
    route: TransferRoute | None = None,
    success: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[PlaybackRecordRead]:
    statement = select(PlaybackRecord).order_by(PlaybackRecord.id).offset(offset).limit(limit)
    if user_id is not None:
        statement = statement.where(PlaybackRecord.user_id == user_id)
    if media_id is not None:
        statement = statement.where(PlaybackRecord.media_id == media_id)
    if route is not None:
        statement = statement.where(PlaybackRecord.route == route)
    if success is not None:
        statement = statement.where(PlaybackRecord.success.is_(success))
    records = session.scalars(statement).all()
    return [PlaybackRecordRead.model_validate(record) for record in records]
```

If Pydantic serializes `route` as enum objects instead of strings, change `PlaybackRecordRead.route` to:

```python
route: TransferRoute
```

and import `TransferRoute` in `schemas.py`:

```python
from gateway.models import PoolObjectStatus, TransferRoute
```

- [ ] **Step 5: Run focused and nearby tests**

Run:

```bash
uv run pytest tests/api/test_admin_playback_records.py tests/api/test_admin_stats.py tests/api/test_playback_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gateway/schemas.py src/gateway/api/admin.py tests/api/test_admin_playback_records.py
git commit -m "feat: add admin playback record listing"
```

---

### Task 6: Full Verification

**Files:**
- No source edits expected

- [ ] **Step 1: Run focused API suite**

Run:

```bash
uv run pytest tests/api -q
```

Expected: all API tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: full suite passes.

- [ ] **Step 3: Check branch state**

Run:

```bash
git status --short --branch
```

Expected: clean working tree, branch ahead by the number of commits created from this plan.

- [ ] **Step 4: Record implementation outcome**

Add a short note to the final response with:

```text
Implemented:
- README positioning refresh
- /api/admin/drive-types
- /api/admin/media-items
- /api/admin/transfer-jobs
- /api/admin/playback-records

Verification:
- uv run pytest tests/api -q
- uv run pytest
```

Do not create an additional commit for this note.

---

## Self-Review

Spec coverage:

- README positioning refresh covers the product positioning requirement.
- Drive type capability API covers provider metadata needed by the future UI and user center.
- Media item listing covers the admin media source read model.
- Transfer job listing covers source/pool copy attempt diagnostics.
- Playback record listing covers final route diagnostics.

Scope boundaries:

- The plan intentionally leaves admin UI productization and user center implementation to later plans because those depend on these read APIs.
- The plan does not change database schema because all required tables and columns already exist.
- The plan does not copy or depend on `/root/nextemby`.

Verification:

- Each endpoint has a failing test first.
- Each task has a focused pytest command.
- The final task runs the full API suite and full test suite.
