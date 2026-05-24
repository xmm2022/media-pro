# media-pro NextEmby-like 泛云盘定位设计

## 背景

`media-pro` 过去的 README 把项目描述为 `GD Source-First Playback Gateway`。这个描述适合早期技术验证，但已经不能覆盖当前方向。项目已经具备 FastAPI 后端、SQLite 持久化、OpenList/GD 媒体源、115/139 用户盘接入、播放路由决策、最小管理页、管理员登录保护和 systemd 部署基线。

用户明确希望项目不是一个 `GD -> 139` 小工具，也不是 `115 -> 115` 专用工具，而是一个类似 NextEmby 的产品：面向 Emby/Jellyfin 播放链路，通过用户云盘缓存和平台媒体源协同，降低源站压力并提升播放体验。不同点是 `media-pro` 必须从第一天就按泛云盘设计，支持 115、139/caiyun，并为后续夸克、百度、阿里等 provider 留扩展口。

本设计只参考 `/root/nextemby` 的产品形态和架构边界。该目录没有 LICENSE/git 元数据，源码有反编译/PyArmor 痕迹，且开发者口头限制为自用修改、不能商用。因此 `media-pro` 不复制 NextEmby 代码、页面、文案、业务实现或授权逻辑，只 clean-room 复刻适合本项目的产品概念。

## 产品定位

`media-pro` 的新定位：

> 面向 Emby/Jellyfin 的泛云盘媒体缓存与播放网关。管理员配置媒体源、用户与策略，用户绑定自己的云盘账号。播放时系统优先命中用户已有缓存，其次复用池内缓存，再尝试从媒体源复制到用户云盘，最后回源直连播放。

第一阶段面向自用和小团队，不面向公开运营。系统应像一个正式产品，而不是临时联调工具：有清晰的管理后台、用户中心、云盘能力展示、播放诊断、缓存对象和转存记录。

## 使用场景

### 管理员

管理员负责：

- 配置媒体源，例如 OpenList/GD。
- 配置系统级能力，例如 OpenList token、默认缓存目录、provider 开关。
- 创建或维护用户。
- 查看用户云盘状态、缓存对象、转存尝试、播放路由和系统健康。
- 在播放失败时能看到失败发生在哪一步：用户缓存、池内复用、源复制还是回源播放。

### 用户

用户负责：

- 登录用户中心。
- 绑定或更新自己的云盘账号。
- 查看账号健康状态、缓存占用、最近播放记录。
- 在凭据失效时能按清晰流程更新凭据。

用户中心第一阶段只服务管理员创建的用户。开放注册、审核、卡密、Telegram 审批后置。

### 播放客户端

Emby/Jellyfin 客户端只关心可播放 URL。`media-pro` 在后端完成用户识别、媒体识别、路由决策、复制尝试和失败回退。

## 非目标

第一阶段不做：

- 公共站运营能力。
- 开放注册和注册审核。
- 卡密、套餐、付费、商业授权。
- Telegram/机器人审批。
- 多租户隔离。
- 完整品牌站点和公告系统。
- 多 worker 横向扩展。
- 复制 NextEmby 的私有源码、页面、文案或授权心跳。

这些能力可以在核心播放闭环稳定后独立设计。

## 核心播放模型

播放决策继续使用现有路线：

```text
self -> pool -> source_copy -> source_stream
```

含义：

- `self`：用户自己的云盘已经有该媒体缓存，直接使用用户盘播放。
- `pool`：其他用户或系统池里已有可复用缓存，尝试复制到当前用户盘。
- `source_copy`：从媒体源复制到当前用户盘，再从用户盘播放。
- `source_stream`：无法缓存或复制时，直接回源播放。

这条路线是产品核心，应保留为管理端和诊断端的共同语言。未来所有 provider 都通过能力描述决定能否参与每个阶段，而不是在 resolver 中继续写死某个云盘。

## Provider 能力模型

每种云盘类型注册为 provider。provider 不只是字符串，而是一组能力：

| 能力 | 说明 |
| --- | --- |
| `can_stream` | 能否从该用户盘生成播放直链 |
| `can_source_copy` | 能否从媒体源复制到该用户盘 |
| `can_pool_copy` | 能否从池内对象复制到该用户盘 |
| `credential_type` | 凭据类型，例如 cookie、token、openlist_storage |
| `managed_by_openlist` | 是否由 OpenList storage 承载 |
| `supports_health_probe` | 是否支持健康检查 |
| `supports_user_bind` | 是否允许用户中心自助绑定 |

第一阶段 provider：

| Provider | 角色 | 实现策略 |
| --- | --- | --- |
| `115` | 专用高价值 provider | 保留现有 115 专用 rapid-copy / stream 能力 |
| `caiyun` | OpenList-backed provider | 通过 OpenList storage 与 `fs/copy` 实现 GD/OpenList 源到 139 |
| `source_openlist` | 媒体源 provider | 作为 catalog 和回源播放来源，不作为用户盘 |

