# media-pro Caiyun（移动云盘 / 139）接入设计

## 目标

把"移动云盘"接入 media-pro，作为继 115 之后的第二个用户终端云盘类型。完成后实现：

- 用户可在 media-pro UI 录入自己的 139 账号
- 播放决策链路上的 `source_copy`（GD → 用户终端）支持把媒体复制到用户 139
- 数据模型、playback_resolver、admin API 都为未来加更多 OpenList-backed driver（百度网盘、夸克等）准备好扩展点
- 不破坏现有 115 P2P 秒传链路

## 目标读者

- 当前维护者
- 后续接手 caiyun 接入实现的开发者
- 想了解"为什么 115 和 139 路径不对称"的人

## 当前现状

media-pro 已完成 MVP + Real Environment Integration，运行时形态：

- 媒体源：平台 GD 池，挂在外部 OpenList，media-pro 通过 `OpenListClient` 只读 stream / 列目录
- 用户终端：仅支持 115，凭据以加密 cookie 形式落 `UserDriveAccount`
- 秒传执行：通过外部 `rapid-copy` HTTP 服务（`RapidCopyClient`），三个路径都假设 115：
  - `pool / P2P`: donor 115 → target 115
  - `source_copy / O2P`: GD → target 115
  - `self`: 用户自己 115 已有缓存
- playback_resolver 三处硬编码 `UserDriveAccount.drive_type == "115"`：
  - `_load_target_drive`（src/gateway/playback_resolver.py:274）
  - `_select_donor_bundle`（同文件:305）
  - `_upsert_pool_object`（同文件:398，drive_type 硬编码字符串 "115"）
- admin API 录入流程：`POST /api/admin/drives` 直接传 cookie，加密落库

POC 阶段（`docs/superpowers/specs/2026-05-23-caiyun-poc-design.md`）的核心问题"GD → 139 服务端秒传是否可行"已被外部证据回答：在另一台机器的 OpenList 上 GD storage → 139 storage 的跨 storage copy 可秒传。本 spec 在该结论之上展开实施设计，POC 中已交付的 `openlist_creds.py` helper 可作为 admin client 的参考实现保留。

## 阶段范围

### 这阶段要做的事

- 引入 `RapidCopyStrategy` 抽象，把"如何 copy"从 playback_resolver 解耦
- 抽出 `OpenListAdminClient`，负责对 OpenList 的 admin/storage 与 fs/copy 调用
- 扩展 `UserDriveAccount`：新增 `openlist_mount_path` 列，`cookie_encrypted` 改 nullable
- playback_resolver 改为按 driver_type 从 strategy registry dispatch
- admin API 加 caiyun 录入 / 删除 / patch / probe 分支
- 端到端 smoke：本地 OpenList + 1 个 139 storage，验证 caiyun source_copy 可达

### 这阶段不做的事

- 不做 139 P2P（donor 139 → target 139 跨账号）。`pool_objects.drive_type` 已存在作为扩展点，但 `_select_donor_bundle` 仍只筛 115。MVP 之后视需要再加。
- 不做 OAuth 跳转。caiyun 录入流程让用户手工贴 access_token + refresh_token，OAuth 由后续 spec 处理。
- 不动 catalog_sync。GD 源仍由 OpenList 提供，与 caiyun 解耦。
- 不替换 115 链路。`Rapid115Strategy` 只包装现有 `RapidCopyClient`，对外行为不变。
- 不做生产部署、监控告警。

## 验收标准

完成时必须满足：

1. 一个用户在 media-pro UI 录入 139（手工贴 token），后端在 OpenList 自动创建对应 storage 并落本地 `UserDriveAccount`
2. 该用户播放一个 GD 媒体时，playback_resolver 选择 `source_copy` 路线，通过 `OpenListCopyStrategy` 把媒体 copy 到用户 139 的 mount_path 下，返回的 stream_url 可播
3. 同一个 user 同时拥有 115 + caiyun 两个 drive 时，按 enabled / drive_type 优先级（默认 115 优先）选择目标
4. 现有 115 链路所有测试保持绿，无回归
5. caiyun 录入失败（OpenList admin API 调用失败、token 无效等）时本地不写脏数据
6. probe 接口对 caiyun 返回 healthy / invalid_token / mount_missing / openlist_http_error / openlist_admin_failed
7. Alembic 迁移在已有 115 数据上 upgrade / downgrade 均无破坏

