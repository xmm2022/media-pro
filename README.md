# GD Source-First Playback Gateway

一个面向 Emby / 媒体网关场景的后端 MVP。当前项目以 FastAPI 为核心，目标是围绕 `GD / OpenList` 媒体源、用户贡献的 `115` 账号池，以及“优先本地命中、其次池内复用、最后回源”的播放决策链路，先搭出一个可运行、可联调、可继续扩展的服务骨架。

## 当前阶段

当前仓库还没有前端页面，项目形态是“后端 API + 数据模型 + 验证脚本 + 测试集”。

可以把它理解为：

- 已经具备本地启动、接口联调、数据库持久化、基础播放决策和运维验证能力
- 还没有 Web 管理后台、用户认证、真实生产部署方案和完整业务闭环
- 更适合当前阶段作为技术验证版 / 联调版，而不是直接当最终生产系统

## MVP Route Order

The playback decision order is `self -> pool -> source_copy -> source_stream`.

## 当前已经实现

- FastAPI 应用骨架与 `/health` 健康检查
- OpenList 与 rapid-copy 适配器契约及基础验证脚本
- SQLAlchemy 模型、Alembic 迁移、SQLite 持久化
- Drive cookie 加密存储
- 管理员用户与 drive 录入接口
- pool object 健康状态查询与手动恢复接口
- 播放路由状态机
- transfer idempotency key 生成
- 播放预算控制
- 管理员 stats 持久化查询
- worker cooldown 恢复 helper
- 本地 smoke 校验脚本与完整测试集

## 当前还没有实现

- 前端管理页面
- 登录认证、权限控制、多角色管理
- 真实 OpenList / 115 环境下的全链路联调闭环
- 完整的任务调度、后台 worker 运行体系
- Docker / systemd / 反向代理等部署方案
- 生产级日志、监控、告警、限流和异常恢复

## 技术栈

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- cryptography
- pytest
- uv

## 项目结构

```text
src/gateway/
  api/                   HTTP 接口
  integrations/          OpenList / rapid-copy 适配器
  models.py              数据模型
  db.py                  数据库与 session 管理
  security.py            cookie 加密
  playback.py            播放路由决策
  transfer.py            幂等 key 等传输辅助逻辑
  pool.py                donor 选择逻辑
  workers.py             worker / cooldown helper
  audit.py               审计与汇总 helper

scripts/
  validate_openlist_stream.py
  validate_rapid_copy.py
  verify_mvp.py

tests/
  api/
  integrations/
  playback/
  transfer/
  workers/
  ...
```

## 快速启动

```bash
cp .env.example .env
uv sync
uv run uvicorn gateway.main:app --reload
```

启动后默认服务入口为：

- `GET /health`
- `POST /api/admin/users`
- `GET /api/admin/drives`
- `POST /api/admin/drives`
- `POST /api/admin/drives/{drive_id}/probe`
- `POST /api/admin/drives/probe`
- `POST /api/admin/drives/disable`
- `POST /api/admin/drives/enable`
- `POST /api/admin/drives/delete`
- `PATCH /api/admin/drives/{drive_id}`
- `DELETE /api/admin/drives/{drive_id}`
- `POST /api/admin/catalog/sync`
- `GET /api/admin/stats`
- `GET /api/admin/overview`
- `GET /api/admin/drives/stats`
- `GET /api/admin/pool-objects`
- `GET /api/admin/pool-objects/stats`
- `POST /api/admin/pool-objects/recover`
- `POST /api/admin/pool-objects/disable`
- `POST /api/admin/pool-objects/enable`
- `POST /api/admin/pool-objects/{pool_object_id}/recover`
- `GET /api/playback/{media_id}`
- `GET /api/playback/{media_id}/stream`

## 环境变量说明

示例文件见 [.env.example](./.env.example)。

当前关键配置项：

- `GATEWAY_DATABASE_URL`
  - 默认值：`sqlite:///./gateway.db`
  - 用于本地 SQLite 或后续替换成真实数据库连接串
- `GATEWAY_COOKIE_SECRET`
  - 用于加密保存 drive cookie
  - 必须替换成你自己的随机长字符串
