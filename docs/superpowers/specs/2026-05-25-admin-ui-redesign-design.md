# Admin UI Redesign Design

> Date: 2026-05-25
> Spec status: draft, pending implementation plan

## Goal

Replace the inline `src/gateway/api/admin_ui.py` (778-line single-file SPA-ish HTML) with a proper Vue 3 + Vite + Naive UI project under `web/`, wire it into FastAPI as a single-page application served at `/admin`, and bring the four newly-added admin APIs (`drive-types`, `media-items`, `transfer-jobs`, `playback-records`) into the UI for the first time.

This is the first step from the "NextEmby-like 泛云盘媒体缓存" foundation (see `docs/superpowers/specs/2026-05-25-media-pro-nextemby-like-positioning-design.md`) that touches the front end.

## Non-Goals

The following are explicitly out of scope for this spec and are deferred to later specs:

- User-facing portal: user table, user login, user self-service drive binding
- Provider strategy refactor beyond consuming the read-only `drive-types` catalog
- caiyun OAuth jump (admin still pastes tokens by hand into the new drive form)
- Dark-mode theme
- i18n / language switching (Chinese only)
- Deep mobile-responsive design (sidebar collapses, but no separate mobile layout)
- Charts and visualizations
- Real-time push (polling + manual refresh is enough)
- A separate form-validation framework (Naive UI built-ins + native HTML5 validation are enough)

## Architecture Decisions

### Stack

- **Vue 3** + Composition API + `<script setup>` SFC syntax
- **Vite** as dev server + build tool
- **Naive UI** as the component library; default light theme tuned to align with the existing teal palette (`#0f766e`)
- **Vue Router 4** in history mode
- **Pinia** for shared state (session + drive-types catalog only — no per-resource stores)
- **TypeScript** for type-safety on the API boundary
- **pnpm** as the package manager

No additional runtime dependencies (no axios, no `@tanstack/vue-query`, no Tailwind, no UI kit beyond Naive UI).

### Repository Layout

```
media-pro/
├── src/gateway/...            # existing FastAPI service, untouched except main.py and admin_ui.py removal
├── web/                       # new Vue project
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts         # dev proxy: /api -> http://localhost:8000
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/                # static assets (favicon, etc.)
│   └── src/
│       ├── main.ts            # creates app, installs router/pinia/naive
│       ├── App.vue            # NLayout shell: sider + header + content
│       ├── router/index.ts
│       ├── stores/
│       │   ├── session.ts     # useSessionStore
│       │   └── catalog.ts     # useCatalogStore (drive-types)
│       ├── api/
│       │   ├── client.ts      # apiGet/apiPost/apiDelete on /api
│       │   └── types.ts       # TS types mirroring gateway.schemas
│       ├── composables/
│       │   └── useApi.ts      # { data, loading, error, refresh }
│       ├── components/
│       │   ├── ResourceTable.vue   # generic Naive UI DataTable wrapper
│       │   ├── StatusPill.vue
│       │   └── PaginationBar.vue
│       └── pages/
│           ├── LoginPage.vue
│           ├── OverviewPage.vue
│           ├── UsersPage.vue
│           ├── DrivesPage.vue
│           ├── PoolPage.vue
│           ├── MediaItemsPage.vue
│           ├── TransferJobsPage.vue
│           └── PlaybackRecordsPage.vue
└── docs/superpowers/...
```

Build output `web/dist/` is `.gitignored`. The whole `web/` directory is committed except `node_modules/`, `dist/`, `.vite/`.

### Routes and Navigation

Vue Router (history mode) covers the following paths:

| Path | Component | Group |
|---|---|---|
| `/admin/login` | `LoginPage` | (none) |
| `/admin/` (redirect to `/admin/overview`) | — | — |
| `/admin/overview` | `OverviewPage` | 运营 |
| `/admin/users` | `UsersPage` | 运营 |
| `/admin/drives` | `DrivesPage` | 运营 |
| `/admin/pool` | `PoolPage` | 运营 |
| `/admin/media-items` | `MediaItemsPage` | 数据 |
| `/admin/transfer-jobs` | `TransferJobsPage` | 诊断 |
| `/admin/playback-records` | `PlaybackRecordsPage` | 诊断 |