## 候选路线

设计阶段评估过三条路径：

### A：每个云盘一套专用 rapid-copy 后端

caiyun 走自写的 `caiyun-rapid-copy` HTTP service，直调 139 API。

- 优势：性能最优，与 115 路径完全对称
- 劣势：每加一个云盘都要写一套 rapid-copy 后端、每个 driver 都要追 token 刷新 / 风控 / 协议升级

### B：所有 driver 都改走 OpenList，包括 115

去掉 `rapid-copy` HTTP 服务，全部通过 OpenList `/api/fs/copy`。

- 优势：driver 中立、加新云盘成本极低、运维只看 OpenList
- 劣势：丢掉 115 P2P 秒传能力（OpenList 的 115 driver 大概率不支持跨账号秒传）、强依赖 OpenList、与 nextemby 模式背道而驰

### C：混合 —— 115 保留专用，其他走 OpenList（选定）

`Rapid115Strategy` 包装现有 `RapidCopyClient`；caiyun / 后续云盘走 `OpenListCopyStrategy`。

- 优势：保留 115 P2P 价值；加新 OpenList-supported driver 成本低（只增配置、不增后端）；用 OpenList 已验证的 GD→139 秒传能力做 caiyun source_copy
- 劣势：数据/UX 在 115 vs caiyun 上不完全对称（但通过 strategy 抽象在调用层抹平）

### 选定路线：C

理由：115 P2P 是 media-pro 的核心价值（继承自 nextemby 模式），不能丢；外部已验证 OpenList GD → 139 秒传可行；后续加云盘按 OpenList 扩展，避免每个云盘重复造轮子。

## 设计

### 1. RapidCopyStrategy 抽象层

新文件 `src/gateway/integrations/rapid_copy_strategy.py`，定义 Protocol：

```python
class RapidCopyStrategy(Protocol):
    drive_type: str

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult: ...
    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult: ...
    async def probe(self, drive: UserDriveAccount) -> ProbeResult: ...
```

两个实现：

- **`Rapid115Strategy`**（`src/gateway/integrations/rapid_copy_115_strategy.py`）：包装现有 `RapidCopyClient` / `PoolCopy115Client` / `SourceCopy115Client`。drive_type = "115"。`copy_from_pool` 与 `copy_from_source` 调用现有客户端。
- **`OpenListCopyStrategy`**（`src/gateway/integrations/openlist_copy_strategy.py`）：调 `OpenListAdminClient.fs_copy(...)`。drive_type ∈ {"caiyun", ...}。`copy_from_pool` 在 MVP 阶段 `raise NotImplementedError("pool not supported for OpenList-backed drivers in MVP")`，留待后续 spec 实现。

注册中心 `RapidCopyStrategyRegistry`：在 app startup 时按配置注册可用 strategy，playback_resolver 在拿到 target_drive 后通过 `registry.get(drive_type)` 取实现。

### 2. 数据模型变更

扩展现有 `UserDriveAccount`：

```python
class UserDriveAccount(Base):
    # 现有字段不变
    id, user_id, drive_type, root_dir,
    enabled, share_pool_enabled, health_status, last_checked_at

    # 字段变更
    cookie_encrypted: Mapped[str | None]  # 改为 nullable（caiyun 不存 token）

    # 新增字段
    openlist_mount_path: Mapped[str | None]  # OpenList-backed driver 用
```

字段语义按 driver 区分：

