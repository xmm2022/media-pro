# 移动云盘秒传可行性 POC 设计

## 目标

通过一次有界探索，搞清楚「GD 资源 → 用户移动云盘（139 网盘）账号」的可行执行路径，给出 media-pro 下一阶段 gateway 改造方案的判定依据。

POC 结束时必须能直接回答：

- 移动云盘的「秒传 / 服务端复制」能力到底走哪条路？
- gateway 要不要立刻做 provider 抽象，还是先并行加 `drive_type="caiyun"`？
- 接入移动云盘需要改 media-pro 的哪几个文件、影响哪些测试？

## 目标读者

- 当前维护者
- 后续接手「caiyun-rapid-copy 后端 + media-pro caiyun 接入」的开发者
- 任何 clone 本仓库后想从 `poc/caiyun/` 重跑可行性验证的人

## 当前现状

media-pro 已经完成 MVP（Task 1-12）与 Real Environment Integration（Task 1-6），README 暴露的接口、catalog sync、playback resolver、real integration smoke probe 都已就位。仓库内 `master` 与 `origin/real-environment-integration` 内容等价，前者一次性合并提交，后者保留细粒度提交链。

但「GD → 用户移动云盘」这条产品路径并没有真正打通：

- `RapidCopyClient` 只是一层 HTTP 壳，向外部 rapid-copy 服务 POST `/copy`，本身不懂任何云盘协议。
- 外部 rapid-copy 服务目前是为 115 互传写的，**移动云盘对应的后端服务不存在**。
- 代码内多处硬编码 115：`playback_resolver` 三处 `UserDriveAccount.drive_type == "115"`，`admin.py` probe 仅识别 `115 / alist`，新建 drive 也默认 `drive_type="115"`。
- `/root/mobile-caiyun-autosave` 是 Playwright + Tampermonkey 浏览器自动化，不是 HTTP 秒传服务，不能直接被 gateway 调用。

进一步上游问题：用户已经在本机 OpenList 里接入了 2 个 139 storage，认证有效期长，但 **OpenList 内部存储的认证形式（推测为 OAuth access/refresh token）能否在服务端直调 139 API 时通用**，尚未验证。

## 阶段范围

### 这阶段要做的事

- 静态分析 `mobile-caiyun-autosave` 的油猴脚本与 Python CLI，提取 139 实际调用的 API 列表。
- 用从 OpenList 取出的 139 凭据直调上述 API，验证服务端可用性。优先验证「服务端跨账号 copy」「同账号 server-side copy」「上传 / hash 秒传」三类非分享路径。
- 探测 OpenList 自身能否承担「同账号目录间 copy」或「跨 storage copy」的角色。
- 用 Playwright 在 139 网页跑「同账号复制 / 跨账号迁移 / 上传」三类非分享操作，抓取实际网络请求，回灌给 T2 做精准复现 —— Playwright 在本 POC 里定位为「动态抓包发现 API」，不再以「复现油猴分享转存」为目标。
- 分享转存路径只在前 3 类全失败时作为 fallback 评估，且报告必须明确把它降级。
- 产出可行性报告 + media-pro 下一阶段改造 PR 草图。

### 这阶段不做的事

- 不修改 `src/gateway/` 任何业务代码。
- 不写完整的 `caiyun-rapid-copy` 生产服务，只验证最小动作链路。
- 不做生产部署、不接入真实用户、不做监控告警。
- 不动现有 115 适配器代码。
- 不做 provider 接口抽象（推迟到 POC 结论之后）。

## 验收标准

POC 完成时必须满足：

1. `poc/caiyun/reports/2026-05-23-caiyun-poc-report.md` 存在，且包含 4 条 track 各自的「可行 / 有条件可行 / 不可行」三态结论。
2. 每条 track 在 `poc/caiyun/results/` 下留存可复现的原始证据（响应 JSON、日志、Playwright trace 等）。
3. 报告 4.2 节给出选定的 caiyun 后端实施路径与关键组件清单。
4. 报告 4.3 节给出可执行的 media-pro 改造 PR 草图：文件清单、关键伪代码、Alembic 迁移摘要、受影响测试列表、预估代码量级。
5. `poc/caiyun/README.md` 写明任何接手者重跑 POC 的最小步骤。
6. 整个 POC 过程对 `src/gateway/` 零修改，git diff 验证。