The sidebar (NMenu) renders three groups: 运营 (overview/users/drives/pool), 数据 (media-items), 诊断 (transfer-jobs/playback-records).

### API Layer

`web/src/api/client.ts` is a thin `fetch()` wrapper:

- Base path `/api`
- Sends and accepts JSON; sends cookies
- 401 → emit a session-expired event and route to `/admin/login`
- Non-2xx → throw `ApiError(status, body)`
- Surface: `apiGet<T>(path, params?)`, `apiPost<T>(path, body)`, `apiDelete<T>(path)`

`web/src/api/types.ts` hand-writes TS types mirroring `src/gateway/schemas.py`. Each TS type has a comment `// mirrors gateway.schemas.XxxRead` so backend changes are easy to grep for and update on the front end. No OpenAPI codegen toolchain.

`composables/useApi.ts` returns reactive `{ data, loading, error, refresh }` for a fetch function passed in. No caching, no SWR, no optimistic updates. State lives for the duration of the page that called it.

### State (Pinia)

Two stores only:

- **`useSessionStore`** — `authenticated: boolean`, `logout()`. Cookie is written by the backend; the store just reflects state.
- **`useCatalogStore`** — `driveTypes: DriveTypeRead[]`, loaded once at app mount. Used by `DrivesPage` to render the right credential fields per drive type.

All other resources (users, drives, pool objects, media items, transfer jobs, playback records) live in page-local `useApi()` state and refetch on navigation.

### Auth Flow

The existing `src/gateway/api/admin_auth.py` cookie-session flow is preserved:

- `GATEWAY_ADMIN_PASSWORD` unset → backend lets everything through; `LoginPage` is skipped by checking `/api/admin/session`
- `GATEWAY_ADMIN_PASSWORD` set → admin endpoints require the cookie

Router `beforeEach` guard:
1. If route is `/admin/login`, allow.
2. Otherwise GET `/api/admin/session`. If `auth_enabled` is `false`, allow. If `auth_enabled` is `true` and `authenticated` is `true`, allow. Otherwise push to `/admin/login` with a `next` query parameter.
3. `LoginPage` POSTs `{password}` (no username; the existing endpoint only takes a password) to `/api/admin/login`; on success, redirect to `next`.

**Backend change:** extend the existing `GET /api/admin/session` endpoint in `src/gateway/api/admin_auth.py`. Today it returns `{auth_enabled: bool}`. It will additionally return `authenticated: bool` (verified via the same logic as the auth dependency / `admin_session_is_valid`). This is a small expansion, not a new endpoint.

### Dev and Build

- **Dev:** `pnpm dev` runs Vite (default port 5173). `vite.config.ts` proxies `/api/*` → `http://localhost:8000`. FastAPI runs separately under `uvicorn`. HMR works.
- **Build:** `pnpm build` outputs to `web/dist/`.
- **Prod:** FastAPI mounts the built artifact:

```python
# src/gateway/main.py
app.mount("/admin/assets", StaticFiles(directory="web/dist/assets"), name="admin-assets")

@app.get("/admin/{path:path}", include_in_schema=False)
def admin_spa(path: str) -> FileResponse:
    return FileResponse("web/dist/index.html")
```

The SPA fallback returns `index.html` for any path under `/admin/` that does not match a static asset. `/api/*` keeps its routes ahead of the fallback.

If `web/dist/` does not exist (e.g. forgot to build), the static mount and the fallback both 500 with a clear message; covered by a smoke test.

### Migration Cutover

A single commit performs the cutover at the end of the plan:

1. Delete `src/gateway/api/admin_ui.py`.
2. Move the auth coverage out of `tests/api/test_admin_ui.py` into a new `tests/api/test_admin_auth.py` (or rename), keeping the three auth-flow tests (auth disabled, auth enabled / login + protected access, logout clears cookie) and dropping the UI-HTML smoke test. Update them to no longer assert on the inline HTML page content and to assert on the new `authenticated` field where relevant. Then delete `tests/api/test_admin_ui.py`.
3. In `src/gateway/api/admin_auth.py`, delete the `GET /admin/login` HTML route (the SPA now serves this path). Keep `POST /api/admin/login`, `POST /api/admin/logout`, and `GET /api/admin/session` (extended per the Auth Flow section above).
4. In `src/gateway/main.py`:
   - Unmount `admin_ui.router`.
   - Update the public-path allowlist that currently lists `/admin/login` etc. so that any path under `/admin/` (except `/api/admin/*`) is served by the SPA, while API routes under `/api/admin/*` still go through the existing auth dependency.
   - Replace the `/admin → /admin/login` redirect with a static mount + SPA fallback:
     ```python
     app.mount("/admin/assets", StaticFiles(directory="web/dist/assets"), name="admin-assets")

     @app.get("/admin", include_in_schema=False)
     @app.get("/admin/{path:path}", include_in_schema=False)
     def admin_spa(path: str = "") -> FileResponse:
         return FileResponse("web/dist/index.html")
     ```
5. Update README's `## 当前阶段` section to note that admin is now served as a Vue SPA.
6. Add a short note in `deploy/systemd/` README (or a new fragment) saying release requires `pnpm install && pnpm build` first.

Rollback is `git revert` on that single commit. Before the cutover commit, the Vue project must already cover all four existing views plus the three new views and the login flow; the cutover does not introduce new functionality.

## Testing Strategy

### Backend (pytest)

- The existing 176 tests remain untouched **except** for the auth coverage currently living in `tests/api/test_admin_ui.py`, which is migrated into `tests/api/test_admin_auth.py` (see Migration Cutover step 2).
- Add `tests/api/test_admin_session.py` covering the **extended** `/api/admin/session` endpoint: `auth_enabled` false + `authenticated` false; `auth_enabled` true + no cookie → `authenticated` false; `auth_enabled` true + valid cookie → `authenticated` true; `auth_enabled` true + expired cookie → `authenticated` false.
- Add `tests/api/test_admin_spa_serving.py`:
  - `GET /admin/` returns 200 with HTML.
  - `GET /admin/login` falls through to `index.html`.
  - `GET /admin/assets/<known asset>` returns 200.
  - When `web/dist/` is missing, the mount surfaces a clear error (verified via temporary monkeypatch).

### Frontend (Vitest)

- `api/client.test.ts` — `fetch` wrapper: 401 routing, non-2xx error normalization, query string building.
- `composables/useApi.test.ts` — loading/error/refresh state machine.
- `components/ResourceTable.test.ts` — props contract for the generic DataTable wrapper.

Page-level component tests are not written; cost/benefit is poor at this size.

### End-to-end

Not in scope. No Playwright. The SPA smoke tests above plus manual verification cover this iteration.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| pnpm/Node toolchain becomes a new dependency for deploy and CI | Deploy and CI need Node available | systemd unit doesn't change; Node is only required at build time. Document `pnpm install && pnpm build` as a release step. |
| `web/` subdir + Python single-repo creates a polyglot layout | Repo complexity rises | `.gitignore` adds `web/node_modules`, `web/dist`, `web/.vite`. README adds a "前端开发约定" section explaining the layout. |
| Mirroring Pydantic schemas to TS types drifts when backend changes | Front end silently breaks when schema changes | Every TS type carries a `// mirrors gateway.schemas.XxxRead` comment; the plan explicitly requires updating both sides in the same task when adding a field. |
| Cookie session compatibility during cutover | Admins are logged out the moment we switch | `admin_auth` backend behavior does not change; only the UI shell changes. Existing cookies remain valid. |
| `web/dist/` missing in production | `/admin` 500s | Smoke test catches this. Deploy README emphasizes the build step. |

## Success Criteria

- All seven pages render and read from their `/api/admin/*` endpoints.
- Login page works for both `GATEWAY_ADMIN_PASSWORD` set and unset cases.
- `pnpm build` produces `web/dist/` that FastAPI serves cleanly at `/admin`.
- Existing 176 backend tests still pass; the new session + SPA smoke tests pass; the new Vitest tests pass.
- `admin_ui.py` and `test_admin_ui.py` are removed.
- README and deploy notes reflect the new layout.