| 字段 | 115 | caiyun |
|---|---|---|
| `cookie_encrypted` | 必填 | NULL（token 在 OpenList 那边） |
| `root_dir` | `/EmbyCache/<user>` | mount_path 下的子目录，如 `/EmbyCache` |
| `openlist_mount_path` | NULL | 如 `/caiyun-alice` |
| `share_pool_enabled` | P2P donor 开关 | MVP 无意义，强制 false |

`pool_objects.drive_type` 字段已存在，不动；目前仍只取 "115" 值，待 P2P 扩展时补 "caiyun"。

Alembic 迁移：
- `ALTER TABLE user_drive_accounts ADD COLUMN openlist_mount_path VARCHAR(255) NULL`
- `ALTER TABLE user_drive_accounts ALTER COLUMN cookie_encrypted DROP NOT NULL`
- downgrade 逆向，已有 115 数据 cookie_encrypted 已有值不受影响

支持的 drive_type 集合作为常量集中维护：

```python
SUPPORTED_DRIVE_TYPES = {"115", "caiyun"}
OPENLIST_BACKED_DRIVE_TYPES = {"caiyun"}
```

### 3. playback_resolver 改造

| 位置 | 当前 | 改后 |
|---|---|---|
| `_load_target_drive`（playback_resolver.py:269） | `drive_type == "115"` | 去掉过滤，按 user_id + enabled 取 drive；多 drive 时按 `drive_type` 偏好顺序（115 > caiyun）选 |
| `_select_donor_bundle`（playback_resolver.py:285） | `drive_type == "115"` | **保留**（MVP 决定，pool 仅对 115 起作用） |
| `_upsert_pool_object`（playback_resolver.py:380） | drive_type 硬编码 "115" | 改为 `drive_type=target_drive.drive_type` |

copy 分支：当前 `await self._rapid_copy_client.copy_from_X(...)` 改为：

```python
strategy = self._strategy_registry.get(target_drive.drive_type)
result = await strategy.copy_from_source(source_request)
```

`PlaybackResolver.__init__` 替换：把现有 `rapid_copy_client / pool_copy_client / source_copy_client / drive_stream_client` 等参数收拢为 `strategy_registry: RapidCopyStrategyRegistry`。`drive_stream_client`（Drive115StreamClient）的引用迁到 `Rapid115Strategy` 内部。

stream_decision 路径：对 caiyun，`_cached_stream_info` 不再用 `Drive115StreamClient`，直接走 `_openlist_client.get_stream_info(mount_path + root_dir + 文件相对路径)`。

### 4. Admin API 扩展

`POST /api/admin/drives` 请求体扩展：

```json
{
  "user_id": 7,
  "drive_type": "caiyun",
  "caiyun": {
    "access_token": "...",
    "refresh_token": "...",
    "account_type": "personal"
  },
  "mount_path": "/caiyun-alice",
  "root_dir": "/EmbyCache"
}
```

drive_type = "115" 时维持现有 `cookie` 字段；drive_type = "caiyun" 时读 `caiyun` 子对象 + `mount_path`，忽略 `cookie`。

后端动作（caiyun 分支）：
1. 校验 caiyun 子对象字段
2. 调 `OpenListAdminClient.create_storage(driver="139Yun", mount_path, addition={access_token, refresh_token, type})`
3. OpenList 成功后写本地：`UserDriveAccount(user_id, drive_type="caiyun", cookie_encrypted=NULL, openlist_mount_path=mount_path, root_dir, share_pool_enabled=False)`
4. OpenList 失败：返回 error_code = `openlist_admin_failed`，本地不写

`DELETE /api/admin/drives/{id}` 对 caiyun：先调 `OpenListAdminClient.delete_storage_by_mount(mount_path)`，再删本地。OpenList 删失败时返回 `openlist_admin_failed`，本地保留（让运维介入）。

`PATCH /api/admin/drives/{id}` 对 caiyun：
- 请求体含 `caiyun.access_token / refresh_token` → 调 `update_storage` 写 OpenList addition
- 仅改 `enabled / health_status` → 只改本地
- 不允许通过 PATCH 修改 `drive_type` / `openlist_mount_path`