- `GATEWAY_OPENLIST_BASE_URL`
  - OpenList 服务地址
- `GATEWAY_OPENLIST_TOKEN`
  - OpenList Token
- `GATEWAY_OPENLIST_ADMIN_TOKEN`
  - OpenList admin token
  - caiyun / 139Yun storage 创建、复用已有 storage、删除 managed storage、`fs/copy` 都需要它
- `GATEWAY_OPENLIST_COPY_VERIFY_ATTEMPTS`
  - caiyun / 139Yun `source_copy` 后等待目标文件在 OpenList 可见的最大探测次数
  - 默认值：`30`
- `GATEWAY_OPENLIST_COPY_VERIFY_INTERVAL_SECONDS`
  - 每次目标文件可见性探测之间的等待秒数
  - 默认值：`1.0`
- `GATEWAY_RAPID_COPY_BASE_URL`
  - rapid-copy 服务地址
- `GATEWAY_OPENLIST_PROBE_PATH`
  - OpenList 实际探针文件路径
- `GATEWAY_CATALOG_ROOT_PATH`
  - catalog sync 读取的 OpenList 根目录
- `GATEWAY_RAPID_COPY_DONOR_COOKIE`
  - `pool / P2P` 探针 donor `115` cookie
- `GATEWAY_RAPID_COPY_TARGET_COOKIE`
  - `pool / P2P` 与 `source_copy / O2P` 共用的 target `115` cookie
- `GATEWAY_RAPID_COPY_SOURCE_PATH`
  - `pool / P2P` 或 `source_copy / O2P` 的源路径
- `GATEWAY_RAPID_COPY_TARGET_PATH`
  - `pool / P2P` 或 `source_copy / O2P` 的目标路径

Set `GATEWAY_COOKIE_SECRET` in `.env` before storing real drive cookies through the admin API. Keep `GATEWAY_DATABASE_URL` pointed at the SQLite file or database you want the gateway to manage.

如果已有 `gateway.db`，升级新版代码后先备份并迁移：

```bash
cp gateway.db gateway.db.bak-$(date +%Y%m%d%H%M%S)
uv run alembic upgrade head
```

如果 `gateway.db` 还不存在，应用启动时会自动创建当前模型对应的表结构。

## 当前接口说明

### `GET /health`

返回服务健康状态：

```json
{"status": "ok"}
```

### `POST /api/admin/users`

创建一个管理员侧用户记录。

请求示例：

```json
{
  "username": "alice",
  "status": "active"
}
```

### `POST /api/admin/drives`

为某个用户录入 drive 账号信息。`115` 的 cookie 会加密落库；`caiyun` 的 token 默认交给 OpenList storage 保存，media-pro 只保存 mount path。

`115` 请求示例：

```json
{
  "user_id": 1,
  "drive_type": "115",
  "cookie": "UID=1; CID=2",
  "root_dir": "/EmbyCache/alice",
  "share_pool_enabled": true
}
```

让 media-pro 创建并管理新的 139Yun / caiyun OpenList storage：

```json
{
  "user_id": 1,
  "drive_type": "caiyun",
  "root_dir": "/EmbyCache",
  "mount_path": "/caiyun-alice",
  "caiyun": {
    "access_token": "<139 access token>",
    "refresh_token": "<139 refresh token>",
    "account_type": "personal_new"
  }
}
```

复用 OpenList 里已经存在的 139Yun / caiyun storage，例如 `/yidon`：

```json
{
  "user_id": 1,
  "drive_type": "caiyun",
  "root_dir": "/",
  "mount_path": "/yidon",
  "adopt_existing": true
}
```

`adopt_existing=true` 会把该 drive 标记为 `openlist_storage_managed=false`：

- media-pro 只绑定已有 OpenList storage
- 不创建新的 OpenList storage
- 不更新该 storage 的 token
- 删除 media-pro drive 时不会删除 OpenList 里的原 storage

如果目标目录尚未存在，先用 `root_dir="/"`。例如 `/yidon/EmbyCache` 不存在时，`root_dir="/EmbyCache"` 会让 copy 目标落到不存在的目录下。

