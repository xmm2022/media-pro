# Admin UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline 778-line `src/gateway/api/admin_ui.py` with a Vue 3 + Vite + Naive UI single-page application served at `/admin`, covering the four existing views plus the three new admin APIs (`media-items`, `transfer-jobs`, `playback-records`).

**Architecture:** New `web/` subdirectory holding the Vue project. FastAPI mounts the built `web/dist/` as static assets + SPA fallback at `/admin`. Vue Router (history mode), Pinia stores for session + drive-types catalog only, page-local `useApi` composable for all other resources. A single rip-and-replace cutover commit at the end of the plan removes `admin_ui.py` and rewires `main.py`.

**Tech Stack:** Vue 3.5 + Composition API, Vite 6, Naive UI 2.41+, Vue Router 4, Pinia, TypeScript 5, pnpm, Vitest + happy-dom for frontend tests; existing FastAPI + pytest backend.

---

## Scope

Implements the spec in `docs/superpowers/specs/2026-05-25-admin-ui-redesign-design.md`.

Included:

- Vue 3 + Vite + Naive UI project scaffold under `web/`
- API client + TS types mirroring `gateway.schemas`
- `useApi` composable, Pinia stores for session + catalog
- App shell with sidebar grouped nav (运营 / 数据 / 诊断)
- 7 pages: Overview, Users, Drives, Pool, MediaItems, TransferJobs, PlaybackRecords
- LoginPage + router guard
- Backend extension of `GET /api/admin/session` with `authenticated: bool`
- Migration cutover: delete `admin_ui.py`, delete `GET /admin/login` HTML route, mount SPA at `/admin`, migrate auth tests, update README and deploy docs

Excluded (per spec Non-Goals):

- Dark mode, i18n, deep mobile design
- Charts, real-time push, end-to-end / Playwright tests
- User-facing portal, OAuth jump, provider strategy refactor

---

## File Structure

Created:

- `web/package.json`, `web/pnpm-lock.yaml`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/index.html`, `web/src/env.d.ts`
- `web/src/main.ts` — bootstraps Vue + Pinia + Router + Naive
- `web/src/App.vue` — `NLayout` shell with sider + header + content
- `web/src/router/index.ts` — routes + `beforeEach` auth guard
- `web/src/stores/session.ts` — `useSessionStore`
- `web/src/stores/catalog.ts` — `useCatalogStore` (drive-types)
- `web/src/api/client.ts` — `apiGet/apiPost/apiDelete` thin fetch wrapper
- `web/src/api/types.ts` — TS types mirroring `gateway.schemas`
- `web/src/composables/useApi.ts` — `{ data, loading, error, refresh }`
- `web/src/components/ResourceTable.vue` — generic Naive UI DataTable wrapper
- `web/src/components/StatusPill.vue` — small status badge
- `web/src/pages/LoginPage.vue`, `OverviewPage.vue`, `UsersPage.vue`, `DrivesPage.vue`, `PoolPage.vue`, `MediaItemsPage.vue`, `TransferJobsPage.vue`, `PlaybackRecordsPage.vue`
- `web/tests/api/client.test.ts`, `web/tests/composables/useApi.test.ts`, `web/tests/components/ResourceTable.test.ts`
- `tests/api/test_admin_session.py` — new pytest for extended session endpoint
- `tests/api/test_admin_auth.py` — migrated auth flow tests
- `tests/api/test_admin_spa_serving.py` — SPA mount smoke

Modified:

- `src/gateway/api/admin_auth.py` — extend `GET /api/admin/session` to also return `authenticated`. (Cutover task: also delete `GET /admin/login` HTML route.)
- `.gitignore` — add `web/node_modules`, `web/dist`, `web/.vite`, `web/coverage`
- `README.md` — update `## 当前阶段` section after cutover, add `## 前端开发约定`
- `deploy/systemd/README.md` (or new `deploy/systemd/build.md`) — note `pnpm install && pnpm build` release step

Deleted (cutover task only):

- `src/gateway/api/admin_ui.py`
- `tests/api/test_admin_ui.py`

---

### Task 1: Vue Project Scaffold

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/index.html`, `web/src/main.ts`, `web/src/App.vue`, `web/src/env.d.ts`
- Modify: `.gitignore`
- Test: build smoke (`pnpm build`)

- [ ] **Step 1: Confirm pnpm is available**

Run:

```bash
pnpm --version
```

Expected: prints a version (e.g. `9.x` or `10.x`). If not installed, install via `corepack enable && corepack prepare pnpm@latest --activate` or `npm i -g pnpm` before continuing.

- [ ] **Step 2: Create `web/package.json`**

```json
{
  "name": "media-pro-admin-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "vue": "^3.5.0",
    "vue-router": "^4.5.0",
    "pinia": "^3.0.0",
    "naive-ui": "^2.41.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "@vue/test-utils": "^2.4.0",
    "happy-dom": "^16.0.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0",
    "vitest": "^3.0.0",
    "vue-tsc": "^2.2.0"
  }
}
```

- [ ] **Step 3: Create `web/vite.config.ts`**

```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    target: 'es2022',
    sourcemap: true,
  },
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['tests/**/*.test.ts'],
  },
});
```

- [ ] **Step 4: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vitest/globals", "node"],
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] },
    "noEmit": true
  },
  "include": ["src/**/*", "src/**/*.vue", "tests/**/*"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 5: Create `web/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "skipLibCheck": true,
    "types": ["node"]
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 6: Create `web/index.html`**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>media-pro 管理工作台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 7: Create `web/src/env.d.ts`**

```ts
/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}
```

- [ ] **Step 8: Create a minimal `web/src/main.ts` placeholder**

This will be expanded in Task 6. For scaffold smoke, keep it bootable.

```ts
import { createApp } from 'vue';
import App from './App.vue';

createApp(App).mount('#app');
```

- [ ] **Step 9: Create a minimal `web/src/App.vue` placeholder**

```vue
<script setup lang="ts">
</script>

<template>
  <div>media-pro admin scaffold ready</div>
</template>
```

- [ ] **Step 10: Update root `.gitignore`**

Append the following lines to `/home/nax/media-pro/.gitignore` (do not remove existing lines):

```
web/node_modules
web/dist
web/.vite
web/coverage
```

Verify with:

```bash
tail -5 .gitignore
```

- [ ] **Step 11: Install dependencies and run a build smoke**

Run:

```bash
cd web
pnpm install
pnpm build
```

Expected: `pnpm install` completes without errors. `pnpm build` runs `vue-tsc --noEmit && vite build` and produces `web/dist/index.html` plus an `assets/` directory.

Verify with:

```bash
ls web/dist
```

Expected: lists `index.html` and `assets/`.

- [ ] **Step 12: Commit**

```bash
cd /home/nax/media-pro
git add web/package.json web/pnpm-lock.yaml web/vite.config.ts web/tsconfig.json web/tsconfig.node.json web/index.html web/src/main.ts web/src/App.vue web/src/env.d.ts .gitignore
git commit -m "feat: scaffold web/ vue 3 + vite + naive-ui project"
```

---

### Task 2: Extend `GET /api/admin/session` with `authenticated` Field

**Files:**
- Modify: `src/gateway/api/admin_auth.py`
- Create: `tests/api/test_admin_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_admin_session.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def _client(tmp_path: Path, *, admin_password: str = "") -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'session.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(
        create_app(database_url=database_url, admin_password=admin_password)
    )


def test_session_reports_unauthenticated_when_auth_disabled(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": False, "authenticated": False}


def test_session_reports_unauthenticated_when_auth_enabled_no_cookie(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": True, "authenticated": False}


def test_session_reports_authenticated_after_valid_login(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        login = client.post("/api/admin/login", json={"password": "secret"})
        session = client.get("/api/admin/session")

    assert login.status_code == 200
    assert session.status_code == 200
    assert session.json() == {"auth_enabled": True, "authenticated": True}


def test_session_reports_unauthenticated_when_cookie_invalid(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        client.cookies.set("media_pro_admin_session", "not-a-valid-token")
        response = client.get("/api/admin/session")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": True, "authenticated": False}
```

If `create_app` does not yet accept an `admin_password` kwarg, check `src/gateway/main.py` for the current parameter name (e.g. `admin_password=`) and adjust both the test and any downstream tasks consistently. Do not silently rename — keep the signature as-is.

- [ ] **Step 2: Run the failing test**

Run:

```bash
.venv/bin/pytest tests/api/test_admin_session.py -q
```

Expected: at least the last two cases FAIL because the response is currently `{"auth_enabled": ...}` only, missing the `authenticated` key.

- [ ] **Step 3: Extend the session endpoint**