`POST /api/admin/drives/{id}/probe` 对 caiyun：调 `OpenListAdminClient.fs_list(mount_path)`：
- 200 + 非空 → `healthy`
- 401 → `invalid_token`
- 404 → `mount_missing`
- 其他非 200 → `openlist_http_error`
- 调用本身异常 → `openlist_admin_failed`

新错误码集合（在现有基础上）：
- `invalid_token`
- `mount_missing`
- `openlist_admin_failed`

### 5. catalog_sync 不变

`POST /api/admin/catalog/sync` 仍从 GD-on-OpenList 同步 media_items。caiyun 的 mount_path 不作为 catalog 源。本节存在只为明确边界：catalog 与用户终端 driver 完全解耦。

### 6. OpenList admin client

新文件 `src/gateway/integrations/openlist_admin_client.py`：

```python
class OpenListAdminClient:
    def __init__(self, *, base_url: str, admin_token: str) -> None: ...
    async def list_storages(self) -> list[Storage]: ...
    async def create_storage(
        self, *, driver: str, mount_path: str, addition: dict
    ) -> int: ...
    async def update_storage(self, storage_id: int, *, addition: dict) -> None: ...
    async def delete_storage(self, storage_id: int) -> None: ...
    async def delete_storage_by_mount(self, mount_path: str) -> None: ...
    async def fs_copy(
        self, *, src_dir: str, dst_dir: str, names: list[str]
    ) -> CopyResult: ...
    async def fs_list(self, mount_path: str) -> list[FsItem]: ...
```

为什么不塞进现有 `openlist_client.py`：`OpenListClient` 当前职责是只读 stream / 列目录（用 OpenList user token 即可）；admin 操作需要 admin token，权限不同、语义不同，分开避免误用。两个 client 共享 base_url，但 token 是两个独立 env var。

新增 env vars：
- `GATEWAY_OPENLIST_ADMIN_TOKEN`（必填于 caiyun 接入；如部署仅启用 115，可空）
- 复用现有 `GATEWAY_OPENLIST_BASE_URL`

OpenList admin API 的具体 URL 形态（如 `/api/admin/storage/create`、`/api/admin/storage/update`、`/api/admin/storage/delete`、`/api/fs/copy`、`/api/fs/list`）在 plan 阶段对照 OpenList 5.x 源码确认。本 spec 不锁死 URL，留 plan 调整空间。

### 7. 测试策略

**改**（应保持绿，最多调一行 fixture）：
- `tests/playback/test_playback_resolver_*.py`：`_load_target_drive` 去掉 `== "115"` 过滤后，纯 115 测试仍应通过
- `tests/api/test_admin_drives.py`：现有 115 录入测试保持

**新增**：
- `tests/integrations/test_openlist_admin_client.py`（respx mock 所有 admin / fs API）
- `tests/integrations/test_openlist_copy_strategy.py`
- `tests/integrations/test_rapid_115_strategy.py`（包装层测试）
- `tests/integrations/test_rapid_copy_strategy_registry.py`
- `tests/playback/test_playback_resolver_caiyun.py`（source_copy 链路 caiyun 分支）
- `tests/api/test_admin_drives_caiyun.py`（create / delete / patch / probe）
- `tests/api/test_admin_drives_caiyun_failure.py`（OpenList 失败时本地不写脏数据）

**端到端**：
- 扩 `scripts/verify_mvp.py` 加 caiyun 分支（可选）
- 或新增 `scripts/validate_caiyun_source_copy.py` 类似 `validate_rapid_copy.py`

## 实施顺序

按 TDD 顺序，每个 task 都"先红后绿再 commit"。详细 step 在 plan 文档展开。