返回里会包含当前 donor 运维常用字段：

- `enabled`
- `share_pool_enabled`
- `health_status`
- `last_checked_at`
- `cookie_preview`
- `openlist_mount_path`
- `openlist_storage_managed`

### `POST /api/admin/drives/{drive_id}/probe`

对单个 drive 执行一次手动探活，并回写：

- `health_status`
- `last_checked_at`

当前探活策略：

- `115`
  - 校验 cookie 是否还能拿到 `upload_info.userkey`
  - 校验或创建 `root_dir`，确认目标缓存目录可用
- `alist`
  - 通过 OpenList 列举 `root_dir`，确认路径仍可访问
- `caiyun`
  - 通过 OpenList admin token 列举 `openlist_mount_path`
  - 可返回 `healthy`、`invalid_token`、`mount_missing`、`openlist_http_error`、`openlist_admin_failed`

返回示例：

```json
{
  "ok": true,
  "error_code": null,
  "detail": null,
  "drive": {
    "id": 7,
    "user_id": 3,
    "drive_type": "115",
    "root_dir": "/EmbyCache/alice",
    "enabled": true,
    "share_pool_enabled": false,
    "health_status": "healthy",
    "last_checked_at": "2026-05-20T11:00:00Z",
    "cookie_preview": "UID=a..."
  }
}
```

常见失败状态：

- `invalid_cookie`
- `root_dir_unavailable`
- `openlist_auth_failed`
- `openlist_http_error`
- `probe_failed`
- `unsupported_drive_type`

### `POST /api/admin/drives/probe`

按选择器批量执行 drive 探活。支持的选择器：

- `ids`
- `user_id`
- `drive_type`
- `enabled`
- `share_pool_enabled`

这条接口适合在真实多账号联调前，一次性刷新整批 donor 的健康状态。

请求示例：

```json
{
  "enabled": true
}
```

返回示例：

```json
{
  "matched": 2,
  "healthy": 1,
  "unhealthy": 1,
  "drive_ids": [1, 2],
  "results": [
    {
      "ok": true,
      "error_code": null,
      "detail": null,
      "drive": {
        "id": 1,
        "user_id": 1,
        "drive_type": "115",
        "root_dir": "/EmbyCache/alice",
        "enabled": true,
        "share_pool_enabled": true,
        "health_status": "healthy",
        "last_checked_at": "2026-05-20T11:10:00Z",
        "cookie_preview": "UID=a..."
      }
    },
    {
      "ok": false,
      "error_code": "invalid_cookie",
      "detail": "cookie expired",
      "drive": {
        "id": 2,
        "user_id": 2,
        "drive_type": "115",
        "root_dir": "/EmbyCache/bob",
        "enabled": true,
        "share_pool_enabled": false,
        "health_status": "invalid_cookie",
        "last_checked_at": "2026-05-20T11:10:00Z",
        "cookie_preview": "UID=b..."
      }
    }
  ]
}
```

### `GET /api/admin/drives`

列出当前所有 drive 账号，并支持按以下参数过滤：

- `user_id`
- `drive_type`
- `enabled`
- `share_pool_enabled`

这条接口适合用来查看当前哪些 115 账号已启用、哪些账号开放了 pool 共享。

### `PATCH /api/admin/drives/{drive_id}`

更新单个 drive 账号的运维字段。当前支持：

- `cookie`
- `root_dir`
- `enabled`
- `share_pool_enabled`
- `health_status`
- `caiyun`

请求示例：

```json
{
  "enabled": false,
  "share_pool_enabled": false,
  "health_status": "cooldown"
}
```

这条接口主要用于 donor 账号级别的开关和维护，不需要去直接改数据库。

对 `caiyun`：

- managed storage 可通过 `caiyun` 字段更新 OpenList storage token
- adopted storage 即 `openlist_storage_managed=false` 会拒绝 token 更新并返回 `409 storage_unmanaged`

当前联动规则：

- `enabled=false`
  - 自动把该 drive `root_dir` 下的 pool objects 标记为 `disabled`