In `src/gateway/api/admin_auth.py`, locate:

```python
@router.get("/api/admin/session")
def admin_session(request: Request) -> JSONResponse:
    return JSONResponse({"auth_enabled": bool(getattr(request.app.state, "admin_password", ""))})
```

Replace with:

```python
@router.get("/api/admin/session")
def admin_session(request: Request) -> JSONResponse:
    auth_enabled = bool(getattr(request.app.state, "admin_password", ""))
    if not auth_enabled:
        authenticated = False
    else:
        token = request.cookies.get(ADMIN_SESSION_COOKIE)
        authenticated = bool(token) and admin_session_is_valid(request, token)
    return JSONResponse({"auth_enabled": auth_enabled, "authenticated": authenticated})
```

`ADMIN_SESSION_COOKIE` and `admin_session_is_valid` are already defined in the same file; no new imports required.

- [ ] **Step 4: Run the test**

```bash
.venv/bin/pytest tests/api/test_admin_session.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Relax strict-equality assertions in `tests/api/test_admin_ui.py`**

The existing `test_admin_ui.py` asserts the exact dict shape returned by `/api/admin/session`. After Step 3 added the `authenticated` key, those assertions break. Update two lines in `tests/api/test_admin_ui.py`:

Replace:

```python
assert session_response.json() == {"auth_enabled": False}
```

with:

```python
assert session_response.json()["auth_enabled"] is False
```

And replace:

```python
assert session_response.json() == {"auth_enabled": True}
```

with:

```python
assert session_response.json()["auth_enabled"] is True
```

Do NOT touch `assert login_response.json() == {"ok": True, "auth_enabled": True}` — that comes from `POST /api/admin/login`, which this task does not change.

- [ ] **Step 6: Run nearby tests to confirm no regression**

```bash
.venv/bin/pytest tests/api/test_admin_ui.py tests/api/test_admin_session.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tests/api/test_admin_session.py tests/api/test_admin_ui.py src/gateway/api/admin_auth.py
git commit -m "feat: report authenticated state from admin session endpoint"
```

---

### Task 3: API Client + Types

**Files:**
- Create: `web/src/api/client.ts`, `web/src/api/types.ts`, `web/tests/api/client.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/tests/api/client.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost, apiDelete, setUnauthorizedHandler } from '@/api/client';

const originalFetch = globalThis.fetch;

function mockFetchOnce(response: Response): void {
  globalThis.fetch = vi.fn().mockResolvedValueOnce(response);
}

beforeEach(() => {
  setUnauthorizedHandler(null);
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe('apiGet', () => {
  it('appends query params and parses JSON', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    globalThis.fetch = fetchSpy;

    const result = await apiGet<{ ok: boolean }>('/admin/media-items', { q: 'Movie', limit: 10 });

    expect(result).toEqual({ ok: true });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/admin/media-items?q=Movie&limit=10');
    expect(init.credentials).toBe('include');
  });

  it('omits undefined and null params', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    globalThis.fetch = fetchSpy;

    await apiGet('/admin/users', { limit: 50, offset: undefined, q: null });

    expect(fetchSpy.mock.calls[0][0]).toBe('/api/admin/users?limit=50');
  });

  it('throws ApiError on non-2xx with parsed body', async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: 'nope' }), {
        status: 400,
        headers: { 'content-type': 'application/json' },
      }),
    );

    await expect(apiGet('/admin/users')).rejects.toMatchObject({
      status: 400,
      body: { detail: 'nope' },
    });
    await expect(apiGet('/admin/users')).rejects.toBeInstanceOf(ApiError);
  });

  it('invokes the unauthorized handler on 401', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetchOnce(
      new Response('Unauthorized', { status: 401 }),
    );

    await expect(apiGet('/admin/users')).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledTimes(1);
  });
});

describe('apiPost and apiDelete', () => {
  it('apiPost sends JSON body', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 1 }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    globalThis.fetch = fetchSpy;

    const result = await apiPost('/admin/users', { username: 'alice' });

    expect(result).toEqual({ id: 1 });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/admin/users');
    expect(init.method).toBe('POST');
    expect(init.headers).toMatchObject({ 'content-type': 'application/json' });
    expect(JSON.parse(init.body as string)).toEqual({ username: 'alice' });
  });

  it('apiDelete sends DELETE', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    globalThis.fetch = fetchSpy;

    await apiDelete('/admin/drives/1');

    expect(fetchSpy.mock.calls[0][1].method).toBe('DELETE');
  });
});
```

- [ ] **Step 2: Run the failing test**

```bash
cd web
pnpm test
```

Expected: tests fail because `@/api/client` does not exist.

- [ ] **Step 3: Implement the client**

Create `web/src/api/client.ts`:

```ts
const API_BASE = '/api';

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const url = `${API_BASE}${path}`;
  if (!params) {
    return url;
  }
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

async function readBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return await response.text();
}