后续夸克、百度、阿里优先按 OpenList-backed provider 接入。只有当某个 provider 有明确的专用秒传价值时，才实现专用 strategy。

## 系统边界

### 媒体源层

媒体源层负责：

- 从 OpenList/GD 同步 catalog 到 `media_items`。
- 提供回源播放的 stream URL。
- 提供 `source_copy` 的源路径或源文件引用。

第一阶段不把用户云盘 mount 作为 catalog 源。用户云盘是缓存目标，不是媒体库来源。

### Provider 层

Provider 层负责：

- 暴露能力描述。
- 校验凭据。
- 生成播放 stream 信息。
- 执行 `source_copy` 或 `pool_copy`。
- 把 provider-specific 错误映射成统一错误码。

`115` 可以继续使用专用 client 和策略。`caiyun` 走 OpenList admin/client。调用方只依赖 provider 能力，不依赖 provider 内部协议。

### 播放决策层

播放决策层负责：

- 读取用户、媒体、用户盘、池对象。
- 按 `self -> pool -> source_copy -> source_stream` 执行。
- 为每次尝试写入 `transfer_jobs` 或等价尝试记录。
- 为最终结果写入 `playback_records`。
- 输出一份可给管理端展示的解释结果。

播放决策层不能继续扩大 provider-specific 分支。已有 115/139 分支需要逐步收敛到 provider capability 和 strategy registry。

### 状态与诊断层

状态层使用现有数据模型作为基础：

- `users`
- `user_drive_accounts`
- `media_items`
- `pool_objects`
- `transfer_jobs`
- `playback_records`
- `audit_logs`

需要补强的是读模型和解释能力：

- 最近播放记录。
- 某次播放尝试的阶段、耗时、失败码、最终路线。
- 某个媒体当前在哪些用户盘有缓存。
- 某个用户盘最近健康检查和失败分布。

### UI 层

管理端应从“最小页面”升级为正式工作台：

- 仪表盘：路线分布、用户盘健康、缓存对象、失败趋势。
- 媒体源：OpenList/GD 连接、catalog sync、源文件状态。
- 用户：用户列表、状态、到期时间、模板。
- 云盘账号：按 provider 展示能力、健康、绑定状态。
- 缓存对象：媒体、owner、provider、状态、失败次数、冷却时间。
- 转存任务：最近 `pool/source_copy` 尝试和错误码。
- 播放诊断：按用户、媒体、路线查询播放结果。
- 系统设置：OpenList、默认目录、provider 开关、管理员安全项。

用户中心第一阶段包含：

- 用户登录。
- 用户盘绑定和更新。
- 用户盘健康状态。
- 近期播放和缓存摘要。

## API 方向

第一阶段新增或补强这些 API：

| API | 用途 |
| --- | --- |
| `GET /api/admin/drive-types` | 返回 provider 列表、能力、凭据字段和 UI 展示信息 |
| `GET /api/admin/playback-records` | 查询播放结果 |
| `GET /api/admin/transfer-jobs` | 查询转存/复制尝试 |
| `GET /api/admin/media-items` | 查询 catalog 媒体 |
| `GET /api/admin/capabilities` | 返回系统启用能力，可与 `drive-types` 合并实现 |
| `GET /user` | 用户中心页面 |
| `GET /api/user/session` | 用户登录态 |
| `GET /api/user/drives` | 当前用户云盘 |
| `POST /api/user/drives` | 当前用户绑定云盘 |
| `PATCH /api/user/drives/{id}` | 当前用户更新凭据或启停 |

管理端和用户端都不应硬编码 provider 表单。表单字段、提示和能力标签优先来自 `drive-types`。

## 用户凭据策略

凭据处理规则：

- 后端继续加密保存必要凭据。
- UI 默认不回显 cookie/token 明文。
- 更新凭据时只允许提交新值，不提供“读取旧值”能力。
- 如果 provider 能提取稳定账号 ID，后端记录 masked account id 供展示和冲突检测。
- 用户中心只能管理自己的 drive，管理员后台可以管理所有 drive。

`115` 的扫码绑定、139 的 OAuth/刷新 token、其他网盘的自助授权都作为 provider-specific bind flow。第一阶段先支持管理员手工录入和用户手工更新；扫码/OAuth 在对应 provider 稳定后单独设计。

## 与当前代码的关系

当前 `media-pro` 已经有可复用基础：

- `PlaybackResolver` 已有 `self -> pool -> source_copy -> source_stream` 路线。
- `RapidCopyStrategyRegistry` 已经开始把 copy 行为从 resolver 中拆出。
- `UserDriveAccount` 已经包含 `drive_type`、`openlist_mount_path`、`openlist_storage_managed`。
- `PoolObject` 已经有 `drive_type`。
- Admin API 已有 users、drives、pool objects、stats、overview。
- systemd 部署和管理员登录保护已经存在。

需要调整的方向：

