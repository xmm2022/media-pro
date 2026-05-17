# Real Environment Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前后端 MVP 打通到真实 OpenList / rapid-copy / catalog / playback / stats 链路，并提供可重复执行的联调脚本与中文操作文档。

**Architecture:** 保持现有 FastAPI + SQLAlchemy 结构不大改，先补全真实环境配置与脚本输入，再在适配器层吸收真实响应差异，随后新增最小 catalog 入库与 playback 编排层，让 `/api/playback/{media_id}` 从数据库与 OpenList 真实数据构造决策并落库 `PlaybackRecord`。真实联调验证独立成新脚本，不把 `verify_mvp.py` 继续膨胀成复杂工具。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic Settings, httpx, pytest, respx, uv

---

## File Map

- `src/gateway/config.py`: 增加真实联调阶段所需环境变量。
- `src/gateway/script_inputs.py`: 集中校验脚本探针输入，避免脚本里散落硬编码。
- `.env.example`: 增补真实环境联调用到的示例变量。
- `scripts/validate_openlist_stream.py`: 从 settings/helper 读取真实探针路径。
- `scripts/validate_rapid_copy.py`: 从 settings/helper 读取 donor/target cookie 与路径。
- `src/gateway/integrations/openlist_client.py`: 兼容真实 OpenList 的字段差异，并提供 `aclose()`。
- `src/gateway/integrations/rapid_copy_client.py`: 做网络错误与 HTTP 错误映射，并提供 `aclose()`。
- `src/gateway/catalog_sync.py`: 新增最小 catalog 同步服务，负责把 OpenList 列表写入 `MediaItem`。
- `src/gateway/schemas.py`: 新增 catalog sync 请求/响应模型。
- `src/gateway/api/admin.py`: 新增 `POST /api/admin/catalog/sync`。
- `src/gateway/playback.py`: 支持把真实 pool/source_copy URL 传进决策层，消除占位 URL。
- `src/gateway/playback_resolver.py`: 新增 playback 编排层，负责查 DB、调 OpenList、持久化 `PlaybackRecord`。
- `src/gateway/api/playback.py`: 接入 `PlaybackResolver`，按 `user_id + media_id` 返回真实结果。
- `src/gateway/real_integration.py`: 封装真实联调 smoke 流程，供脚本调用。
- `scripts/verify_real_integration.py`: 执行真实环境 smoke 验证。
- `README.md`: 补全真实环境联调章节、命令与验收步骤。
- `tests/config/test_settings.py`: 验证新环境变量可被 `Settings` 正确读取。
- `tests/scripts/test_script_inputs.py`: 验证脚本探针输入的校验逻辑。
- `tests/integrations/test_openlist_client.py`: 覆盖 OpenList 真实字段差异。
- `tests/integrations/test_rapid_copy_client.py`: 覆盖 rapid-copy 错误映射。
- `tests/catalog/test_catalog_sync_service.py`: 覆盖 catalog upsert。
- `tests/api/test_admin_catalog_sync.py`: 覆盖 catalog sync 接口。
- `tests/playback/test_playback_service.py`: 覆盖 route-specific URL 透传。
- `tests/playback/test_playback_resolver.py`: 覆盖 DB 驱动的 playback 编排与落库。
- `tests/api/test_playback_api.py`: 覆盖 `/api/playback/{media_id}` 真实数据链路。
- `tests/scripts/test_verify_real_integration.py`: 覆盖真实联调 smoke 编排与 README 命令说明。

### Task 1: Real Config And Script Inputs

**Files:**
- Create: `src/gateway/script_inputs.py`
- Create: `tests/config/test_settings.py`
- Create: `tests/scripts/test_script_inputs.py`
- Modify: `src/gateway/config.py`
- Modify: `.env.example`
- Modify: `scripts/validate_openlist_stream.py`
- Modify: `scripts/validate_rapid_copy.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing tests**

```python
# tests/config/test_settings.py
from gateway.config import Settings


def test_settings_load_real_integration_fields_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_OPENLIST_PROBE_PATH", "/Movies/real.mkv")
    monkeypatch.setenv("GATEWAY_CATALOG_ROOT_PATH", "/Movies")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_DONOR_COOKIE", "UID=donor")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_TARGET_COOKIE", "UID=target")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_SOURCE_PATH", "/Movies/real.mkv")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_TARGET_PATH", "/EmbyCache/real.mkv")

    settings = Settings(_env_file=None)

    assert settings.openlist_probe_path == "/Movies/real.mkv"
    assert settings.catalog_root_path == "/Movies"
    assert settings.rapid_copy_target_path == "/EmbyCache/real.mkv"
```

```python
# tests/scripts/test_script_inputs.py
import pytest

from gateway.config import Settings
from gateway.script_inputs import RapidCopyProbe, build_openlist_probe_path, build_rapid_copy_probe


