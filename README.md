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
- `POST /api/admin/drives`
- `GET /api/admin/stats`
- `GET /api/playback/{media_id}`

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
- `GATEWAY_RAPID_COPY_BASE_URL`
  - rapid-copy 服务地址
- `GATEWAY_OPENLIST_PROBE_PATH`
  - `validate_openlist_stream.py` 使用的真实媒体探针路径
- `GATEWAY_CATALOG_ROOT_PATH`
  - 给后续 catalog sync 使用的根目录；当前两个探针脚本不会直接消费它
- `GATEWAY_RAPID_COPY_DONOR_COOKIE`
  - rapid-copy 验证脚本使用的 donor cookie
- `GATEWAY_RAPID_COPY_TARGET_COOKIE`
  - rapid-copy 验证脚本使用的 target cookie
- `GATEWAY_RAPID_COPY_SOURCE_PATH`
  - rapid-copy 验证脚本使用的源路径
- `GATEWAY_RAPID_COPY_TARGET_PATH`
  - rapid-copy 验证脚本使用的目标路径

Set `GATEWAY_COOKIE_SECRET` in `.env` before storing real drive cookies through the admin API. Keep `GATEWAY_DATABASE_URL` pointed at the SQLite file or database you want the gateway to manage.

## 真实联调必填变量

- `GATEWAY_OPENLIST_PROBE_PATH`
- `GATEWAY_CATALOG_ROOT_PATH`
  - 给后续 catalog sync 使用，当前 `validate_openlist_stream.py` / `validate_rapid_copy.py` 不直接读取它
- `GATEWAY_RAPID_COPY_DONOR_COOKIE`
- `GATEWAY_RAPID_COPY_TARGET_COOKIE`
- `GATEWAY_RAPID_COPY_SOURCE_PATH`
- `GATEWAY_RAPID_COPY_TARGET_PATH`

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

为某个用户录入 drive 账号信息，cookie 会加密落库。

请求示例：

```json
{
  "user_id": 1,
  "drive_type": "115",
  "cookie": "UID=1; CID=2",
  "root_dir": "/EmbyCache/alice",
  "share_pool_enabled": true
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

### `GET /api/playback/{media_id}`

按当前 MVP 逻辑返回一个播放决策结果。

返回示例：

```json
{
  "media_id": 42,
  "route": "source_stream",
  "stream_url": "https://openlist.local/media/42.mkv"
}
```

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