- README 和产品文档从 GD-source-first 改成泛云盘媒体缓存网关。
- UI 从最小工作台升级为正式信息架构。
- API 增加 provider capability 和诊断读模型。
- resolver 中残留的 provider-specific 判断逐步移入 provider strategy。
- `transfer_jobs` 从“尝试写入”升级为可查询、可解释的转存历史。

## 候选路线

### A. 继续小步修补现有 MVP

在当前管理页上继续加 139、播放记录和几个按钮。

优势：最快看到功能。

劣势：产品定位仍然混乱，UI 和 API 会继续被 115/139 分支拖着走，后续加 provider 会变难。

### B. 直接 fork/改造 NextEmby 私有源码

把 `/root/nextemby` 作为基础，在里面加入 139/OpenList/provider。

优势：短期产品界面和功能看起来完整。

劣势：授权不清晰、不能商用、源码反编译不完整、115 耦合很深、难以维护，也不适合把成果并回 `media-pro`。

### C. 以 `media-pro` 为干净底座，clean-room 模仿 NextEmby 产品形态

保留 `media-pro` 的现有后端和测试体系，按 provider capability 和正式工作台方向扩展。

优势：代码和授权边界清晰；能保留现有 115/139 成果；能长期扩展 provider；适合后续公开维护。

劣势：需要补 UI、用户中心和诊断能力，短期工作量比小修补大。

选定路线：C。

## 第一阶段实施顺序

### 1. 定位和文档

更新 README 和项目文档，把项目定位从 `GD Source-First Playback Gateway` 调整为泛云盘媒体缓存与播放网关。

验收标准：

- README 首屏能说明项目是 NextEmby-like 泛云盘网关。
- 文档明确 115 不是唯一目标，139/caiyun 是已接入 provider，OpenList/GD 是媒体源能力。
- 文档明确 `/root/nextemby` 只作为私有参考，不复制代码。

### 2. Provider capability API

增加 provider 能力描述，并暴露给管理端。

验收标准：

- `GET /api/admin/drive-types` 返回 115 和 caiyun。
- 每个 drive type 返回能力、凭据字段、是否 OpenList-backed、是否支持 pool/source/self。
- 管理端创建/编辑 drive 的表单可以从该 API 渲染或至少使用该 API 校验。

### 3. 诊断读模型

补齐播放和转存查询 API。

验收标准：

- 管理员能查询最近播放记录。
- 管理员能查询最近 transfer jobs。
- 每条记录包含用户、媒体、provider、阶段、路线、状态、错误码、时间。
- 播放失败时能看出失败发生在 `self`、`pool`、`source_copy` 还是 `source_stream`。

### 4. 管理后台产品化

重做 `/admin` 信息架构，但继续使用本项目自己的代码。

验收标准：

- 页面包含仪表盘、媒体源、用户、云盘账号、缓存对象、转存任务、播放诊断、系统设置。
- 当前已有 API 能支撑的页面必须接真实数据。
- 还没有后端能力的控件不做假功能，显示清晰的 disabled 状态或不出现。
- 移动端布局不破坏核心操作。

### 5. 用户中心 MVP

增加用户登录和用户自助管理自己的云盘。

验收标准：

- 管理员创建用户后，用户能登录用户中心。
- 用户能查看自己的 drive 状态。
- 用户能绑定或更新支持 `supports_user_bind` 的 provider。
- 用户不能读取其他用户数据。

### 6. Provider 收敛

把 resolver 和 admin API 中的 provider-specific 逻辑逐步收敛到 provider/strategy。

验收标准：

- 新 provider 接入优先新增 provider metadata 和 strategy，不需要在多个 API 文件里重复写分支。
- 115 专用能力保留。
- caiyun OpenList-backed 能力保留。
- 现有测试保持通过。

## 风险与约束

- NextEmby 私有源码只能作为产品参考，不能作为实现来源。
- OpenList-backed provider 的能力受 OpenList driver 质量影响，必须通过 probe 和错误码暴露真实状态。
- 115 专用能力和 OpenList-backed 能力不是完全对称的，UI 要展示差异，而不是假装所有 provider 能力一样。
- SQLite 和单进程内存缓存适合第一阶段小团队使用；如果后续走公开站或多 worker，需要重新设计会话、锁和队列。
- 用户凭据属于敏感数据，任何日志、错误信息、页面展示都不能泄漏明文 cookie/token。

## 成功标准

本阶段完成后，项目应满足：

- 新用户能理解这是一个泛云盘版 NextEmby-like 产品。
- 管理员能在一个正式工作台里完成核心运维。
- 用户能在用户中心完成基础云盘绑定和状态查看。
- 播放链路出现问题时，能通过诊断 API 和 UI 定位失败阶段。
- 115 和 139/caiyun 都作为 provider 被统一呈现，后续新增 provider 有明确落点。
- 现有系统服务、管理员登录、OpenList/GD/139 POC 能力不回退。