def test_build_openlist_probe_path_returns_settings_value() -> None:
    app_settings = Settings(_env_file=None, openlist_probe_path="/Movies/real.mkv")

    assert build_openlist_probe_path(app_settings) == "/Movies/real.mkv"


def test_build_rapid_copy_probe_rejects_missing_required_values() -> None:
    app_settings = Settings(
        _env_file=None,
        rapid_copy_donor_cookie="",
        rapid_copy_target_cookie="",
        rapid_copy_source_path="/Movies/real.mkv",
        rapid_copy_target_path="/EmbyCache/real.mkv",
    )

    with pytest.raises(ValueError, match="GATEWAY_RAPID_COPY_DONOR_COOKIE"):
        build_rapid_copy_probe(app_settings)


def test_build_rapid_copy_probe_returns_env_driven_payload() -> None:
    app_settings = Settings(
        _env_file=None,
        rapid_copy_donor_cookie="UID=donor",
        rapid_copy_target_cookie="UID=target",
        rapid_copy_source_path="/Movies/real.mkv",
        rapid_copy_target_path="/EmbyCache/real.mkv",
    )

    assert build_rapid_copy_probe(app_settings) == RapidCopyProbe(
        donor_cookie="UID=donor",
        target_cookie="UID=target",
        source_path="/Movies/real.mkv",
        target_path="/EmbyCache/real.mkv",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/config/test_settings.py tests/scripts/test_script_inputs.py -v`

Expected: FAIL because `Settings` 里还没有这些字段，且 `gateway.script_inputs` 模块还不存在。

- [ ] **Step 3: Write minimal implementation**

```python
# src/gateway/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GD Source-First Playback Gateway"
    openlist_base_url: str = Field("http://localhost:5244")
    openlist_token: str = Field("")
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

```python
# src/gateway/script_inputs.py
from dataclasses import dataclass

from gateway.config import Settings


@dataclass(frozen=True, slots=True)
class RapidCopyProbe:
    donor_cookie: str
    target_cookie: str
    source_path: str
    target_path: str


def build_openlist_probe_path(app_settings: Settings) -> str:
    if not app_settings.openlist_probe_path:
        raise ValueError("GATEWAY_OPENLIST_PROBE_PATH must not be empty")
    return app_settings.openlist_probe_path


def build_rapid_copy_probe(app_settings: Settings) -> RapidCopyProbe:
    required_values = {
        "GATEWAY_RAPID_COPY_DONOR_COOKIE": app_settings.rapid_copy_donor_cookie,
        "GATEWAY_RAPID_COPY_TARGET_COOKIE": app_settings.rapid_copy_target_cookie,
        "GATEWAY_RAPID_COPY_SOURCE_PATH": app_settings.rapid_copy_source_path,
        "GATEWAY_RAPID_COPY_TARGET_PATH": app_settings.rapid_copy_target_path,
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"Missing probe settings: {', '.join(missing)}")
    return RapidCopyProbe(
        donor_cookie=app_settings.rapid_copy_donor_cookie,
        target_cookie=app_settings.rapid_copy_target_cookie,
        source_path=app_settings.rapid_copy_source_path,
        target_path=app_settings.rapid_copy_target_path,
    )
```

```python
# scripts/validate_openlist_stream.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.openlist_client import OpenListClient
from gateway.script_inputs import build_openlist_probe_path


async def main() -> None:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    info = await client.get_stream_info(build_openlist_probe_path(settings))
    print({"url": info.raw_url, "accepts_ranges": info.accepts_ranges})


if __name__ == "__main__":
    asyncio.run(main())
```

```python
# scripts/validate_rapid_copy.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.rapid_copy_client import RapidCopyClient
from gateway.script_inputs import build_rapid_copy_probe


async def main() -> None:
    probe = build_rapid_copy_probe(settings)
    client = RapidCopyClient(settings.rapid_copy_base_url)
    result = await client.copy(
        probe.donor_cookie,
        probe.target_cookie,
        probe.source_path,
        probe.target_path,
    )
    print({"ok": result.ok, "error_code": result.error_code})


if __name__ == "__main__":
    asyncio.run(main())
```

```dotenv
# .env.example
GATEWAY_DATABASE_URL=sqlite:///./gateway.db
GATEWAY_COOKIE_SECRET=replace-me-with-a-long-random-secret
GATEWAY_OPENLIST_BASE_URL=http://127.0.0.1:5244
GATEWAY_OPENLIST_TOKEN=
GATEWAY_RAPID_COPY_BASE_URL=http://127.0.0.1:9000
GATEWAY_OPENLIST_PROBE_PATH=/Movies/sample.mkv
GATEWAY_CATALOG_ROOT_PATH=/Movies
GATEWAY_RAPID_COPY_DONOR_COOKIE=
GATEWAY_RAPID_COPY_TARGET_COOKIE=
GATEWAY_RAPID_COPY_SOURCE_PATH=/Movies/sample.mkv
GATEWAY_RAPID_COPY_TARGET_PATH=/EmbyCache/sample.mkv
```

```markdown
<!-- README.md -->
## 真实联调必填变量

- `GATEWAY_OPENLIST_PROBE_PATH`
- `GATEWAY_CATALOG_ROOT_PATH`
- `GATEWAY_RAPID_COPY_DONOR_COOKIE`
- `GATEWAY_RAPID_COPY_TARGET_COOKIE`
- `GATEWAY_RAPID_COPY_SOURCE_PATH`
- `GATEWAY_RAPID_COPY_TARGET_PATH`
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/config/test_settings.py tests/scripts/test_script_inputs.py -v`

Expected: PASS with the new settings fields and helper module.

- [ ] **Step 5: Commit**

```bash
git add .env.example README.md src/gateway/config.py src/gateway/script_inputs.py scripts/validate_openlist_stream.py scripts/validate_rapid_copy.py tests/config/test_settings.py tests/scripts/test_script_inputs.py
git commit -m "feat: add real integration settings and script inputs"
```

### Task 2: Harden OpenList Parsing For Real Responses

**Files:**
- Modify: `src/gateway/integrations/openlist_client.py`
- Modify: `tests/integrations/test_openlist_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/test_openlist_client.py
import json

import httpx
import pytest
import respx

from gateway.integrations.openlist_client import CatalogRow, OpenListClient


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_accepts_raw_url_and_boolean_range_flag() -> None:
    respx.post("http://openlist.local/api/fs/link").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "raw_url": "https://drive.local/raw.mkv",
                    "content_length": "2048",
                    "accept_ranges": True,
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    info = await client.get_stream_info("/Movies/raw.mkv")

    assert info.raw_url == "https://drive.local/raw.mkv"
    assert info.content_length == 2048
    assert info.accepts_ranges is True


@pytest.mark.asyncio
@respx.mock
async def test_openlist_client_builds_catalog_path_from_name_when_path_missing() -> None:
    route = respx.post("http://openlist.local/api/fs/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "name": "Movie.2024.mkv",
                            "size": 2048,
                            "id": 12,
                            "modified_at": "2026-05-17T00:00:00Z",
                        }
                    ]
                }
            },
        )
    )

    client = OpenListClient("http://openlist.local", "token")
    rows = await client.list_catalog("/Movies")

    assert route.called is True
    assert rows == [
        CatalogRow(
            path="/Movies/Movie.2024.mkv",
            size=2048,
            file_id="12",
            mtime="2026-05-17T00:00:00Z",
        )
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integrations/test_openlist_client.py::test_openlist_client_accepts_raw_url_and_boolean_range_flag tests/integrations/test_openlist_client.py::test_openlist_client_builds_catalog_path_from_name_when_path_missing -v`

Expected: FAIL because `OpenListClient` 目前只识别 `url` / `accept_ranges == "bytes"` / `row["path"]` / `row["modified"]`。

- [ ] **Step 3: Write minimal implementation**

```python
# src/gateway/integrations/openlist_client.py
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class CatalogRow:
    path: str
    size: int
    file_id: str | None
    mtime: str | None


@dataclass(slots=True)
class StreamInfo:
    raw_url: str
    content_length: int | None
    accepts_ranges: bool


class OpenListClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token} if token else {},
            timeout=5.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _coerce_int(self, value: object) -> int | None:
        if value is None:
            return None
        return int(value)

    def _coerce_ranges(self, value: object) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() == "bytes"

    def _normalize_catalog_path(self, root_path: str, row: dict[str, object]) -> str:
        raw_path = row.get("path")
        if raw_path:
            return str(raw_path)
        raw_name = str(row.get("name") or "").strip("/")
        if not raw_name:
            raise ValueError("openlist catalog row missing path")
        return f"{root_path.rstrip('/')}/{raw_name}"

    def _normalize_mtime(self, row: dict[str, object]) -> str | None:
        for key in ("modified", "modified_at", "updated_at"):
            value = row.get(key)
            if value:
                return str(value)
        return None

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        response = await self._client.post("/api/fs/link", json={"path": source_path})
        response.raise_for_status()
        data = response.json().get("data") or {}
        raw_url = data.get("raw_url") or data.get("url")
        if not raw_url:
            raise ValueError("openlist stream response missing url")
        return StreamInfo(
            raw_url=str(raw_url),
            content_length=self._coerce_int(data.get("content_length")),
            accepts_ranges=self._coerce_ranges(data.get("accept_ranges")),
        )

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        response = await self._client.post("/api/fs/list", json={"path": root_path})
        response.raise_for_status()
        rows = response.json()["data"]["content"]
        return [
            CatalogRow(
                path=self._normalize_catalog_path(root_path, row),
                size=int(row.get("size") or 0),
                file_id=str(row["id"]) if row.get("id") is not None else None,
                mtime=self._normalize_mtime(row),
            )
            for row in rows
            if not row.get("is_dir", False)
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integrations/test_openlist_client.py -v`

Expected: PASS for the existing coverage plus the new real-response normalization cases.

- [ ] **Step 5: Commit**

```bash
git add src/gateway/integrations/openlist_client.py tests/integrations/test_openlist_client.py
git commit -m "feat: harden openlist response parsing"
```

### Task 3: Harden Rapid-Copy Error Mapping

**Files:**
- Modify: `src/gateway/integrations/rapid_copy_client.py`
- Modify: `tests/integrations/test_rapid_copy_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integrations/test_rapid_copy_client.py
import httpx
import pytest
import respx

from gateway.integrations.rapid_copy_client import RapidCopyClient


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_connect_error_to_service_unreachable() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        side_effect=httpx.ConnectError("rapid-copy offline")
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "service_unreachable"
    assert "rapid-copy offline" in result.detail


@pytest.mark.asyncio
@respx.mock
async def test_rapid_copy_client_maps_422_to_invalid_request() -> None:
    respx.post("http://rapid-copy.local/copy").mock(
        return_value=httpx.Response(422, json={"detail": "bad source path"})
    )

    client = RapidCopyClient("http://rapid-copy.local")
    result = await client.copy(
        donor_cookie="cookie-a",
        target_cookie="cookie-b",
        source_path="/Movies/movie.mkv",
        target_path="/EmbyCache/movie.mkv",
    )

    assert result.ok is False
    assert result.error_code == "invalid_request"
    assert result.detail == "bad source path"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integrations/test_rapid_copy_client.py::test_rapid_copy_client_maps_connect_error_to_service_unreachable tests/integrations/test_rapid_copy_client.py::test_rapid_copy_client_maps_422_to_invalid_request -v`

Expected: FAIL because `RapidCopyResult` 还没有 `detail` 字段，也没有网络错误与 422 的映射逻辑。

- [ ] **Step 3: Write minimal implementation**

```python
# src/gateway/integrations/rapid_copy_client.py
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class RapidCopyResult:
    ok: bool
    error_code: str | None
    target_path: str | None = None
    detail: str | None = None


class RapidCopyClient:
    _STATUS_MAP = {
        400: "invalid_request",
        401: "permission_denied",
        403: "permission_denied",
        404: "endpoint_not_found",
        409: "target_conflict",
        422: "invalid_request",
    }

    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=2.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _json_payload(self, response: httpx.Response) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    async def copy(
        self,
        donor_cookie: str,
        target_cookie: str,
        source_path: str,
        target_path: str,
    ) -> RapidCopyResult:
        try:
            response = await self._client.post(
                "/copy",
                json={
                    "donor_cookie": donor_cookie,
                    "target_cookie": target_cookie,
                    "source_path": source_path,
                    "target_path": target_path,
                },
            )
        except httpx.HTTPError as exc:
            return RapidCopyResult(
                ok=False,
                error_code="service_unreachable",
                detail=str(exc),
            )

        payload = self._json_payload(response)
        if response.status_code >= 400:
            mapped_error = payload.get("error") or self._STATUS_MAP.get(
                response.status_code,
                "upstream_error",
            )
            detail = payload.get("detail")
            return RapidCopyResult(
                ok=False,
                error_code=str(mapped_error),
                detail=str(detail) if detail else None,
            )

        return RapidCopyResult(
            ok=True,
            error_code=None,
            target_path=str(payload["target_path"]),
            detail=None,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integrations/test_rapid_copy_client.py -v`

Expected: PASS for success, explicit error, network unreachable, and invalid request cases.

- [ ] **Step 5: Commit**

```bash
git add src/gateway/integrations/rapid_copy_client.py tests/integrations/test_rapid_copy_client.py
git commit -m "feat: harden rapid copy error mapping"
```

### Task 4: Add Minimal Catalog Sync And Admin Endpoint

**Files:**
- Create: `src/gateway/catalog_sync.py`
- Create: `tests/catalog/test_catalog_sync_service.py`
- Create: `tests/api/test_admin_catalog_sync.py`
- Modify: `src/gateway/schemas.py`
- Modify: `src/gateway/api/admin.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/catalog/test_catalog_sync_service.py
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
from gateway.integrations.openlist_client import CatalogRow
from gateway.models import Base, MediaItem


class StubOpenListClient:
    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        assert root_path == "/Movies"
        return [
            CatalogRow(
                path="/Movies/Movie.2024.mkv",
                size=2048,
                file_id="gd-1",
                mtime="2026-05-17T00:00:00Z",
            )
        ]


@pytest.mark.asyncio
async def test_catalog_sync_service_upserts_media_items(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'catalog-sync.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    service = CatalogSyncService(CatalogService(), StubOpenListClient())

    with Session(engine) as session:
        first = await service.sync_root(session, "/Movies")
        second = await service.sync_root(session, "/Movies")
        media = session.execute(select(MediaItem)).scalar_one()

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 0
    assert second.updated == 1
    assert media.openlist_path == "/Movies/Movie.2024.mkv"
```

```python
# tests/api/test_admin_catalog_sync.py
from pathlib import Path

import gateway.api.admin as admin_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import CatalogRow
from gateway.main import create_app
from gateway.models import Base, MediaItem


class StubOpenListClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        assert root_path == "/Movies"
        return [
            CatalogRow(
                path="/Movies/Movie.2024.mkv",
                size=2048,
                file_id="gd-1",
                mtime="2026-05-17T00:00:00Z",
            )
        ]

    async def aclose(self) -> None:
        return None


def test_admin_catalog_sync_endpoint_persists_media(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'admin-catalog.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(admin_module, "OpenListClient", StubOpenListClient)

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.post("/api/admin/catalog/sync", json={"root_path": "/Movies"})

    assert response.status_code == 200
    assert response.json() == {"created": 1, "updated": 0}

    with Session(engine) as session:
        media = session.execute(select(MediaItem)).scalar_one()

    assert media.fingerprint == "2048:movie.2024:mkv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/catalog/test_catalog_sync_service.py tests/api/test_admin_catalog_sync.py -v`

Expected: FAIL because `CatalogSyncService` 与 `/api/admin/catalog/sync` 还不存在。

- [ ] **Step 3: Write minimal implementation**

```python
# src/gateway/catalog_sync.py
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.catalog import CatalogEntry, CatalogService
from gateway.integrations.openlist_client import OpenListClient
from gateway.models import MediaItem


@dataclass(slots=True)
class CatalogSyncSummary:
    created: int
    updated: int


class CatalogSyncService:
    def __init__(self, catalog_service: CatalogService, openlist_client: OpenListClient) -> None:
        self._catalog_service = catalog_service
        self._openlist_client = openlist_client

    async def sync_root(self, session: Session, root_path: str) -> CatalogSyncSummary:
        rows = await self._openlist_client.list_catalog(root_path)
        created = 0
        updated = 0
        for row in rows:
            payload = self._catalog_service.to_media_item(
                CatalogEntry(
                    source_path=row.path,
                    source_file_id=row.file_id,
                    size=row.size,
                    mtime=row.mtime,
                )
            )
            media = session.scalar(select(MediaItem).where(MediaItem.source_path == row.path))
            if media is None:
                session.add(MediaItem(**payload))
                created += 1
                continue
            for field_name, value in payload.items():
                setattr(media, field_name, value)
            updated += 1
        session.commit()
        return CatalogSyncSummary(created=created, updated=updated)
```

```python
# src/gateway/schemas.py
from pydantic import BaseModel, ConfigDict


class CatalogSyncRequest(BaseModel):
    root_path: str


class CatalogSyncResponse(BaseModel):
    created: int
    updated: int
```

```python
# src/gateway/api/admin.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
from gateway.config import settings
from gateway.db import get_session
from gateway.integrations.openlist_client import OpenListClient
from gateway.models import PlaybackRecord, User, UserDriveAccount
from gateway.schemas import (
    CatalogSyncRequest,
    CatalogSyncResponse,
    DriveAccountCreate,
    DriveAccountRead,
    UserCreate,
    UserRead,
)


@router.post("/catalog/sync", response_model=CatalogSyncResponse)
async def sync_catalog(
    payload: CatalogSyncRequest,
    session: Session = Depends(get_session),
) -> CatalogSyncResponse:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    service = CatalogSyncService(CatalogService(), client)
    try:
        summary = await service.sync_root(session, payload.root_path)
    finally:
        await client.aclose()
    return CatalogSyncResponse(created=summary.created, updated=summary.updated)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/catalog/test_catalog_sync_service.py tests/api/test_admin_catalog_sync.py -v`

Expected: PASS and `MediaItem` rows are persisted from the stubbed OpenList listing.

- [ ] **Step 5: Commit**

```bash
git add src/gateway/catalog_sync.py src/gateway/schemas.py src/gateway/api/admin.py tests/catalog/test_catalog_sync_service.py tests/api/test_admin_catalog_sync.py
git commit -m "feat: add minimal catalog sync flow"
```

### Task 5: Make Playback API Consume Real Media Data

**Files:**
- Create: `src/gateway/playback_resolver.py`
- Create: `tests/playback/test_playback_resolver.py`
- Modify: `src/gateway/playback.py`
- Modify: `src/gateway/api/playback.py`
- Modify: `tests/playback/test_playback_service.py`
- Modify: `tests/api/test_playback_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/playback/test_playback_service.py
from gateway.playback import PlaybackDecision, PlaybackService


def test_playback_service_uses_supplied_pool_stream_url() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit=None,
        donor_available=True,
        source_copy_supported=True,
        source_stream_url="https://openlist.local/source.mkv",
        pool_stream_url="https://target.local/pool.mkv",
    )

    assert decision == PlaybackDecision(route="pool", stream_url="https://target.local/pool.mkv")
```

```python
# tests/playback/test_playback_resolver.py
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.models import Base, MediaItem, PlaybackRecord, TransferRoute, User
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
```

```python
# tests/api/test_playback_api.py
from pathlib import Path

import gateway.api.playback as playback_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.main import create_app
from gateway.models import Base, MediaItem, User


class StubOpenListClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        assert source_path == "/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://drive.local/Movie.2024.mkv",
            content_length=2048,
            accepts_ranges=True,
        )

    async def aclose(self) -> None:
        return None


def test_playback_api_reads_media_from_database(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-api.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)

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
        user_id = user.id
        media_id = media.id

    with TestClient(create_app(database_url=database_url)) as client:
        response = client.get(f"/api/playback/{media_id}", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": user_id,
        "media_id": media_id,
        "route": "source_stream",
        "stream_url": "https://drive.local/Movie.2024.mkv",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/playback/test_playback_service.py::test_playback_service_uses_supplied_pool_stream_url tests/playback/test_playback_resolver.py::test_playback_resolver_returns_real_source_stream_and_persists_record tests/api/test_playback_api.py::test_playback_api_reads_media_from_database -v`

Expected: FAIL because `PlaybackService` 还不接受 route-specific URL，`PlaybackResolver` 不存在，`/api/playback/{media_id}` 也还没有读数据库。

- [ ] **Step 3: Write minimal implementation**

```python
# src/gateway/playback.py
from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackDecision:
    route: str
    stream_url: str


class PlaybackService:
    def __init__(self, total_budget_ms: int = 2000) -> None:
        self.total_budget_ms = total_budget_ms

    def resolve(
        self,
        self_hit: str | None,
        donor_available: bool,
        source_copy_supported: bool,
        source_stream_url: str,
        pool_stream_url: str | None = None,
        source_copy_stream_url: str | None = None,
        elapsed_ms: int = 0,
    ) -> PlaybackDecision:
        if self_hit:
            return PlaybackDecision(route="self", stream_url=self_hit)
        if elapsed_ms >= self.total_budget_ms:
            return PlaybackDecision(route="source_stream", stream_url=source_stream_url)
        if donor_available:
            return PlaybackDecision(route="pool", stream_url=pool_stream_url or source_stream_url)
        if source_copy_supported:
            return PlaybackDecision(
                route="source_copy",
                stream_url=source_copy_stream_url or source_stream_url,
            )
        return PlaybackDecision(route="source_stream", stream_url=source_stream_url)
```

```python
# src/gateway/playback_resolver.py
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import OpenListClient
from gateway.models import MediaItem, PlaybackRecord, PoolObject, TransferRoute, User, UserDriveAccount
from gateway.playback import PlaybackDecision, PlaybackService


class PlaybackResolver:
    def __init__(self, playback_service: PlaybackService, openlist_client: OpenListClient) -> None:
        self._playback_service = playback_service
        self._openlist_client = openlist_client

    async def resolve(self, session: Session, *, user_id: int, media_id: int) -> PlaybackDecision:
        user = session.get(User, user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")

        media = session.get(MediaItem, media_id)
        if media is None:
            raise LookupError(f"media {media_id} not found")

        self_hit = session.scalar(
            select(PoolObject.target_path).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id == user_id,
            )
        )
        donor_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id != user_id,
            )
        )
        donor_available = donor_pool is not None and session.scalar(
            select(UserDriveAccount.id).where(
                UserDriveAccount.user_id == donor_pool.owner_user_id,
                UserDriveAccount.enabled.is_(True),
                UserDriveAccount.share_pool_enabled.is_(True),
            )
        ) is not None
        target_drive = session.scalar(
            select(UserDriveAccount).where(
                UserDriveAccount.user_id == user_id,
                UserDriveAccount.enabled.is_(True),
            )
        )
        source_copy_stream_url = None
        if target_drive is not None:
            target_name = PurePosixPath(media.source_path).name
            source_copy_stream_url = f"{target_drive.root_dir.rstrip('/')}/{target_name}"

        stream_info = await self._openlist_client.get_stream_info(media.openlist_path)
        decision = self._playback_service.resolve(
            self_hit=self_hit,
            donor_available=donor_available,
            source_copy_supported=target_drive is not None,
            source_stream_url=stream_info.raw_url,
            pool_stream_url=donor_pool.target_path if donor_pool is not None else None,
            source_copy_stream_url=source_copy_stream_url,
            elapsed_ms=0,
        )

        session.add(
            PlaybackRecord(
                user_id=user_id,
                media_id=media_id,
                route=TransferRoute(decision.route),
                success=True,
                latency_ms=0,
            )
        )
        session.commit()
        return decision
```

```python
# src/gateway/api/playback.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from gateway.config import settings
from gateway.db import get_session
from gateway.integrations.openlist_client import OpenListClient
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver

router = APIRouter(prefix="/api/playback", tags=["playback"])


@router.get("/{media_id}")
async def resolve_playback(media_id: int, user_id: int, session: Session = Depends(get_session)) -> dict[str, str | int]:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    resolver = PlaybackResolver(PlaybackService(total_budget_ms=2000), client)
    try:
        try:
            decision = await resolver.resolve(session, user_id=user_id, media_id=media_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
    finally:
        await client.aclose()
    return {
        "user_id": user_id,
        "media_id": media_id,
        "route": decision.route,
        "stream_url": decision.stream_url,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/playback/test_playback_service.py::test_playback_service_uses_supplied_pool_stream_url tests/playback/test_playback_resolver.py::test_playback_resolver_returns_real_source_stream_and_persists_record tests/api/test_playback_api.py::test_playback_api_reads_media_from_database -v`

Expected: PASS and `/api/playback/{media_id}` now depends on real DB data plus OpenList stream resolution.

- [ ] **Step 5: Commit**

```bash
git add src/gateway/playback.py src/gateway/playback_resolver.py src/gateway/api/playback.py tests/playback/test_playback_service.py tests/playback/test_playback_resolver.py tests/api/test_playback_api.py
git commit -m "feat: wire playback api to real media data"
```

### Task 6: Add Real Integration Smoke Probe And Docs Closeout

**Files:**
- Create: `src/gateway/real_integration.py`
- Create: `scripts/verify_real_integration.py`
- Create: `tests/scripts/test_verify_real_integration.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing tests**

```python
# tests/scripts/test_verify_real_integration.py
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.config import Settings
from gateway.integrations.openlist_client import CatalogRow, StreamInfo
from gateway.integrations.rapid_copy_client import RapidCopyResult
from gateway.models import Base
from gateway.real_integration import run_real_integration_probe


class StubOpenListClient:
    async def get_stream_info(self, source_path: str) -> StreamInfo:
        assert source_path == "/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://drive.local/Movie.2024.mkv",
            content_length=2048,
            accepts_ranges=True,
        )

    async def list_catalog(self, root_path: str) -> list[CatalogRow]:
        assert root_path == "/Movies"
        return [
            CatalogRow(
                path="/Movies/Movie.2024.mkv",
                size=2048,
                file_id="gd-1",
                mtime="2026-05-17T00:00:00Z",
            )
        ]