- `enabled=true`
  - 自动把该 drive `root_dir` 下已 `disabled` 的 pool objects 恢复为 `ready`
- `root_dir` 变更
  - 自动把旧 `root_dir` 下的 pool objects 标记为 `disabled`
- `share_pool_enabled`
  - 只影响 donor 是否参与池共享，不改 pool object 状态

### `POST /api/admin/drives/disable`

按选择器批量停用 drive。支持的选择器：

- `ids`
- `user_id`
- `drive_type`
- `enabled`
- `share_pool_enabled`

当前行为：

- 将选中的 drive 批量设为 `enabled=false`
- 自动停用这些 drive `root_dir` 下的 pool objects

### `POST /api/admin/drives/enable`

按选择器批量启用 drive。

当前行为：

- 将选中的 drive 批量设为 `enabled=true`
- 自动恢复这些 drive `root_dir` 下已 `disabled` 的 pool objects

### `POST /api/admin/drives/delete`

按选择器批量删除 drive。

当前行为：

- 先停用这些 drive `root_dir` 下的 pool objects
- 再删除 drive 记录本身
- 返回命中的 `drive_ids` 和联动修改的 pool object 数量

### `DELETE /api/admin/drives/{drive_id}`

删除一个 drive 账号记录。

当前行为：

- 先把该 drive `root_dir` 下的 pool objects 标记为 `disabled`
- 再删除 drive 账号本身
- `caiyun` 且 `openlist_storage_managed=true` 时，会同时删除对应 OpenList storage
- `caiyun` 且 `openlist_storage_managed=false` 时，只删除本地 drive 记录，不删除 OpenList 里的已有 storage
- 返回本次联动停用的 pool object 数量

返回示例：

```json
{
  "drive_id": 7,
  "user_id": 3,
  "disabled_pool_objects": 12
}
```

### `POST /api/admin/catalog/sync`

从 OpenList 根目录同步媒体目录到本地 `media_items`。

请求示例：

```json
{
  "root_path": "/Movies"
}
```

### `GET /api/admin/stats`

返回当前 playback route 的统计桶：

```json
{
  "self": 0,
  "pool": 0,
  "source_copy": 0,
  "source_stream": 0
}
```

### `GET /api/admin/overview`

返回管理首页可直接消费的总览数据：

- `routes`
  - playback route 统计桶
- `drives.stats`
  - drive 聚合统计
- `drives.attention_total`
  - 需要关注的 drive 数量，当前规则是 `enabled=false` 或 `health_status != healthy`
- `drives.probe_error_distribution`
  - 最近已探活且结果非 `healthy` 的错误分布
- `drives.stale_probe_count`
  - `last_checked_at` 为空，或早于阈值的 drive 数量
- `drives.stale_probe_threshold_hours`
  - 计算 `stale_probe_count` 时使用的小时阈值
- `drives.items`
  - 默认最多返回前 `10` 条需要关注的 drive，可通过 `drive_limit` 调整
- `pool_objects.stats`
  - pool objects 聚合统计
- `pool_objects.attention_total`
  - 当前 `status != ready` 的对象数量
- `pool_objects.items`
  - 默认最多返回前 `10` 条异常对象，可通过 `pool_object_limit` 调整

请求参数：

- `drive_limit`
  - 默认 `10`，范围 `0-100`
- `pool_object_limit`
  - 默认 `10`，范围 `0-100`
- `stale_probe_after_hours`
  - 默认 `24`，范围 `1-720`

返回示例：

```json
{
  "routes": {
    "self": 1,
    "pool": 0,
    "source_copy": 0,
    "source_stream": 2
  },
  "drives": {
    "stats": {
      "total": 3,
      "users": 2,
      "enabled": 2,
      "disabled": 1,
      "share_pool_enabled": 1,
      "by_drive_type": {
        "115": 3
      },
      "by_health_status": {
        "healthy": 2,
        "unknown": 1
      }
    },
    "attention_total": 2,
    "probe_error_distribution": {
      "invalid_cookie": 1
    },
    "stale_probe_count": 1,
    "stale_probe_threshold_hours": 24,
    "items": []
  },
  "pool_objects": {
    "stats": {
      "total": 4,
      "owners": 2,
      "media_items": 3,
      "by_status": {
        "ready": 1,
        "suspect": 0,
        "cooldown": 1,
        "disabled": 1,
        "stale": 1
      },
      "by_drive_type": {
        "115": 4
      },
      "cooldown_active": 1,
      "cooldown_expired": 0
    },
    "attention_total": 3,
    "items": []
  }
}
```