## 候选路线

### 路线 A：先静态分析，后动态验证

T1 静态分析 → T2/T3/T4 动态验证 步进，每一步可独立止损。

优点：最低成本起手，Step 1 几乎一定能拿到 80% 答案。
缺点：节奏不算最快。

### 路线 B：4 条 track 全开，最后汇总

T1/T2/T3/T4 同时启动，最后产出对比表。

优点：最快得到完整画面。
缺点：可能在已经被 T1+T2 排除的路径上浪费时间。

### 选定路线

**路线 A 的步进顺序 + T4 重新定位为 API 动态抓包工具，与 T1/T3 并行启动**。

理由：

- T1 + T4 同时跑可以最大化 API 发现面：静态读源码 + 动态抓真实请求 = 互补。
- T2 必须在 T1 + T4 之后跑，因为它要复现两者抽出的 API 清单。
- T3 与 T1 / T4 无依赖，可并行，节省总时长。
- 分享转存路径不作为主推方向（用户偏好），仅在前 3 类 API 全部失败时由 T2 在 P3 优先级上补测。

## 设计

### Track 1：静态分析 `mobile-caiyun-autosave`

输入：`/root/mobile-caiyun-autosave/userscripts/caiyun_share_autosave.user.js`、`/root/mobile-caiyun-autosave/src/*.py`

动作：

- 通读油猴脚本，找出所有 `fetch / XMLHttpRequest / window.location` 涉及的 139 endpoint。
- 通读 Python CLI（`cli.py`、`transfer_runner.py`、`cookie_loader.py`），找出 Playwright 自动化点的语义动作（点击哪个按钮、等待哪个 DOM 节点、调哪个 API）。
- 对每个 endpoint 记录：URL、HTTP 方法、参数、Header 形态、是否需要签名 / 时间戳、Referer 要求。
- 区分纯前端 DOM 动作（无法服务端化）和真实 API 调用（可服务端化候选）。

产出：`poc/caiyun/results/t1_api_inventory.md` —— 一份 139 API 清单，按「能否脱离浏览器单独调用」标注。

可行性：零成本，必定可执行。

### Track 2：cookie / token 直调验证

前置：T1 产出 API 清单 + OpenList 已配 2 个 139 storage（两个不同账号）。

动作：

- 启动时调 OpenList admin API（`/api/admin/storage/list` 或等价）取 2 个 139 storage 的认证字段。可能是 OAuth `access_token + refresh_token`，也可能是裸 cookie。
- 用 httpx 复现 T1 + T4 喂过来的 API 调用，按优先级：
  - **P1 服务端同账号 copy**（账号 A 内部目录间复制，`POST /orchestration/personalCloud-rebuild/.../copy` 或等价）
  - **P1 服务端跨账号 copy / 迁移**（账号 A → 账号 B，可能走家庭共享、群空间或迁移接口）
  - **P1 上传 / hash 秒传**（先调 prepare 接口看 hash 命中是否能跳过传输）
  - **P2 列目录与查任务状态**（轮询、状态机）
  - **P3 分享识别 + 分享转存**（fallback，最后试）
- 每个 API 在「OpenList 凭据」和「浏览器 cookie」两种认证形态下各测一次，判断认证模型。
- 用「hash 命中」和「全新文件」两种样本测秒传 / 走流量行为。
- 记录速率限制：连续 N 次后是否触发风控、间隔多久放行。

产出：`poc/caiyun/results/t2_cookie_probe.jsonl` —— 每次调用一行，含请求、响应、耗时、错误码、风控判定。

### Track 3：OpenList 探测

前置：本机 OpenList 已有 2 个 139 storage。

动作：

- 调 OpenList 自身 API（`/api/fs/copy`、`/api/fs/put`）尝试以下场景：
  - 同账号 139 storage 内部 copy（A 用户的 `/Movies/x.mkv` → `/Cache/x.mkv`）
  - 跨账号 139 storage copy（A 用户 → B 用户）
  - 跨 storage 类型 copy（GD storage → 139 storage）