class StubRapidCopyClient:
    async def copy(
        self,
        donor_cookie: str,
        target_cookie: str,
        source_path: str,
        target_path: str,
    ) -> RapidCopyResult:
        assert donor_cookie == "UID=donor"
        assert target_cookie == "UID=target"
        return RapidCopyResult(ok=True, error_code=None, target_path=target_path, detail=None)


@pytest.mark.asyncio
async def test_run_real_integration_probe_returns_sync_playback_and_stats(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'real-integration.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    app_settings = Settings(
        _env_file=None,
        cookie_secret="x" * 32,
        catalog_root_path="/Movies",
        openlist_probe_path="/Movies/Movie.2024.mkv",
        rapid_copy_donor_cookie="UID=donor",
        rapid_copy_target_cookie="UID=target",
        rapid_copy_source_path="/Movies/Movie.2024.mkv",
        rapid_copy_target_path="/EmbyCache/probe/Movie.2024.mkv",
    )

    with Session(engine) as session:
        summary = await run_real_integration_probe(
            session=session,
            app_settings=app_settings,
            openlist_client=StubOpenListClient(),
            rapid_copy_client=StubRapidCopyClient(),
        )

    assert summary["sync"] == {"created": 1, "updated": 0}
    assert summary["playback"]["route"] == "source_copy"
    assert summary["rapid_copy"] == {"ok": True, "error_code": None}
    assert summary["stats"]["source_copy"] == 1