async function request<T>(method: string, path: string, body?: unknown, params?: Record<string, unknown>): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const response = await fetch(buildUrl(path, params), init);

  if (response.status === 401) {
    unauthorizedHandler?.();
  }

  if (!response.ok) {
    const errorBody = await readBody(response);
    throw new ApiError(response.status, errorBody, `${method} ${path} failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await readBody(response)) as T;
}

export function apiGet<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  return request<T>('GET', path, undefined, params);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

export function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}
```

- [ ] **Step 4: Create `web/src/api/types.ts`**

```ts
// All types mirror gateway.schemas — keep field names and optionality in sync.

// mirrors gateway.schemas.UserRead
export interface UserRead {
  id: number;
  username: string;
  status: string;
}

// mirrors gateway.schemas.UserCreate
export interface UserCreate {
  username: string;
  status?: string;
}

// mirrors gateway.schemas.DriveAccountRead
export interface DriveAccountRead {
  id: number;
  user_id: number;
  drive_type: string;
  root_dir: string;
  enabled: boolean;
  share_pool_enabled: boolean;
  health_status: string;
  last_checked_at: string | null;
  cookie_preview: string | null;
  openlist_mount_path: string | null;
  openlist_storage_managed: boolean;
}

// mirrors gateway.schemas.CaiyunDriveCredentials
export interface CaiyunDriveCredentials {
  access_token: string;
  refresh_token?: string;
  account_type?: string;
}

// mirrors gateway.schemas.DriveAccountCreate
export interface DriveAccountCreate {
  user_id: number;
  drive_type: string;
  cookie?: string | null;
  root_dir: string;
  share_pool_enabled?: boolean;
  caiyun?: CaiyunDriveCredentials | null;
  mount_path?: string | null;
}

// mirrors gateway.schemas.PoolObjectRead
export interface PoolObjectRead {
  id: number;
  media_id: number;
  owner_user_id: number;
  drive_type: string;
  target_path: string;
  status: string;
  last_verified_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  failure_count: number;
  cooldown_until: string | null;
}

// mirrors gateway.schemas.MediaItemRead
export interface MediaItemRead {
  id: number;
  source_path: string;
  source_file_id: string | null;
  size: number;
  mtime: string | null;
  fingerprint: string;
  openlist_path: string;
}

// mirrors gateway.schemas.TransferJobRead
export interface TransferJobRead {
  id: number;
  media_id: number;
  donor_user_id: number | null;
  target_user_id: number;
  route_stage: string;
  idempotency_key: string;
  status: string;
  error_code: string | null;
  attempt_no: number;
}

// mirrors gateway.schemas.PlaybackRecordRead
export interface PlaybackRecordRead {
  id: number;
  user_id: number;
  media_id: number;
  route: string;
  success: boolean;
  latency_ms: number;
}

// mirrors gateway.schemas.CredentialFieldRead
export interface CredentialFieldRead {
  name: string;
  label: string;
  secret: boolean;
  required: boolean;
  help_text: string | null;
}

// mirrors gateway.schemas.DriveTypeCapabilitiesRead
export interface DriveTypeCapabilitiesRead {
  can_stream: boolean;
  can_source_copy: boolean;
  can_pool_copy: boolean;
  managed_by_openlist: boolean;
  supports_health_probe: boolean;
  supports_user_bind: boolean;
}

// mirrors gateway.schemas.DriveTypeRead
export interface DriveTypeRead {
  drive_type: string;
  label: string;
  description: string;
  credential_type: string;
  default_root_dir: string;
  capabilities: DriveTypeCapabilitiesRead;
  credential_fields: CredentialFieldRead[];
}

// mirrors response of GET /api/admin/session (gateway.api.admin_auth.admin_session)
export interface AdminSessionRead {
  auth_enabled: boolean;
  authenticated: boolean;
}

// mirrors gateway.schemas.AdminOverviewRead (and nested sections)
export interface AdminOverviewRead {
  routes: Record<string, number>;
  drives: {
    total: number;
    attention: DriveAccountRead[];
    [key: string]: unknown;
  };
  pool_objects: {
    total: number;
    attention: PoolObjectRead[];
    [key: string]: unknown;
  };
}
```

If any field name disagrees with `src/gateway/schemas.py`, fix this file to match the Python definitions — the Python schemas are authoritative.

- [ ] **Step 5: Run the test**

```bash
cd web
pnpm test
```

Expected: client tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/nax/media-pro
git add web/src/api/client.ts web/src/api/types.ts web/tests/api/client.test.ts
git commit -m "feat: add admin api client and shared types"
```

---

### Task 4: `useApi` Composable

**Files:**
- Create: `web/src/composables/useApi.ts`, `web/tests/composables/useApi.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/tests/composables/useApi.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';
import { useApi } from '@/composables/useApi';
import { ApiError } from '@/api/client';

async function flush(): Promise<void> {
  await nextTick();
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  await nextTick();
}

describe('useApi', () => {
  it('starts with loading=true and resolves with data', async () => {
    const fetcher = vi.fn().mockResolvedValue(['item']);
    const { data, loading, error } = useApi(fetcher);

    expect(loading.value).toBe(true);
    expect(data.value).toBeNull();

    await flush();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(data.value).toEqual(['item']);
  });

  it('captures errors and clears data', async () => {
    const fetcher = vi.fn().mockRejectedValue(new ApiError(500, { detail: 'boom' }, 'boom'));
    const { data, loading, error } = useApi(fetcher);

    await flush();

    expect(loading.value).toBe(false);
    expect(data.value).toBeNull();
    expect(error.value).toBeInstanceOf(ApiError);
    expect((error.value as ApiError).status).toBe(500);
  });

  it('refresh re-invokes the fetcher and resets state', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce([1]).mockResolvedValueOnce([2]);
    const { data, refresh } = useApi(fetcher);

    await flush();
    expect(data.value).toEqual([1]);

    const refreshPromise = refresh();
    await flush();
    await refreshPromise;

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(data.value).toEqual([2]);
  });

  it('skips initial fetch when immediate=false', async () => {
    const fetcher = vi.fn().mockResolvedValue('x');
    const { data, loading, refresh } = useApi(fetcher, { immediate: false });

    expect(loading.value).toBe(false);
    expect(fetcher).not.toHaveBeenCalled();

    await refresh();

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(data.value).toBe('x');
  });
});
```

- [ ] **Step 2: Run the failing test**

```bash
cd web
pnpm test
```

Expected: `useApi.test.ts` cases fail with module-not-found.

- [ ] **Step 3: Implement the composable**

Create `web/src/composables/useApi.ts`:

```ts
import { ref, type Ref } from 'vue';
import { ApiError } from '@/api/client';

export interface UseApiOptions {
  immediate?: boolean;
}

export interface UseApiResult<T> {
  data: Ref<T | null>;
  loading: Ref<boolean>;
  error: Ref<ApiError | Error | null>;
  refresh: () => Promise<void>;
}

export function useApi<T>(fetcher: () => Promise<T>, options: UseApiOptions = {}): UseApiResult<T> {
  const { immediate = true } = options;
  const data = ref<T | null>(null) as Ref<T | null>;
  const loading = ref<boolean>(false);
  const error = ref<ApiError | Error | null>(null);

  async function refresh(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      data.value = await fetcher();
    } catch (caught) {
      data.value = null;
      error.value = caught instanceof Error ? caught : new Error(String(caught));
    } finally {
      loading.value = false;
    }
  }

  if (immediate) {
    void refresh();
  }

  return { data, loading, error, refresh };
}
```

- [ ] **Step 4: Run the test**

```bash
cd web
pnpm test
```

Expected: all client + useApi tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/nax/media-pro
git add web/src/composables/useApi.ts web/tests/composables/useApi.test.ts
git commit -m "feat: add useApi composable"
```

---

### Task 5: Pinia Stores

**Files:**
- Create: `web/src/stores/session.ts`, `web/src/stores/catalog.ts`

No focused tests; these are thin wrappers over `apiGet/apiPost` whose contract is covered by `client.test.ts`. Page-level usage validates them.

- [ ] **Step 1: Create `web/src/stores/session.ts`**

```ts
import { defineStore } from 'pinia';
import { apiGet, apiPost } from '@/api/client';
import type { AdminSessionRead } from '@/api/types';

interface SessionState {
  authEnabled: boolean;
  authenticated: boolean;
  loaded: boolean;
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    authEnabled: false,
    authenticated: false,
    loaded: false,
  }),
  actions: {
    async refresh(): Promise<void> {
      const session = await apiGet<AdminSessionRead>('/admin/session');
      this.authEnabled = session.auth_enabled;
      this.authenticated = session.authenticated;
      this.loaded = true;
    },
    async login(password: string): Promise<void> {
      await apiPost('/admin/login', { password });
      await this.refresh();
    },
    async logout(): Promise<void> {
      await apiPost('/admin/logout', {});
      this.authenticated = false;
    },
  },
});
```

- [ ] **Step 2: Create `web/src/stores/catalog.ts`**

```ts
import { defineStore } from 'pinia';
import { apiGet } from '@/api/client';
import type { DriveTypeRead } from '@/api/types';

interface CatalogState {
  driveTypes: DriveTypeRead[];
  loaded: boolean;
}

export const useCatalogStore = defineStore('catalog', {
  state: (): CatalogState => ({
    driveTypes: [],
    loaded: false,
  }),
  actions: {
    async ensureLoaded(): Promise<void> {
      if (this.loaded) return;
      this.driveTypes = await apiGet<DriveTypeRead[]>('/admin/drive-types');
      this.loaded = true;
    },
  },
});
```

- [ ] **Step 3: Type-check the new files**

```bash
cd web
pnpm exec vue-tsc --noEmit
```

Expected: no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd /home/nax/media-pro
git add web/src/stores/session.ts web/src/stores/catalog.ts
git commit -m "feat: add session and catalog pinia stores"
```

---

### Task 6: App Shell, Router, and LoginPage

**Files:**
- Modify: `web/src/main.ts`, `web/src/App.vue`
- Create: `web/src/router/index.ts`, `web/src/pages/LoginPage.vue`
- Create: placeholder pages for the seven routes (real content added in Tasks 8–14)

- [ ] **Step 1: Add placeholder page components**

The router needs every page to resolve. Create simple stubs for the remaining pages now; later tasks replace their templates.

Create the following with identical placeholder content, substituting the component name and title:

`web/src/pages/OverviewPage.vue`:

```vue
<script setup lang="ts">
</script>

<template>
  <section><h2>系统概览</h2><p>To be implemented in Task 8.</p></section>
</template>
```

Repeat for `UsersPage.vue` ("用户管理", Task 9), `DrivesPage.vue` ("Drive 管理", Task 10), `PoolPage.vue` ("Pool 对象", Task 11), `MediaItemsPage.vue` ("媒体清单", Task 12), `TransferJobsPage.vue` ("转存历史", Task 13), `PlaybackRecordsPage.vue` ("播放诊断", Task 14).

- [ ] **Step 2: Create `web/src/pages/LoginPage.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NCard, NForm, NFormItem, NInput, NButton, NAlert } from 'naive-ui';
import { useSessionStore } from '@/stores/session';
import { ApiError } from '@/api/client';

const router = useRouter();
const route = useRoute();
const session = useSessionStore();

const password = ref('');
const submitting = ref(false);
const errorMessage = ref<string | null>(null);