1. **Alembic 迁移**：`openlist_mount_path` 新增 + `cookie_encrypted` nullable。迁移测试 upgrade / downgrade。
2. **`OpenListAdminClient`**：纯 respx mock 单测驱动实现。Admin API URL 此时对照 OpenList 源码锁死。
3. **`RapidCopyStrategy` Protocol + `Rapid115Strategy`**：重构包装现有 `RapidCopyClient` / `PoolCopy115Client` / `SourceCopy115Client` / `Drive115StreamClient`，所有现有 playback_resolver 测试保持绿。
4. **`OpenListCopyStrategy`**：基于 `OpenListAdminClient.fs_copy`，TDD。
5. **`RapidCopyStrategyRegistry`** + playback_resolver 改造为 dispatch：现有测试保绿 + 加 caiyun source_copy 单元测试。
6. **admin API caiyun 分支**：create / delete / patch / probe，包含错误码与 OpenList 失败时本地不写脏数据。
7. **端到端 smoke**：本地 OpenList + 1 个 139 storage，跑一遍 caiyun source_copy。失败回退到 source_stream 应可观察。

代码量估算：
- 新文件：~3 个 client/strategy + 1 个 migration + 7 个测试文件
- 修改：playback_resolver.py（~30 LOC）、admin.py（~80 LOC）、models.py（~3 LOC）、schemas.py（~20 LOC）、config.py（~5 LOC）、main.py（注册 strategy）
- 总：~600-900 LOC

## 风险与对策

| 风险 | 对策 |
|---|---|
| OpenList admin API URL 与本 spec 假设不符 | plan Task 2 必须先对照 OpenList 5.x 源码锁死所有 URL，再写 client 实现 |
| OpenList admin token 泄露后果严重（能删任何 storage） | env var 注入，不入 git；admin client 只在 main.py 单点构造；后续 spec 评估是否拆短期 token |
| OpenList 跨 storage GD→139 copy 实际不是秒传，而是流量中继 | end-to-end smoke 必须观察 OpenList outbound 流量；若非秒传，仍是可用方案，但需在风险栏明确性能预期 |
| caiyun token 刷新由 OpenList 完成，media-pro 失控 | probe 接口在 401 时归类为 `invalid_token`；admin UX 提示用户重新录入；不在 media-pro 实现刷新逻辑 |
| 用户加 caiyun 后误覆盖 115 优先级 | `_load_target_drive` 按 drive_type 偏好顺序排序（115 > caiyun），同时支持 enabled flag 显式禁用 |
| Alembic 迁移在 SQLite 上 ALTER COLUMN drop NOT NULL 不直接支持 | 用 Alembic batch_alter_table 包一层（SQLite 走重建表逻辑） |
| 多 driver 时 pool_objects.drive_type 与 owner drive 不一致 | `_upsert_pool_object` 写入时使用 `target_drive.drive_type`（caiyun source_copy 成功后写入 "caiyun"）；`_select_donor_bundle` 仍仅筛 "115"，所以非 115 的 pool_objects 当前不会被 donor 查询命中，记录留作 P2P 扩展时的数据基础 |
| 现有 PlaybackResolver 构造签名变化可能影响外部调用方 | main.py / tests 同步修改；strategy_registry 替换四个 client 参数，保持依赖注入风格 |

## 下一步产出

本 spec 完成 + commit 后，由 `superpowers:writing-plans` skill 输出对应的实施 plan：`docs/superpowers/plans/2026-05-23-caiyun-integration-plan.md`，按上述 7 步细化到 step 级别（含 RED / GREEN 验证命令、commit message、文件清单）。

plan 完成后，进入实际编码阶段，建议在 `feat/caiyun-integration` 新分支上推进（当前 `feat/caiyun-poc` 分支可保留 POC 工作历史，spec 与新分支基于其顶点拉出）。

## 结论

C 路线把"加新云盘"从"写新后端"降级为"加新配置"，同时保留 115 P2P 的核心价值。RapidCopyStrategy 抽象一次到位，未来加百度网盘、夸克等只要 OpenList 支持就能复用 `OpenListCopyStrategy`。MVP 不做 caiyun P2P 但数据模型已留扩展点，后续 spec 加一处 `_select_donor_bundle` 修改即可。