def test_readme_mentions_real_integration_probe() -> None:
    readme = Path("/root/gd-playback-gateway/README.md").read_text()

    assert "uv run python scripts/verify_real_integration.py" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_verify_real_integration.py -v`

Expected: FAIL because `gateway.real_integration` 与 `scripts/verify_real_integration.py` 还不存在，README 也还没写这个命令。

- [ ] **Step 3: Write minimal implementation**

```python
# src/gateway/real_integration.py
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.api.admin import summarize_routes
from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
from gateway.config import Settings
from gateway.integrations.openlist_client import OpenListClient
from gateway.integrations.rapid_copy_client import RapidCopyClient
from gateway.models import MediaItem, PlaybackRecord, User, UserDriveAccount
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver
from gateway.script_inputs import build_rapid_copy_probe
from gateway.security import CookieCipher


async def run_real_integration_probe(
    session: Session,
    *,
    app_settings: Settings,
    openlist_client: OpenListClient,
    rapid_copy_client: RapidCopyClient,
) -> dict[str, object]:
    probe = build_rapid_copy_probe(app_settings)
    probe_user = session.scalar(select(User).where(User.username == "probe-user"))
    if probe_user is None:
        probe_user = User(username="probe-user", status="active")
        session.add(probe_user)
        session.flush()

    drive = session.scalar(select(UserDriveAccount).where(UserDriveAccount.user_id == probe_user.id))
    if drive is None:
        session.add(
            UserDriveAccount(
                user_id=probe_user.id,
                drive_type="115",
                cookie_encrypted=CookieCipher(app_settings.cookie_secret).encrypt(
                    app_settings.rapid_copy_target_cookie
                ),
                root_dir=str(PurePosixPath(probe.target_path).parent),
                share_pool_enabled=True,
            )
        )
        session.commit()

    sync_summary = await CatalogSyncService(CatalogService(), openlist_client).sync_root(
        session,
        app_settings.catalog_root_path,
    )
    media_item = session.scalar(
        select(MediaItem).where(MediaItem.source_path == app_settings.openlist_probe_path)
    )
    if media_item is None:
        raise LookupError(f"media not synced for {app_settings.openlist_probe_path}")

    playback = await PlaybackResolver(PlaybackService(), openlist_client).resolve(
        session,
        user_id=probe_user.id,
        media_id=media_item.id,
    )
    copy_result = await rapid_copy_client.copy(
        probe.donor_cookie,
        probe.target_cookie,
        probe.source_path,
        probe.target_path,
    )
    routes = session.scalars(select(PlaybackRecord.route)).all()
    normalized_routes = [
        route.value if hasattr(route, "value") else str(route) for route in routes
    ]
    return {
        "sync": {"created": sync_summary.created, "updated": sync_summary.updated},
        "playback": {"route": playback.route, "stream_url": playback.stream_url},
        "rapid_copy": {"ok": copy_result.ok, "error_code": copy_result.error_code},
        "stats": summarize_routes(normalized_routes),
    }