async function submit(): Promise<void> {
  if (!password.value) {
    errorMessage.value = '请输入密码';
    return;
  }
  submitting.value = true;
  errorMessage.value = null;
  try {
    await session.login(password.value);
    const next = typeof route.query.next === 'string' ? route.query.next : '/admin/overview';
    await router.replace(next);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 401) {
      errorMessage.value = '密码错误';
    } else if (caught instanceof ApiError) {
      errorMessage.value = `登录失败 (${caught.status})`;
    } else {
      errorMessage.value = '登录失败';
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div style="display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px">
    <NCard title="media-pro 管理员登录" style="max-width:380px;width:100%">
      <NAlert v-if="errorMessage" type="error" :show-icon="false" style="margin-bottom:16px">
        {{ errorMessage }}
      </NAlert>
      <NForm @submit.prevent="submit">
        <NFormItem label="管理员密码">
          <NInput v-model:value="password" type="password" show-password-on="click" autofocus />
        </NFormItem>
        <NButton type="primary" block :loading="submitting" attr-type="submit">
          登录
        </NButton>
      </NForm>
    </NCard>
  </div>
</template>
```

- [ ] **Step 3: Create `web/src/router/index.ts`**

```ts
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import LoginPage from '@/pages/LoginPage.vue';
import OverviewPage from '@/pages/OverviewPage.vue';
import UsersPage from '@/pages/UsersPage.vue';
import DrivesPage from '@/pages/DrivesPage.vue';
import PoolPage from '@/pages/PoolPage.vue';
import MediaItemsPage from '@/pages/MediaItemsPage.vue';
import TransferJobsPage from '@/pages/TransferJobsPage.vue';
import PlaybackRecordsPage from '@/pages/PlaybackRecordsPage.vue';
import { useSessionStore } from '@/stores/session';
import { setUnauthorizedHandler } from '@/api/client';

const routes: RouteRecordRaw[] = [
  { path: '/admin', redirect: '/admin/overview' },
  { path: '/admin/login', name: 'login', component: LoginPage, meta: { public: true } },
  { path: '/admin/overview', name: 'overview', component: OverviewPage, meta: { title: '系统概览', group: '运营' } },
  { path: '/admin/users', name: 'users', component: UsersPage, meta: { title: '用户管理', group: '运营' } },
  { path: '/admin/drives', name: 'drives', component: DrivesPage, meta: { title: 'Drive 管理', group: '运营' } },
  { path: '/admin/pool', name: 'pool', component: PoolPage, meta: { title: 'Pool 对象', group: '运营' } },
  { path: '/admin/media-items', name: 'media-items', component: MediaItemsPage, meta: { title: '媒体清单', group: '数据' } },
  { path: '/admin/transfer-jobs', name: 'transfer-jobs', component: TransferJobsPage, meta: { title: '转存历史', group: '诊断' } },
  { path: '/admin/playback-records', name: 'playback-records', component: PlaybackRecordsPage, meta: { title: '播放诊断', group: '诊断' } },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.meta.public) return true;
  const session = useSessionStore();
  if (!session.loaded) {
    try {
      await session.refresh();
    } catch {
      return { name: 'login', query: { next: to.fullPath } };
    }
  }
  if (!session.authEnabled) return true;
  if (session.authenticated) return true;
  return { name: 'login', query: { next: to.fullPath } };
});

export function installUnauthorizedRedirect(): void {
  setUnauthorizedHandler(() => {
    const current = router.currentRoute.value;
    if (current.name === 'login') return;
    void router.replace({ name: 'login', query: { next: current.fullPath } });
  });
}
```

- [ ] **Step 4: Update `web/src/main.ts`**

Replace the scaffold placeholder with:

```ts
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import naive from 'naive-ui';
import App from './App.vue';
import { router, installUnauthorizedRedirect } from './router';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(naive);
installUnauthorizedRedirect();
app.mount('#app');
```

- [ ] **Step 5: Update `web/src/App.vue`**

Replace the scaffold placeholder with:

```vue
<script setup lang="ts">
import { computed, h, onMounted } from 'vue';
import { useRoute, useRouter, RouterView } from 'vue-router';
import {
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NIcon,
  NButton,
  NConfigProvider,
  NMessageProvider,
  NSpace,
} from 'naive-ui';
import { useSessionStore } from '@/stores/session';
import { useCatalogStore } from '@/stores/catalog';

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const catalog = useCatalogStore();

const isLoginRoute = computed(() => route.name === 'login');

const menuOptions = computed(() => {
  const groups: Record<string, { label: string; key: string }[]> = { 运营: [], 数据: [], 诊断: [] };
  for (const r of router.getRoutes()) {
    if (!r.meta?.group || !r.meta?.title) continue;
    groups[r.meta.group as string]?.push({ label: r.meta.title as string, key: r.name as string });
  }
  return (Object.keys(groups) as Array<keyof typeof groups>).flatMap((group) => [
    { type: 'group', label: group, key: `group-${group}`, children: groups[group] },
  ]);
});

const activeKey = computed(() => (route.name as string | undefined) ?? null);

function handleSelect(key: string): void {
  void router.push({ name: key });
}

async function logout(): Promise<void> {
  await session.logout();
  await router.replace({ name: 'login' });
}

onMounted(async () => {
  if (!session.loaded) {
    try {
      await session.refresh();
    } catch {
      /* router guard handles redirect */
    }
  }
  if (!isLoginRoute.value) {
    try {
      await catalog.ensureLoaded();
    } catch {
      /* drive form will surface a retry */
    }
  }
});
</script>

<template>
  <NConfigProvider>
    <NMessageProvider>
      <RouterView v-if="isLoginRoute" />
      <NLayout v-else has-sider style="min-height:100vh">
        <NLayoutSider :width="220" bordered>
          <div style="padding:14px 16px;font-weight:700;font-size:15px">media-pro</div>
          <NMenu :options="menuOptions" :value="activeKey" @update:value="handleSelect" />
        </NLayoutSider>
        <NLayout>
          <NLayoutHeader bordered style="display:flex;align-items:center;justify-content:space-between;padding:0 20px;height:48px">
            <strong>{{ route.meta?.title ?? '管理工作台' }}</strong>
            <NSpace>
              <NButton v-if="session.authEnabled && session.authenticated" size="small" @click="logout">退出</NButton>
            </NSpace>
          </NLayoutHeader>
          <NLayoutContent content-style="padding:20px">
            <RouterView />
          </NLayoutContent>
        </NLayout>
      </NLayout>
    </NMessageProvider>
  </NConfigProvider>
</template>
```

- [ ] **Step 6: Manual verify in browser**

In one terminal run the FastAPI backend:

```bash
.venv/bin/uvicorn gateway.main:app --reload --port 8000
```

In another terminal:

```bash
cd web
pnpm dev
```

Open `http://localhost:5173/admin/`. Expected:

- Redirects to `/admin/overview`
- Sidebar shows 3 groups with 7 items
- Placeholder content reads "To be implemented in Task N"
- If `GATEWAY_ADMIN_PASSWORD` is set on the backend, you are redirected to `/admin/login` instead and the password form appears

If the dev server cannot reach the API, double-check `vite.config.ts` proxy and that uvicorn is listening on `127.0.0.1:8000`.

- [ ] **Step 7: Type-check**

```bash
cd web
pnpm exec vue-tsc --noEmit
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
cd /home/nax/media-pro
git add web/src/main.ts web/src/App.vue web/src/router/index.ts web/src/pages/
git commit -m "feat: add app shell, router with auth guard, and login page"
```

---

### Task 7: ResourceTable Component

**Files:**
- Create: `web/src/components/ResourceTable.vue`, `web/tests/components/ResourceTable.test.ts`

`ResourceTable` is a thin generic wrapper around `NDataTable` that takes columns + rows + pagination state and emits page changes. Pages use it directly; raw `NDataTable` is fine in unusual cases.

- [ ] **Step 1: Write the failing test**

Create `web/tests/components/ResourceTable.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ResourceTable from '@/components/ResourceTable.vue';

describe('ResourceTable', () => {
  it('renders rows from the rows prop', () => {
    const wrapper = mount(ResourceTable, {
      props: {
        columns: [
          { title: 'ID', key: 'id' },
          { title: 'Name', key: 'name' },
        ],
        rows: [
          { id: 1, name: 'alice' },
          { id: 2, name: 'bob' },
        ],
        rowKey: (r: { id: number }) => r.id,
      },
    });
    expect(wrapper.text()).toContain('alice');
    expect(wrapper.text()).toContain('bob');
  });

  it('shows the empty state when there are no rows and not loading', () => {
    const wrapper = mount(ResourceTable, {
      props: {
        columns: [{ title: 'ID', key: 'id' }],
        rows: [],
        rowKey: (r: { id: number }) => r.id,
        emptyText: '没有记录',
      },
    });
    expect(wrapper.text()).toContain('没有记录');
  });

  it('shows the error state when error is provided', () => {
    const wrapper = mount(ResourceTable, {
      props: {
        columns: [{ title: 'ID', key: 'id' }],
        rows: [],
        rowKey: (r: { id: number }) => r.id,
        error: new Error('boom'),
      },
    });
    expect(wrapper.text()).toContain('boom');
  });
});
```

- [ ] **Step 2: Run the failing test**

```bash
cd web
pnpm test
```

Expected: fails because component is missing.

- [ ] **Step 3: Create `web/src/components/ResourceTable.vue`**