- 抓 OpenList 日志或 outbound 流量，判定是 server-side（139 API 直接复制）还是 client-relay（OpenList 拉 + 推、走流量）。
- 测吞吐：用 OpenList 上 GD storage 任选 100 MB / 1 GB / 10 GB 三档样本各一次，记录耗时。样本无需用户提前准备。
- 测秒传命中：同一份文件传两次，第二次是否秒成。

产出：`poc/caiyun/results/t3_openlist_probe.md` —— 各场景结论 + 流量证据 + 吞吐数据。

### Track 4：Playwright 动态抓包

前置：docker 已有 chromium 镜像 + 2 个 139 账号登录态可注入（cookie 或 storageState）。

定位：**不复现油猴分享转存**。Playwright 在本 POC 里只负责「在 139 网页上跑非分享操作 + 抓取实际网络请求」，把抓到的请求回灌给 T2 做精准复现。这是 T1 静态分析的动态补集。

动作：

- 注入账号 A 登录态，打开 `https://yun.139.com/`。
- 按以下三类场景手工 / 脚本触发并抓 outbound 请求：
  - **同账号文件复制 / 移动**：在网页内把 `/Movies/x.mkv` 复制 / 移动到 `/Cache/x.mkv`，抓 `XHR / fetch` 请求。
  - **跨账号迁移**：如果 139 网页提供「家庭共享 / 群空间 / 跨账号迁移」入口，触发一次，抓请求。如果完全没有此类入口，记录「网页层无此能力」结论。
  - **上传**：选一个本地小文件上传，抓 prepare → hash check → upload 全链路请求，重点看是否秒传命中。
- 抓包结果按 `场景 -> 请求列表 -> 请求详情（URL / Method / Headers / Body / Response）` 整理。
- 跑一次「同一文件二次上传」测秒传命中曲线。
- 不再跑「单账号连续 50 次」「并发 N 浏览器」吞吐基线 —— 这些是分享转存模型才需要的指标，新定位下用 T2 cookie 直调的 RPS 数据更准确。

产出：

- `poc/caiyun/results/t4_playwright_capture.har` —— 完整 HAR 文件。
- `poc/caiyun/results/t4_api_findings.md` —— 抽出来的 API 候选列表，格式与 T1 一致，便于合并喂给 T2。

### 工作目录结构

```
poc/caiyun/
  README.md              ← 接手者入口：环境准备、依赖、运行顺序、产出位置
  requirements.txt       ← httpx, pydantic, playwright, openlist 客户端等
  docker-compose.yml     ← chromium（T4） + 可选 OpenList 二号实例
  .env.example           ← OPENLIST_BASE_URL / OPENLIST_ADMIN_TOKEN / 测试 storage 名
  scripts/
    t1_static_analysis.py
    t2_cookie_probe.py
    t3_openlist_probe.py
    t4_playwright_probe.py
    common/
      openlist_creds.py  ← 从 OpenList admin API 取 139 凭据
      caiyun_api.py      ← 139 API thin wrapper
  results/               ← 各 track 原始数据
  reports/
    2026-05-23-caiyun-poc-report.md  ← 最终可行性报告 + PR 草图
```

### Cookie / 凭据获取流程

不依赖用户手动贴 cookie，启动时：

1. 读 `poc/caiyun/.env` 取 `OPENLIST_BASE_URL` + `OPENLIST_ADMIN_TOKEN`。
2. 调 OpenList admin API 列出 storage，过滤 `driver` 字段为 139 相关的条目。
3. 提取每个 storage 的 `addition` 字段（OpenList 用它存 driver-specific 配置，139 driver 多半是 OAuth token）。
4. 解析出来的 token 同时供 T2、T3、T4 使用，避免每条 track 各拿一次。
5. T2 启动时双探：① 用 OpenList 提取出的 token 调 139 ② 在脚本里把同一 token 包装回 cookie 形态再调，对比成功率。

风险：OpenList 内部存储的可能是经 OpenList 自己处理过的 token（含刷新逻辑），脱离 OpenList 直接使用可能失效或过期更快。若验证失败，T2 fallback 到「请用户手动贴一次 cookie」。

### 最终报告结构

`poc/caiyun/reports/2026-05-23-caiyun-poc-report.md` 章节固定如下：