### `GET /api/admin/drives/stats`

返回当前 drive 账号聚合统计，适合快速观察 donor 池规模、启用状态和健康状态分布：

```json
{
  "total": 3,
  "users": 2,
  "enabled": 2,
  "disabled": 1,
  "share_pool_enabled": 1,
  "by_drive_type": {
    "115": 2,
    "alist": 1
  },
  "by_health_status": {
    "healthy": 2,
    "cooldown": 1
  }
}
```

### `GET /api/admin/pool-objects`

返回当前缓存 / donor 对象及其健康状态，可按查询参数过滤：

- `status`
- `owner_user_id`
- `media_id`

返回示例：

```json
[
  {
    "id": 1,
    "media_id": 42,
    "owner_user_id": 7,
    "drive_type": "115",
    "target_path": "/EmbyCache/alice/Movies/Movie.2024.mkv",
    "status": "cooldown",
    "last_verified_at": null,
    "last_success_at": null,
    "last_failure_at": "2026-05-19T23:00:00",
    "failure_count": 2,
    "cooldown_until": "2026-05-19T23:10:00"
  }
]
```

### `GET /api/admin/pool-objects/stats`

返回当前 pool objects 聚合统计，适合观察缓存对象状态分布、来源盘类型分布，以及 `cooldown` 是否仍在生效：

```json
{
  "total": 4,
  "owners": 2,
  "media_items": 2,
  "by_status": {
    "ready": 1,
    "suspect": 0,
    "cooldown": 2,
    "disabled": 0,
    "stale": 1
  },
  "by_drive_type": {
    "115": 3,
    "alist": 1
  },
  "cooldown_active": 1,
  "cooldown_expired": 1
}
```

### `POST /api/admin/pool-objects/{pool_object_id}/recover`

手动恢复一个 `stale / cooldown / suspect` 的 pool object，让它重新回到 `ready` 可选状态。

当前行为：

- 将 `status` 重置为 `ready`
- 清空 `cooldown_until`
- 将 `failure_count` 重置为 `0`

### `POST /api/admin/pool-objects/recover`

按选择器批量恢复 pool object。

支持的选择器：

- `ids`
- `owner_user_id`
- `media_id`
- `statuses`

如果没有显式传 `statuses`，默认只恢复：

- `cooldown`
- `stale`
- `suspect`

请求示例：

```json
{
  "owner_user_id": 7
}
```

这适合在某个 donor 恢复可用后，一次性把它名下的异常对象重新放回候选池。

### `POST /api/admin/pool-objects/disable`

按选择器批量禁用 pool object。最常见的用法是按 `owner_user_id` 一次性禁用某个 donor 的全部共享对象。

请求示例：

```json
{
  "owner_user_id": 7
}
```

### `POST /api/admin/pool-objects/enable`

按选择器批量重新启用 pool object。默认只会匹配当前 `disabled` 的对象，并把它们恢复为 `ready`。

请求示例：

```json
{
  "owner_user_id": 7
}
```

### `GET /api/playback/{media_id}`

按真实用户上下文返回播放决策结果，并给出网关自身的可播放流地址。

请求参数：

- `user_id`
  - 当前播放用户，用于命中当前用户缓存、共享池 donor 和 source copy 目标盘

返回示例：

```json
{
  "user_id": 7,
  "media_id": 42,
  "route": "source_copy",
  "stream_url": "http://gateway.local/api/playback/42/stream?token=...",
  "upstream_stream_url": "https://115cdn.local/media/42.mkv",
  "upstream_stream_headers": {
    "user-agent": ""
  }
}
```

### `GET /api/playback/{media_id}/stream`

网关代理实际播放流：