```vue
<script setup lang="ts" generic="Row extends Record<string, unknown>">
import { computed } from 'vue';
import { NDataTable, NAlert, NEmpty, NSpin } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';

interface Props {
  columns: DataTableColumns<Row>;
  rows: readonly Row[];
  rowKey: (row: Row) => string | number;
  loading?: boolean;
  error?: Error | null;
  emptyText?: string;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
  emptyText: '没有数据',
});

const showEmpty = computed(() => !props.loading && !props.error && props.rows.length === 0);
</script>

<template>
  <div>
    <NAlert v-if="error" type="error" :show-icon="false" style="margin-bottom:12px">
      {{ error.message }}
    </NAlert>
    <NSpin :show="loading">
      <NEmpty v-if="showEmpty" :description="emptyText" style="padding:24px 0" />
      <NDataTable
        v-else
        :columns="columns"
        :data="[...rows]"
        :row-key="rowKey"
        :bordered="false"
        size="small"
      />
    </NSpin>
  </div>
</template>
```

- [ ] **Step 4: Run the test**

```bash
cd web
pnpm test
```

Expected: all three cases pass.

- [ ] **Step 5: Commit**

```bash
cd /home/nax/media-pro
git add web/src/components/ResourceTable.vue web/tests/components/ResourceTable.test.ts
git commit -m "feat: add generic resource table component"
```

---

### Task 8: OverviewPage

**Files:**
- Modify: `web/src/pages/OverviewPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { NCard, NGrid, NGridItem, NStatistic, NSpace, NButton, NTag, NAlert } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import type { AdminOverviewRead } from '@/api/types';

const { data, loading, error, refresh } = useApi<AdminOverviewRead>(() => apiGet('/admin/overview'));
</script>

<template>
  <NSpace vertical size="large">
    <NSpace align="center" justify="space-between">
      <p style="margin:0;color:#64748b">查看关键容量、健康状态和播放路由。</p>
      <NButton size="small" :loading="loading" @click="refresh">刷新</NButton>
    </NSpace>

    <NAlert v-if="error" type="error" :show-icon="false">{{ error.message }}</NAlert>

    <NGrid v-if="data" :cols="4" x-gap="12" y-gap="12">
      <NGridItem><NCard><NStatistic label="Drive 总数" :value="data.drives.total" /></NCard></NGridItem>
      <NGridItem><NCard><NStatistic label="Pool 对象" :value="data.pool_objects.total" /></NCard></NGridItem>
      <NGridItem><NCard><NStatistic label="需要关注 (Drive)" :value="data.drives.attention?.length ?? 0" /></NCard></NGridItem>
      <NGridItem><NCard><NStatistic label="需要关注 (Pool)" :value="data.pool_objects.attention?.length ?? 0" /></NCard></NGridItem>
    </NGrid>

    <NCard v-if="data" title="路由分布">
      <NSpace>
        <NTag v-for="(count, route) in data.routes" :key="route" :bordered="false">
          {{ route }}: {{ count }}
        </NTag>
      </NSpace>
    </NCard>
  </NSpace>
</template>
```

- [ ] **Step 2: Manual verify**

With dev server running (Task 6 Step 6), open `http://localhost:5173/admin/overview`. Expected: statistic cards render with backend numbers; refresh button refetches. If backend `/api/admin/overview` does not return the expected shape, the alert renders the error.

- [ ] **Step 3: Type-check**

```bash
cd web && pnpm exec vue-tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/nax/media-pro
git add web/src/pages/OverviewPage.vue
git commit -m "feat: implement admin overview page"
```

---

### Task 9: UsersPage

**Files:**
- Modify: `web/src/pages/UsersPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { h, ref } from 'vue';
import {
  NCard, NSpace, NButton, NForm, NFormItem, NInput, NSelect, NAlert, useMessage,
} from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet, apiPost, ApiError } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { UserRead } from '@/api/types';

const message = useMessage();

const { data: users, loading, error, refresh } = useApi<UserRead[]>(() => apiGet('/admin/users'));

const form = ref({ username: '', status: 'active' });
const submitting = ref(false);
const formError = ref<string | null>(null);

const statusOptions = [
  { label: 'active', value: 'active' },
  { label: 'disabled', value: 'disabled' },
];

const columns: DataTableColumns<UserRead> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '用户名', key: 'username' },
  { title: '状态', key: 'status', width: 120 },
];

async function submit(): Promise<void> {
  if (!form.value.username.trim()) {
    formError.value = '用户名必填';
    return;
  }
  submitting.value = true;
  formError.value = null;
  try {
    await apiPost('/admin/users', { username: form.value.username.trim(), status: form.value.status });
    form.value.username = '';
    message.success('用户已创建');
    await refresh();
  } catch (caught) {
    formError.value = caught instanceof ApiError ? `${caught.status}: ${JSON.stringify(caught.body)}` : '创建失败';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="创建用户">
      <NAlert v-if="formError" type="error" :show-icon="false" style="margin-bottom:12px">
        {{ formError }}
      </NAlert>
      <NForm inline @submit.prevent="submit">
        <NFormItem label="用户名" style="min-width:240px">
          <NInput v-model:value="form.username" placeholder="alice" />
        </NFormItem>
        <NFormItem label="状态" style="min-width:160px">
          <NSelect v-model:value="form.status" :options="statusOptions" />
        </NFormItem>
        <NFormItem label=" ">
          <NButton type="primary" :loading="submitting" attr-type="submit">创建</NButton>
        </NFormItem>
      </NForm>
    </NCard>

    <NCard title="用户列表">
      <ResourceTable
        :columns="columns"
        :rows="users ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="尚无用户"
      />
    </NCard>
  </NSpace>
</template>
```

- [ ] **Step 2: Manual verify**

Open `http://localhost:5173/admin/users`. Create a user via the form; the table refreshes; new row appears. If form fails, the alert shows the response body.

- [ ] **Step 3: Type-check**

```bash
cd web && pnpm exec vue-tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/UsersPage.vue
git commit -m "feat: implement admin users page"
```

---

### Task 10: DrivesPage (Dynamic Credential Fields from Catalog)