- **4.1 路径结论对照表**：T1 / T2 / T3 三条候选路径 × {API 清单、认证形态、秒传命中、吞吐、风控、可行性三态}。T4 单列「抓包发现」一节，不参与路径三态评价，仅说明它为 T2 提供了哪些新 API。
- **4.2 选定后端实施路径**：基于 4.1，给出「caiyun-rapid-copy 后端走哪一条」「关键组件」「部署形态」。优先推服务端跨账号 / 同账号 copy，分享转存仅作 fallback 评估。
- **4.3 media-pro 改造 PR 草图**：
  - 文件清单（新增 / 修改 / 删除）
  - `UserDriveAccount.drive_type` 与 `PoolObject.drive_type` 的 `caiyun` 值如何 ingest
  - Alembic 迁移概要
  - `playback_resolver.py` 三处 `== "115"` 的改动方向
  - `admin.py` probe 扩展伪代码
  - 新增的 `caiyun_*_client.py` 或 `caiyun_rapid_copy_client.py` 接口签名
  - 受影响测试列表
  - 预估代码量级（行数 / 文件数）
- **4.4 风险 & 遗留**：未在 POC 内解决的事项 + 上线前要补的事。

## 实施顺序

POC 不走严格 TDD（不是产品代码），但保持节奏：

1. 写本 spec + 提交 + 初始化 `poc/caiyun/` 骨架（README、requirements、.env.example、空脚本占位）→ 同一个分支同一次推送。
2. T1 静态分析 + T4 Playwright 动态抓包 + T3 OpenList 探测 三者并行启动（T1/T4 是 API 发现，T3 走 OpenList 平行路径）→ 各自产出 → 分次 commit。
3. T2 cookie 直调验证 在 T1 + T4 产出 API 候选清单后启动，按 P1 → P2 → P3 优先级跑 → 产出 → commit。
4. 汇总写报告（4.1 → 4.2 → 4.3 → 4.4）→ commit。
5. 报告完成后向用户交付，决定下一个 spec（gateway caiyun 接入）。

## 测试策略

POC 脚本不强制单元测试，但满足：

- 每个 track 脚本必须 idempotent：重跑直接覆盖 `results/<track>.{md|jsonl}`，不保留历史副本（POC 不需要回溯，git 提交快照已足够）。
- 关键解析逻辑（如 OpenList token 提取、139 响应字段提取）拆出小函数，便于将来在 gateway 复用时直接抄走。
- T2 / T3 / T4 的脚本必须支持 `--dry-run`，不真的发请求，仅打印将要发的 payload，方便验证脚本本身。

## 风险与对策

| 风险 | 对策 |
|---|---|
| OpenList 内部 token 不能服务端直调 139 | T2 双探 + fallback 到用户手动 cookie；记录失败原因，写入报告 |
| 139 风控触发后 cookie 锁定 | 4 条 track 共享同一组凭据时串行执行风险动作；触发后立即停 + 记录 |
| OpenList 跨 storage copy 走流量而非秒传 | T3 必须看 outbound 流量曲线判定，结论写入报告 4.4，作为成本估算输入 |
| Playwright 抓包覆盖度不足 | T4 三类场景按优先级跑，跑不到的场景在报告里记 N/A，不阻塞 T2 |
| POC 期间 OpenList 凭据失效 | 凭据从 OpenList 取，OpenList 自身负责刷新；脚本检测 401 时报错而非自动重试，避免污染数据 |
| 误改 `src/gateway/` | 工作目录限定 `poc/caiyun/`；commit 前用 `git diff src/` 验证无改动 |

## 下一步产出

POC 报告完成后，下一份 spec 应是「media-pro caiyun 接入设计」，输入来自报告 4.2 + 4.3，至少覆盖：

- caiyun drive_type 进入数据模型的迁移方案
- `playback_resolver.py` 的 caiyun 分支
- `admin.py` caiyun probe 实现
- `caiyun_rapid_copy_client.py`（或决定不写、直接复用 OpenList）
- 是否启动 provider 抽象重构（决定权交给报告 4.2）

## 结论

POC 的本质，是把「移动云盘秒传到底走哪条路」这个未知项变成已知项，让 gateway 改造方案不再建立在猜测之上。

只有 POC 给出明确结论，后续 caiyun 接入的设计、provider 抽象的时机、容量评估的输入才有底气。