- 优先使用签名 `token` 参数访问，旧的 `user_id` 查询参数仅作为兼容兜底
- 自动按当前决策选择 `115` 或 `GD/OpenList` 上游
- 自动附带上游要求的请求头
- 透传 `Range / If-Range`
- 透传 `206 / Content-Range / Accept-Ranges / Content-Length`

## 验证方式

### 1. 跑完整测试

```bash
uv run pytest tests -v
```

### 2. 跑 MVP smoke 验证

```bash
uv run python scripts/verify_mvp.py
```

### 3. 跑外部适配器验证脚本

```bash
uv run python scripts/validate_openlist_stream.py
uv run python scripts/validate_rapid_copy.py
uv run python scripts/verify_mvp.py
```

`validate_rapid_copy.py` 会始终探测 `source_copy / O2P`，并在 donor cookie 已配置时额外探测 `pool / P2P`。这两条链路是分开的：

- `source_copy / O2P`: `GD/OpenList -> 当前用户 115`
- `pool / P2P`: `donor 115 -> target 115`

### 4. 跑 caiyun / 139Yun source copy smoke

需要本地 OpenList、OpenList admin token、一个 GD 源文件、一个 139Yun mount path：

```bash
GATEWAY_OPENLIST_BASE_URL=http://localhost:5246 \
GATEWAY_OPENLIST_ADMIN_TOKEN=<openlist-admin-token> \
GATEWAY_OPENLIST_COPY_VERIFY_ATTEMPTS=30 \
GATEWAY_OPENLIST_COPY_VERIFY_INTERVAL_SECONDS=1.0 \
CAIYUN_MOUNT_PATH=/yidon \
GD_SOURCE_PATH="/google drive/openlist/path/to/sample.mkv" \
CAIYUN_TARGET_SUBDIR="" \
uv run python scripts/validate_caiyun_source_copy.py
```

普通 139 账号可能有单文件上传大小限制。验证时优先选小于账号限制的样例文件。

## 当前项目进度

当前实现已经完成原始 MVP 计划任务 `12 / 12`，大致包括：

- Task 1-2：服务骨架、配置与外部适配器契约
- Task 3-4：数据库、加密、管理员资源录入
- Task 5-6：catalog / fingerprint / donor 选择
- Task 7-8：播放状态机、基础 stats / worker helper
- Task 9：README、verify 脚本、运维验证入口
- Task 10-12：管理员持久化、预算控制、stats 持久化查询、worker 持久化 helper

如果只看“代码计划完成度”，当前已经到第一阶段终点。

## 下一阶段建议

下一阶段不建议先做花哨前端，而是建议按下面顺序推进：

### 第一优先级：接真实环境，打通全链路

目标是把现在的“本地 MVP”推进为“真实业务联调版”：

- 接入真实 OpenList 服务
- 接入真实 rapid-copy / 115 环境
- 跑通真实 catalog 同步
- 跑通真实 playback route 决策
- 让 `/api/admin/users`、`/api/admin/drives`、`/api/admin/stats` 真正服务于真实数据

这是下一阶段最关键的事。因为如果真实链路没通，前端做出来也只是空壳。

### 第二优先级：补最小前端管理页

当真实链路基本稳定后，再做一个最小管理后台，至少覆盖：

- 用户列表 / 创建用户
- drive 列表 / 录入 drive
- stats 查看
- 手工触发验证或同步

这时前端的价值会非常直接，因为后端接口已经有实际数据和真实行为可以展示。

### 第三优先级：生产化加固

在“真实链路可用 + 最小前端可用”之后，再补这些：

- 登录认证与权限
- 更明确的错误码与异常处理
- 日志与审计落库
- Docker / systemd / 部署脚本
- 配置校验
- 监控、告警、限流

## 当前结论

当前项目已经是一个“能跑、能测、能继续接真实环境”的后端 MVP，但还不是最终产品。

一句话概括当前状态：

- 不是空仓库
- 不是纯 demo
- 也还不是完整成品
- 它现在最适合做下一阶段真实链路接入和最小前端建设的基础底座

## 仓库位置

- GitHub: `https://github.com/xmm2022/media-pro`