**Files:**
- Modify: `web/src/pages/DrivesPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { computed, h, ref } from 'vue';
import {
  NCard, NSpace, NButton, NForm, NFormItem, NInput, NSelect, NInputNumber, NAlert, NTag, useMessage,
} from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet, apiPost, apiDelete, ApiError } from '@/api/client';
import { useApi } from '@/composables/useApi';
import { useCatalogStore } from '@/stores/catalog';
import ResourceTable from '@/components/ResourceTable.vue';
import type { DriveAccountRead, DriveTypeRead } from '@/api/types';

const message = useMessage();
const catalog = useCatalogStore();
void catalog.ensureLoaded();

const { data: drives, loading, error, refresh } = useApi<DriveAccountRead[]>(() => apiGet('/admin/drives'));

const driveTypeOptions = computed(() =>
  catalog.driveTypes.map((dt) => ({ label: dt.label, value: dt.drive_type })),
);

const selectedDriveType = ref<string | null>(null);
const selectedDriveTypeRead = computed<DriveTypeRead | null>(() =>
  catalog.driveTypes.find((d) => d.drive_type === selectedDriveType.value) ?? null,
);

const form = ref<{
  user_id: number | null;
  root_dir: string;
  share_pool_enabled: boolean;
  credentials: Record<string, string>;
}>({ user_id: null, root_dir: '/EmbyCache', share_pool_enabled: false, credentials: {} });

const submitting = ref(false);
const formError = ref<string | null>(null);

function onDriveTypeChange(value: string | null): void {
  selectedDriveType.value = value;
  form.value.credentials = {};
  if (value) {
    const dt = catalog.driveTypes.find((d) => d.drive_type === value);
    if (dt) form.value.root_dir = dt.default_root_dir;
  }
}

async function submit(): Promise<void> {
  if (!selectedDriveType.value) {
    formError.value = '请选择 drive_type';
    return;
  }
  if (form.value.user_id === null) {
    formError.value = '请填写 user_id';
    return;
  }
  const dt = selectedDriveTypeRead.value!;
  const missing = dt.credential_fields.filter((f) => f.required && !form.value.credentials[f.name]?.trim());
  if (missing.length > 0) {
    formError.value = `必填字段缺失: ${missing.map((f) => f.label).join(', ')}`;
    return;
  }

  submitting.value = true;
  formError.value = null;
  try {
    const payload: Record<string, unknown> = {
      user_id: form.value.user_id,
      drive_type: selectedDriveType.value,
      root_dir: form.value.root_dir,
      share_pool_enabled: form.value.share_pool_enabled,
    };
    if (selectedDriveType.value === '115') {
      payload.cookie = form.value.credentials.cookie ?? '';
    } else if (selectedDriveType.value === 'caiyun') {
      payload.caiyun = {
        access_token: form.value.credentials.access_token ?? '',
        refresh_token: form.value.credentials.refresh_token ?? '',
        account_type: form.value.credentials.account_type ?? 'personal_new',
      };
    }
    await apiPost('/admin/drives', payload);
    message.success('Drive 已创建');
    form.value.credentials = {};
    await refresh();
  } catch (caught) {
    formError.value = caught instanceof ApiError ? `${caught.status}: ${JSON.stringify(caught.body)}` : '创建失败';
  } finally {
    submitting.value = false;
  }
}

async function removeDrive(id: number): Promise<void> {
  try {
    await apiDelete(`/admin/drives/${id}`);
    message.success('Drive 已删除');
    await refresh();
  } catch (caught) {
    const msg = caught instanceof ApiError ? `${caught.status}: ${JSON.stringify(caught.body)}` : '删除失败';
    message.error(msg);
  }
}

const columns: DataTableColumns<DriveAccountRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'User ID', key: 'user_id', width: 90 },
  { title: 'Type', key: 'drive_type', width: 110 },
  { title: 'Root', key: 'root_dir' },
  {
    title: '启用', key: 'enabled', width: 80,
    render: (row) => (row.enabled ? '是' : '否'),
  },
  {
    title: '健康', key: 'health_status', width: 110,
    render: (row) => row.health_status,
  },
  { title: 'Mount', key: 'openlist_mount_path' },
  {
    title: '操作', key: 'actions', width: 100,
    render: (row) =>
      h(
        NButton,
        { size: 'tiny', type: 'error', tertiary: true, onClick: () => removeDrive(row.id) },
        { default: () => '删除' },
      ),
  },
];

import { h } from 'vue';
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="创建 Drive">
      <NAlert v-if="formError" type="error" :show-icon="false" style="margin-bottom:12px">
        {{ formError }}
      </NAlert>
      <NForm @submit.prevent="submit">
        <NSpace>
          <NFormItem label="User ID" style="min-width:140px">
            <NInputNumber v-model:value="form.user_id" :min="1" />
          </NFormItem>
          <NFormItem label="Drive 类型" style="min-width:200px">
            <NSelect :options="driveTypeOptions" :value="selectedDriveType" @update:value="onDriveTypeChange" />
          </NFormItem>
          <NFormItem label="Root" style="min-width:200px">
            <NInput v-model:value="form.root_dir" />
          </NFormItem>
        </NSpace>
        <NSpace v-if="selectedDriveTypeRead">
          <NFormItem
            v-for="field in selectedDriveTypeRead.credential_fields"
            :key="field.name"
            :label="field.label"
            style="min-width:260px"
          >
            <NInput
              v-model:value="form.credentials[field.name]"
              :type="field.secret ? 'password' : 'text'"
              :show-password-on="field.secret ? 'click' : undefined"
              :placeholder="field.help_text ?? ''"
            />
          </NFormItem>
        </NSpace>
        <NButton type="primary" :loading="submitting" attr-type="submit">创建</NButton>
      </NForm>
    </NCard>

    <NCard title="Drive 列表">
      <ResourceTable
        :columns="columns"
        :rows="drives ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="尚无 drive"
      />
    </NCard>
  </NSpace>
</template>
```

Note: place the `h` and `NTag` imports at the top of the `<script setup>` block (the example above already does this).

- [ ] **Step 2: Manual verify**

Open `http://localhost:5173/admin/drives`. Pick `115` from the dropdown — only the `cookie` field appears. Pick `caiyun` — `access_token`, `refresh_token`, `account_type` appear. Submit a drive (with a real user_id that exists); list refreshes.

- [ ] **Step 3: Type-check**

```bash
cd web && pnpm exec vue-tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/DrivesPage.vue
git commit -m "feat: implement admin drives page with dynamic credential fields"
```

---

### Task 11: PoolPage

**Files:**
- Modify: `web/src/pages/PoolPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { computed, ref } from 'vue';
import { NCard, NSpace, NButton, NInputNumber, NSelect } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { PoolObjectRead } from '@/api/types';

const filters = ref<{
  status: string | null;
  media_id: number | null;
  owner_user_id: number | null;
  limit: number;
  offset: number;
}>({ status: null, media_id: null, owner_user_id: null, limit: 50, offset: 0 });

const statusOptions = [
  { label: 'ready', value: 'ready' },
  { label: 'suspect', value: 'suspect' },
  { label: 'cooldown', value: 'cooldown' },
  { label: 'disabled', value: 'disabled' },
  { label: 'stale', value: 'stale' },
];

const queryParams = computed(() => ({
  status: filters.value.status,
  media_id: filters.value.media_id,
  owner_user_id: filters.value.owner_user_id,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<PoolObjectRead[]>(() =>
  apiGet('/admin/pool-objects', queryParams.value),
);

const columns: DataTableColumns<PoolObjectRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'Media', key: 'media_id', width: 90 },
  { title: 'Owner', key: 'owner_user_id', width: 90 },
  { title: 'Type', key: 'drive_type', width: 90 },
  { title: 'Path', key: 'target_path' },
  { title: '状态', key: 'status', width: 110 },
  { title: '失败次数', key: 'failure_count', width: 100 },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NSelect
          v-model:value="filters.status"
          :options="statusOptions"
          placeholder="状态"
          clearable
          style="width:160px"
        />
        <NInputNumber v-model:value="filters.media_id" placeholder="media_id" clearable style="width:140px" />
        <NInputNumber v-model:value="filters.owner_user_id" placeholder="owner_user_id" clearable style="width:160px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:120px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:120px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="Pool 对象">
      <ResourceTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="无匹配记录"
      />
    </NCard>
  </NSpace>
</template>
```

- [ ] **Step 2: Manual verify**

Open `http://localhost:5173/admin/pool`. Apply a filter (e.g. status=`ready`), press 查询. Table updates. Clear filter, requery — full list returns.

- [ ] **Step 3: Type-check + commit**

```bash
cd web && pnpm exec vue-tsc --noEmit
cd /home/nax/media-pro
git add web/src/pages/PoolPage.vue
git commit -m "feat: implement admin pool objects page with filters"
```

---

### Task 12: MediaItemsPage

**Files:**
- Modify: `web/src/pages/MediaItemsPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { computed, ref } from 'vue';
import { NCard, NSpace, NButton, NInput, NInputNumber } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { MediaItemRead } from '@/api/types';

const filters = ref({ q: '', fingerprint: '', limit: 50, offset: 0 });

const queryParams = computed(() => ({
  q: filters.value.q.trim() || null,
  fingerprint: filters.value.fingerprint.trim() || null,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<MediaItemRead[]>(() =>
  apiGet('/admin/media-items', queryParams.value),
);

const columns: DataTableColumns<MediaItemRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'Source Path', key: 'source_path' },
  { title: 'Fingerprint', key: 'fingerprint', width: 200 },
  { title: 'Size', key: 'size', width: 110 },
  { title: 'MTime', key: 'mtime', width: 180, render: (row) => row.mtime ?? '—' },
  { title: 'OpenList', key: 'openlist_path' },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NInput v-model:value="filters.q" placeholder="路径关键字" style="width:240px" />
        <NInput v-model:value="filters.fingerprint" placeholder="fingerprint" style="width:220px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:120px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:120px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="媒体清单">
      <ResourceTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="无匹配记录"
      />
    </NCard>
  </NSpace>
</template>
```

- [ ] **Step 2: Manual verify**

Open `http://localhost:5173/admin/media-items`. Filter by `q=Movies` and confirm only Movies paths appear (assumes seeded data exists; if backend DB is empty, table is empty and that is fine).

- [ ] **Step 3: Type-check + commit**

```bash
cd web && pnpm exec vue-tsc --noEmit
cd /home/nax/media-pro
git add web/src/pages/MediaItemsPage.vue
git commit -m "feat: implement admin media items page"
```

---

### Task 13: TransferJobsPage