```

```python
# scripts/verify_real_integration.py
import asyncio
import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.db import init_schema, make_engine
from gateway.integrations.openlist_client import OpenListClient
from gateway.integrations.rapid_copy_client import RapidCopyClient
from gateway.real_integration import run_real_integration_probe


async def main() -> None:
    engine = make_engine(settings.database_url)
    init_schema(engine)
    openlist_client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    rapid_copy_client = RapidCopyClient(settings.rapid_copy_base_url)
    try:
        with Session(engine) as session:
            summary = await run_real_integration_probe(
                session=session,
                app_settings=settings,
                openlist_client=openlist_client,
                rapid_copy_client=rapid_copy_client,
            )
        print(summary)
    finally:
        await openlist_client.aclose()
        await rapid_copy_client.aclose()
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

```markdown
<!-- README.md -->
## 真实环境联调步骤

1. 在 `.env` 中填入 `GATEWAY_OPENLIST_*` 与 `GATEWAY_RAPID_COPY_*` 变量。
2. 先执行 `uv run python scripts/validate_openlist_stream.py`。
3. 再执行 `uv run python scripts/validate_rapid_copy.py`。
4. 最后执行 `uv run python scripts/verify_real_integration.py`。
5. 看到输出里包含 `sync`、`playback`、`rapid_copy`、`stats` 四个键后，再去手工验收 `/api/playback/{media_id}` 与 `/api/admin/stats`。
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_verify_real_integration.py -v`

Expected: PASS with the smoke probe unit coverage and the README command reference.

Run: `uv run pytest tests -v`

Expected: full test suite PASS after all six tasks land.

Run: `uv run python scripts/verify_real_integration.py`

Expected: 在真实环境变量已填好的前提下，脚本退出码为 0，并打印包含 `sync`、`playback`、`rapid_copy`、`stats` 的字典。

- [ ] **Step 5: Commit**

```bash
git add README.md src/gateway/real_integration.py scripts/verify_real_integration.py tests/scripts/test_verify_real_integration.py
git commit -m "docs: add real integration smoke workflow"
```