**Files:**
- Modify: `web/src/pages/TransferJobsPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { computed, h, ref } from 'vue';
import { NCard, NSpace, NButton, NInputNumber, NSelect, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { TransferJobRead } from '@/api/types';

const filters = ref<{
  status: string | null;
  route_stage: string | null;
  media_id: number | null;
  donor_user_id: number | null;
  target_user_id: number | null;
  limit: number;
  offset: number;
}>({ status: null, route_stage: null, media_id: null, donor_user_id: null, target_user_id: null, limit: 50, offset: 0 });

const statusOptions = [
  { label: 'pending', value: 'pending' },
  { label: 'running', value: 'running' },
  { label: 'succeeded', value: 'succeeded' },
  { label: 'failed', value: 'failed' },
];

const stageOptions = [
  { label: 'try_pool', value: 'try_pool' },
  { label: 'try_source_copy', value: 'try_source_copy' },
];

const queryParams = computed(() => ({
  status: filters.value.status,
  route_stage: filters.value.route_stage,
  media_id: filters.value.media_id,
  donor_user_id: filters.value.donor_user_id,
  target_user_id: filters.value.target_user_id,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<TransferJobRead[]>(() =>
  apiGet('/admin/transfer-jobs', queryParams.value),
);

function statusColor(status: string): 'success' | 'warning' | 'error' | 'default' {
  if (status === 'succeeded') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'running' || status === 'pending') return 'warning';
  return 'default';
}

const columns: DataTableColumns<TransferJobRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'Media', key: 'media_id', width: 80 },
  { title: 'Donor', key: 'donor_user_id', width: 90, render: (row) => row.donor_user_id ?? '—' },
  { title: 'Target', key: 'target_user_id', width: 90 },
  { title: 'Stage', key: 'route_stage', width: 160 },
  {
    title: 'Status', key: 'status', width: 120,
    render: (row) => h(NTag, { type: statusColor(row.status), size: 'small', bordered: false }, { default: () => row.status }),
  },
  { title: 'Error', key: 'error_code', render: (row) => row.error_code ?? '—' },
  { title: 'Attempt', key: 'attempt_no', width: 90 },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NSelect v-model:value="filters.status" :options="statusOptions" placeholder="状态" clearable style="width:140px" />
        <NSelect v-model:value="filters.route_stage" :options="stageOptions" placeholder="route_stage" clearable style="width:180px" />
        <NInputNumber v-model:value="filters.media_id" placeholder="media_id" clearable style="width:130px" />
        <NInputNumber v-model:value="filters.donor_user_id" placeholder="donor_user_id" clearable style="width:160px" />
        <NInputNumber v-model:value="filters.target_user_id" placeholder="target_user_id" clearable style="width:160px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:110px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:110px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="转存历史">
      <ResourceTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="无匹配记录"
      />
    </NCard>
  </NSpace>
</template>
```

- [ ] **Step 2: Manual verify + type-check + commit**

```bash
# manual: open http://localhost:5173/admin/transfer-jobs, apply status=failed filter
cd web && pnpm exec vue-tsc --noEmit
cd /home/nax/media-pro
git add web/src/pages/TransferJobsPage.vue
git commit -m "feat: implement admin transfer jobs page"
```

---

### Task 14: PlaybackRecordsPage

**Files:**
- Modify: `web/src/pages/PlaybackRecordsPage.vue`

- [ ] **Step 1: Replace the placeholder with real content**

```vue
<script setup lang="ts">
import { computed, h, ref } from 'vue';
import { NCard, NSpace, NButton, NInputNumber, NSelect, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { PlaybackRecordRead } from '@/api/types';

const filters = ref<{
  user_id: number | null;
  media_id: number | null;
  route: string | null;
  success: boolean | null;
  limit: number;
  offset: number;
}>({ user_id: null, media_id: null, route: null, success: null, limit: 50, offset: 0 });

const routeOptions = [
  { label: 'self', value: 'self' },
  { label: 'pool', value: 'pool' },
  { label: 'source_copy', value: 'source_copy' },
  { label: 'source_stream', value: 'source_stream' },
];

const successOptions = [
  { label: '成功', value: true },
  { label: '失败', value: false },
];

const queryParams = computed(() => ({
  user_id: filters.value.user_id,
  media_id: filters.value.media_id,
  route: filters.value.route,
  success: filters.value.success,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<PlaybackRecordRead[]>(() =>
  apiGet('/admin/playback-records', queryParams.value),
);

const columns: DataTableColumns<PlaybackRecordRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'User', key: 'user_id', width: 80 },
  { title: 'Media', key: 'media_id', width: 80 },
  { title: 'Route', key: 'route', width: 140 },
  {
    title: '结果', key: 'success', width: 90,
    render: (row) =>
      h(NTag, { type: row.success ? 'success' : 'error', size: 'small', bordered: false }, { default: () => (row.success ? '成功' : '失败') }),
  },
  { title: '延迟 (ms)', key: 'latency_ms', width: 110 },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NInputNumber v-model:value="filters.user_id" placeholder="user_id" clearable style="width:130px" />
        <NInputNumber v-model:value="filters.media_id" placeholder="media_id" clearable style="width:130px" />
        <NSelect v-model:value="filters.route" :options="routeOptions" placeholder="route" clearable style="width:160px" />
        <NSelect v-model:value="filters.success" :options="successOptions" placeholder="结果" clearable style="width:120px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:110px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:110px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="播放诊断">
      <ResourceTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="无匹配记录"
      />
    </NCard>
  </NSpace>
</template>
```

- [ ] **Step 2: Manual verify + type-check + commit**

```bash
# manual: open http://localhost:5173/admin/playback-records, apply route=source_stream filter
cd web && pnpm exec vue-tsc --noEmit
cd /home/nax/media-pro
git add web/src/pages/PlaybackRecordsPage.vue
git commit -m "feat: implement admin playback records page"
```

---

### Task 15: Migration Cutover

**Files:**
- Modify: `src/gateway/main.py`, `src/gateway/api/admin_auth.py`, `README.md`, `deploy/systemd/` (new `README.md` if absent)
- Delete: `src/gateway/api/admin_ui.py`, `tests/api/test_admin_ui.py`
- Create: `tests/api/test_admin_auth.py`, `tests/api/test_admin_spa_serving.py`

This is the only task that touches both frontend and backend together. Build first, then wire FastAPI, then migrate tests, then delete.

- [ ] **Step 1: Verify a fresh production build exists**

```bash
cd web
pnpm install
pnpm build
ls dist
```

Expected: `dist/index.html` plus `dist/assets/`.

- [ ] **Step 2: Inspect current main.py for what must change**

Read `src/gateway/main.py` and locate:
- Where `admin_ui.router` is registered (search for `admin_ui`).
- The middleware/redirect that maps `request.url.path == "/admin"` to `/admin/login`.
- The public-path allowlist (`/admin/login`, `/api/admin/login`, `/api/admin/logout`, `/api/admin/session`).

Note the exact line numbers; the edits below reference what to add/remove.

- [ ] **Step 3: Update `src/gateway/main.py`**

Remove the `admin_ui` import and `app.include_router(admin_ui.router)` line.

Remove the `if request.url.path == "/admin": return RedirectResponse("/admin/login", status_code=303)` block.

Update the public-path allowlist to allow the SPA shell paths. Replace the existing check that listed only specific paths with logic that allows anything under `/admin/` (except the API). The function that decides "is this path admin-protected?" should now read:

```python
def _is_protected_path(path: str) -> bool:
    # /api/admin/* still goes through the admin auth dependency,
    # except for the login/logout/session endpoints handled directly.
    if path in {"/api/admin/login", "/api/admin/logout", "/api/admin/session"}:
        return False
    if path.startswith("/api/admin/"):
        return True
    # /admin and /admin/* are now served by the SPA shell (static index.html);
    # client-side guard handles auth.
    return False
```

If the existing function has a different name, edit the body to the above; keep the signature.

After all other route registrations, mount the SPA shell:

```python
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

ADMIN_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"

app.mount("/admin/assets", StaticFiles(directory=ADMIN_DIST / "assets"), name="admin-assets")

@app.get("/admin", include_in_schema=False)
@app.get("/admin/{path:path}", include_in_schema=False)
def admin_spa(path: str = "") -> FileResponse:
    return FileResponse(ADMIN_DIST / "index.html")
```

If `ADMIN_DIST` is more naturally derived from a setting (e.g. `settings.web_dist_dir`), wire it through `gateway.config` instead. Keep the path resolution centralised in one place.

- [ ] **Step 4: Update `src/gateway/api/admin_auth.py`**

Remove the `@router.get("/admin/login", response_class=HTMLResponse)` route and its `admin_login_page` function. The SPA now serves `/admin/login`.

Keep: `POST /api/admin/login`, `POST /api/admin/logout`, `GET /api/admin/session` (extended in Task 2).

- [ ] **Step 5: Create `tests/api/test_admin_auth.py` from migrated tests**

This file replaces the auth coverage previously living in `tests/api/test_admin_ui.py`. Drop assertions on inline HTML; keep behavior coverage.

```python
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base


def _client(tmp_path: Path, *, admin_password: str = "") -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'auth.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(
        create_app(database_url=database_url, admin_password=admin_password)
    )


def test_admin_auth_is_disabled_when_password_is_not_configured(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        session = client.get("/api/admin/session")
        overview = client.get("/api/admin/overview")

    assert session.status_code == 200
    assert session.json() == {"auth_enabled": False, "authenticated": False}
    assert overview.status_code == 200


def test_admin_auth_protects_api_when_password_is_configured(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        no_cookie = client.get("/api/admin/overview")
        bad_login = client.post("/api/admin/login", json={"password": "wrong"})
        login = client.post("/api/admin/login", json={"password": "secret"})
        after_login = client.get("/api/admin/overview")

    assert no_cookie.status_code == 401
    assert bad_login.status_code == 401
    assert login.status_code == 200
    assert after_login.status_code == 200


def test_admin_logout_clears_session_cookie(tmp_path: Path) -> None:
    with _client(tmp_path, admin_password="secret") as client:
        login = client.post("/api/admin/login", json={"password": "secret"})
        logout = client.post("/api/admin/logout")
        after_logout = client.get("/api/admin/overview")

    assert login.status_code == 200
    assert logout.status_code == 200
    assert after_logout.status_code == 401
```

- [ ] **Step 6: Create `tests/api/test_admin_spa_serving.py`**

```python
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gateway.main import create_app
from gateway.models import Base

DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def _client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'spa.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return TestClient(create_app(database_url=database_url))


def test_admin_root_serves_index_html(tmp_path: Path) -> None:
    assert (DIST / "index.html").exists(), "web/dist/index.html missing — run `pnpm build` first"
    with _client(tmp_path) as client:
        response = client.get("/admin")

    assert response.status_code == 200
    assert "<div id=\"app\"></div>" in response.text


def test_admin_subroute_falls_through_to_index_html(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/admin/login")

    assert response.status_code == 200
    assert "<div id=\"app\"></div>" in response.text


def test_admin_assets_directory_is_mounted(tmp_path: Path) -> None:
    assets_dir = DIST / "assets"
    asset_files = list(assets_dir.iterdir())
    assert asset_files, "web/dist/assets is empty — rebuild the frontend"
    asset = next(p for p in asset_files if p.is_file())
    with _client(tmp_path) as client:
        response = client.get(f"/admin/assets/{asset.name}")
    assert response.status_code == 200
```

- [ ] **Step 7: Delete the old admin UI and its tests**

```bash
git rm src/gateway/api/admin_ui.py tests/api/test_admin_ui.py
```

- [ ] **Step 8: Update README**

In `README.md`, under `## 当前阶段`, replace the bullet about admin UI to read:

```markdown
- 已经具备 Vue 3 + Naive UI 的正式管理后台（侧边栏分组 / 运营、数据、诊断），覆盖 overview、users、drives、pool、media-items、transfer-jobs、playback-records 7 个视图
```

Add a new top-level section before `## MVP Route Order` (or the closest equivalent):

```markdown
## 前端开发约定

- 前端代码在 `web/`，Vue 3 + Vite + Naive UI + TypeScript，包管理用 pnpm。
- 本地开发同时跑两个进程：`uvicorn gateway.main:app --reload --port 8000` 和 `cd web && pnpm dev`。Vite 把 `/api/*` 代理到 `:8000`。
- 部署前需执行 `cd web && pnpm install && pnpm build` 生成 `web/dist/`，FastAPI 会从该目录挂载 `/admin/assets` 并对其它 `/admin/*` 路径返回 `index.html`。
- TS 类型在 `web/src/api/types.ts` 中手动镜像 `src/gateway/schemas.py`；改后端字段时同步更新前端。
```

- [ ] **Step 9: Update deploy notes**

If `deploy/systemd/README.md` exists, append:

```markdown

## 前端构建

发布前请执行：

```bash
cd web
pnpm install
pnpm build
```

如果跳过，FastAPI 启动后访问 `/admin` 会因为 `web/dist/` 不存在而 500。
```

If `deploy/systemd/README.md` does not exist, create it with just the above block (plus a one-line opening header `# media-pro systemd deploy`).

- [ ] **Step 10: Run the full backend test suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass. The original 176 minus the 4 from `test_admin_ui.py` plus 3 in `test_admin_auth.py` plus 4 in `test_admin_session.py` plus 3 in `test_admin_spa_serving.py` = approximately 182 tests.

If the SPA smoke tests fail because the test environment cannot find `web/dist/`, the build step in Task 15 Step 1 was skipped or failed — fix that before continuing.

- [ ] **Step 11: Manual end-to-end verify**

Build, then run only the FastAPI process (no Vite dev server):

```bash
cd web && pnpm build && cd ..
.venv/bin/uvicorn gateway.main:app --port 8000
```

Open `http://localhost:8000/admin`. Expected:

- Redirects to `/admin/overview`
- Sidebar shows the 3 groups, 7 items
- Each page loads its data (cards / table)
- With `GATEWAY_ADMIN_PASSWORD=secret` set in the env, you are redirected to `/admin/login`; entering the wrong password shows the error; correct password redirects to `/admin/overview`; 退出 returns to login
- `GET /admin/login` directly returns the SPA shell (not the old server-rendered form)

- [ ] **Step 12: Commit**

```bash
git add src/gateway/main.py src/gateway/api/admin_auth.py tests/api/test_admin_auth.py tests/api/test_admin_spa_serving.py README.md deploy/systemd/README.md
git rm src/gateway/api/admin_ui.py tests/api/test_admin_ui.py  # already staged in Step 7 if rm ran
git commit -m "feat: cut over admin /admin to vue spa"
```

---

### Task 16: Final Verification

**Files:**
- No edits expected

- [ ] **Step 1: Run the full backend suite**

```bash
.venv/bin/pytest -q
```

Expected: all pass.

- [ ] **Step 2: Run the full frontend suite**

```bash
cd web
pnpm test
```

Expected: all pass.

- [ ] **Step 3: Type-check the frontend**

```bash
cd web
pnpm exec vue-tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Production build smoke**

```bash
cd web
pnpm build
ls dist/index.html dist/assets
```

Expected: both exist.

- [ ] **Step 5: Branch state**

```bash
cd /home/nax/media-pro
git status --short --branch
git log --oneline -20
```

Expected: working tree clean, 16 new commits on top of the spec commit (`fb57771`).

- [ ] **Step 6: Record implementation outcome**

Add a short note to the final response:

```text
Implemented:
- Vue 3 + Vite + Naive UI admin SPA at web/
- 7 pages (overview/users/drives/pool/media-items/transfer-jobs/playback-records)
- Extended /api/admin/session with authenticated field
- Migration cutover: admin_ui.py and its tests deleted, FastAPI mounts web/dist/ at /admin

Verification:
- .venv/bin/pytest -q (backend)
- cd web && pnpm test && pnpm exec vue-tsc --noEmit && pnpm build (frontend)
- Manual: http://localhost:8000/admin with and without GATEWAY_ADMIN_PASSWORD
```

Do not create an additional commit for this note.

---

## Self-Review

Spec coverage:

- Repository layout (`web/` + Python service) — Task 1.
- API client + types mirror gateway.schemas — Task 3.
- `useApi` composable contract — Task 4.
- Pinia stores (session + catalog only) — Task 5.
- App shell with sidebar three groups + auth router guard + login page — Task 6.
- Generic `ResourceTable` — Task 7.
- Each of the 7 pages — Tasks 8–14.
- Backend extension of `/api/admin/session` with `authenticated` — Task 2 (placed early so router guard works in Task 6).
- Migration cutover: delete `admin_ui.py`, delete `GET /admin/login` HTML route, mount StaticFiles + SPA fallback, migrate auth tests, update main.py allowlist, README, deploy notes, SPA smoke tests — Task 15.
- Backend tests `test_admin_session.py`, `test_admin_auth.py`, `test_admin_spa_serving.py` — Tasks 2 and 15.
- Frontend tests `client.test.ts`, `useApi.test.ts`, `ResourceTable.test.ts` — Tasks 3, 4, 7.

Scope boundaries:

- No dark mode, i18n, mobile-deep, charts, real-time, Playwright — all explicitly absent from the plan.
- Plan does not touch the database schema, the playback resolver, or any provider strategy beyond consuming the read-only `/api/admin/drive-types` catalog.

Type consistency:

- TS types in `web/src/api/types.ts` use `snake_case` field names matching Pydantic; pages destructure these consistently (`source_path`, `route_stage`, `target_user_id`, etc.).
- Router uses `meta.title` and `meta.group`; App.vue and the menu both reference these by the same names.
- `useSessionStore` exposes `authEnabled` and `authenticated` (camelCase TS), populated from `auth_enabled` / `authenticated` in the API response. Router guard and App.vue both read the camelCase store fields.
