# 真实链路接入阶段设计

## 目标

把当前 `gd-playback-gateway` 从“本地可跑的后端 MVP”推进到“可接真实 OpenList / 115 / rapid-copy 环境的联调版”。

这一阶段的重点不是前端，而是让真实配置、真实外部服务、真实媒体数据和当前后端 API 真正连起来。

## 目标读者

- 当前维护者
- 后续负责后端联调的开发者
- 需要准备真实环境并验证链路的技术同事

## 当前现状

项目已经具备这些基础：

- FastAPI 服务、数据库模型、Alembic 迁移、cookie 加密
- 管理员用户 / drive 录入接口
- OpenList / rapid-copy 适配器骨架
- 播放路由决策骨架
- stats 汇总与 worker helper
- `validate_*` 与 `verify_mvp.py` 验证脚本

但距离“真实链路可用”还有几个关键缺口：

1. 外部适配器只验证了契约和假数据路径，没有完整吸收真实返回差异。
2. 验证脚本仍然使用写死的样例路径或占位 cookie，不适合真实环境直接联调。
3. `/api/playback/{media_id}` 仍然返回占位式播放决策，没有真正从数据库 / catalog / drive 记录推导输入。
4. catalog 同步、媒体入库、播放记录写入还没有形成真实工作流。
5. 真实环境配置项还不够完整，README 虽然有基础说明，但还没有“真实联调操作手册”。

## 阶段范围

### 这阶段要做的事

1. 让 OpenList 与 rapid-copy 适配器能对真实服务返回做稳定解析和错误映射。
2. 把验证脚本改成可通过环境变量驱动，而不是依赖硬编码样例。
3. 补齐“真实环境下录入用户 / drive 后，如何拉取媒体、如何验证播放、如何查看 stats”的最小链路。
4. 让 `/api/playback/{media_id}` 至少能够依据真实入库媒体和真实配置生成可解释结果，而不是纯占位逻辑。
5. 补充真实联调所需测试与文档。

### 这阶段不做的事

- 前端页面
- 登录认证与权限
- 生产部署方案
- 完整后台任务调度体系
- 大规模性能优化

## 验收标准

这一阶段完成时，应满足以下条件：

1. `scripts/validate_openlist_stream.py` 在真实 OpenList 环境下可执行，并返回真实流地址 / Range 能力信息。
2. `scripts/validate_rapid_copy.py` 在真实 rapid-copy 环境下可执行，并返回真实成功或失败分类。
3. 可以通过 `/api/admin/users` 与 `/api/admin/drives` 录入真实用户和真实 drive，且 cookie 继续加密存储。
4. 至少有一条真实或准真实的媒体记录可进入数据库，并能被 `/api/playback/{media_id}` 用于生成真实链路下的播放决策。
5. `/api/admin/stats` 能基于真实或测试注入的 playback 数据返回稳定四桶统计结果。
6. `verify_mvp.py` 之外，应新增一套面向真实联调的验证路径，能证明真实链路而不是仅证明本地骨架。

## 候选方案

### 方案 A：脚本优先

先强化 `validate_openlist_stream.py` 和 `validate_rapid_copy.py`，让脚本在真实环境下全部跑通，再回头补 API。

优点：

- 最快拿到“外部依赖是否可用”的证据
- 风险低，适合先排查环境问题

缺点：

- 只能证明局部可用
- 很容易出现脚本绿了，但 API 实际仍然没打通

### 方案 B：适配器 + API 联调优先

先完善适配器，再把真实链路直接接进管理接口、catalog 和 playback API。

优点：

- 直接面向最终验收目标
- 最能暴露真实数据格式、鉴权和时序问题

缺点：

- 一开始工作量更集中
- 对真实环境稳定性依赖更高

### 方案 C：后端链路分层推进

按“配置与脚本 → 适配器 → catalog / 数据库 → playback API → stats 验收”分层推进，每层都要求可独立验证。

优点：

- 风险最可控
- 每一层的失败原因更容易定位
- 更适合现有仓库从 MVP 继续演进

缺点：

- 节奏比方案 A 慢一点
- 需要更明确的阶段划分

### 推荐方案

采用 `方案 C`。

原因：

- 它保留了脚本验证的价值，但不把脚本当成最终验收。
- 它允许在不做前端的情况下，逐步把真实链路接到 API 和数据库上。
- 对当前仓库最自然，因为现有结构已经按模块拆开，适合分层补强。

## 设计

### 一、配置层设计

当前配置只覆盖了最基础的 URL 与 secret。真实联调阶段需要把“真实脚本输入”和“真实业务输入”区分开来。

建议补充两类配置：

1. 外部服务配置
   - OpenList 地址与 token
   - rapid-copy 地址
   - 数据库连接

2. 联调脚本配置
   - OpenList 用于验证的样例媒体路径
   - rapid-copy 用于验证的 donor cookie / target cookie / source path / target path
   - playback 验证用媒体 ID 或 source path

原则：

- 不把真实联调所需样例路径写死在脚本里
- 通过环境变量注入，便于不同环境复用
- README 中明确哪些变量是“服务运行需要”，哪些变量是“联调脚本需要”

### 二、OpenList 适配器设计

`OpenListClient` 当前已经能：

- 获取流地址
- 列出目录

但真实链路阶段要补的不是“更多功能”，而是“更稳的真实返回吸收能力”：

- 明确真实 OpenList 返回中哪些字段可缺失
- 统一 `mtime`、`file_id`、`path` 的归一化处理
- 对错误场景给出更可读的异常

输出目标：

- `get_stream_info()` 能在真实环境返回可直接用于 playback 的 `raw_url`
- `list_catalog()` 能生成可直接进入 `CatalogService.to_media_item()` 的输入

### 三、rapid-copy 适配器设计

当前 `RapidCopyClient.copy()` 只做了最薄的成功 / 失败分类。

真实链路阶段要补的是：

- 对常见失败类型做稳定映射
- 区分“外部服务不可达”“参数非法”“目标路径冲突”“账号无权限”“不支持快速复制”等错误
- 保证返回值可直接进入后续播放路由决策或联调日志输出

这一层仍然保持“适配器”定位，不直接承担复杂业务编排。

### 四、catalog 与媒体入库设计

当前 `CatalogService` 已具备：

- `mtime` 解析
- 名称归一化
- 弱指纹构建
- media item 字段转换

真实链路阶段需要补的是“把 OpenList 目录结果真正写入数据库”的最小流程。

建议增加一个最小同步入口：

- 输入：OpenList 根目录路径
- 动作：调用 `OpenListClient.list_catalog()`，经过 `CatalogService` 转换后写入 `MediaItem`
- 输出：新增 / 更新了多少条媒体记录

这一层的目标不是做完整同步系统，而是让 `/api/playback/{media_id}` 不再脱离真实媒体数据。

### 五、管理员录入与 drive 使用设计

当前管理员接口已经能持久化用户和 drive，并加密 cookie。

真实链路阶段继续沿用这个接口，不额外重做模型，只补这些约束：

- 明确 drive 是否为 donor / target 的使用场景
- 为后续 rapid-copy 联调提供最少必要查询入口
- 保证联调脚本或内部服务能够读取解密后的 cookie 用于外部请求

这里不做前端，也不做复杂权限，只要求后端链路可用。

### 六、playback API 设计

这是这阶段最关键的改动之一。

当前 `/api/playback/{media_id}` 仍然把输入硬编码成：

- 没有 self hit
- donor 不可用
- source copy 不支持
- 直接回源

真实链路阶段要把它变成“基于真实数据构造决策输入”：

1. 根据 `media_id` 读取 `MediaItem`
2. 从已有 pool / user / drive 数据判断 donor 是否存在
3. 在可配置条件下决定 source copy 是否支持
4. 根据 `PlaybackService.resolve()` 给出 route
5. 若 route 为 `source_stream`，返回真实 OpenList 流地址

注意：

- 这一阶段不要求完整实现真正的 copy 执行编排
- 但要求 API 输出建立在真实数据库数据和真实外部能力判断之上

### 七、stats 与 playback record 设计

`/api/admin/stats` 现在已经能根据 `PlaybackRecord.route` 做稳定四桶统计。

真实链路阶段需要补的是：

- 在真实 playback 验证路径中，至少能插入或记录一部分 playback record
- 保证 stats 不再只是“空桶接口”，而是真能反映联调行为

这一步可以很轻，不需要一开始就做完整审计平台。

### 八、脚本设计

这一阶段脚本分两类：

1. 探针脚本
   - `validate_openlist_stream.py`
   - `validate_rapid_copy.py`

2. 本地 smoke 脚本
   - `verify_mvp.py`

设计要求：

- 保留 `verify_mvp.py` 的当前最小用途，不扩成复杂真实联调器
- 对真实环境验证，增加新的环境驱动脚本或增强现有 `validate_*` 输入能力
- 脚本输出必须偏运维可读，不应只是 trace

## 实施顺序

建议分五步实施：

### 第一步：配置与脚本输入改造

- 补真实联调所需环境变量
- 去掉验证脚本中的硬编码样例路径 / 占位 cookie
- 更新 README

### 第二步：适配器真实返回加固

- 完善 OpenList 真实响应解析
- 完善 rapid-copy 错误映射
- 为真实返回差异补测试

### 第三步：catalog 最小入库链路

- 把真实目录数据同步到 `MediaItem`
- 验证数据库内确实出现真实媒体记录

### 第四步：playback API 接真实数据

- 让 `/api/playback/{media_id}` 读取真实 media
- 让 route 决策至少部分基于真实 donor / source / stream 信息

### 第五步：stats / 回归 / 文档收口

- 记录 playback 数据
- 校验 `/api/admin/stats`
- 更新 README 与联调手册
- 跑真实环境验收清单

## 测试策略

测试分三层：

1. 单元测试
   - 适配器解析
   - catalog 转换
   - playback 决策
   - stats 汇总

2. API 集成测试
   - admin 用户与 drive
   - playback 查询
   - stats 查询

3. 联调脚本验证
   - 真实 OpenList 探针
   - 真实 rapid-copy 探针
   - 本地 smoke 脚本

原则：

- 真实环境联调不依赖前端
- 能自动化的尽量自动化
- 脚本验证只做“环境证据”，不替代 API 测试

## 风险

### 外部接口不稳定

真实 OpenList 或 rapid-copy 可能返回与当前契约测试不同的字段结构。

处理方式：

- 优先增强适配器解析与错误信息
- 不把真实返回结构散落到业务层

### 账号与权限问题

115 donor / target 账号可能在真实环境中存在权限差异。

处理方式：

- 在 rapid-copy 适配器层明确分类错误
- 在验证脚本层输出可读诊断

### 真实链路和现有占位逻辑冲突

当前 playback API 还是占位式实现，容易和真实链路接入时发生分支冲突。

处理方式：

- 保留 `PlaybackService` 作为纯决策层
- 把真实输入构造放到 API 或 service 编排层

### 脚本通过但 API 不通过

这正是当前仓库最需要避免的问题。

处理方式：

- 把 API 作为主验收面
- 脚本只做辅助证明

## 下一步产出

这份设计之后，下一份文档应是实现计划，按以下任务拆分：

1. 真实环境配置与脚本输入改造
2. OpenList 适配器真实返回加固
3. rapid-copy 适配器错误映射加固
4. catalog 最小同步入库
5. playback API 真实数据接入
6. stats / 回归 / 文档收口

## 结论

下一阶段的本质，不是“继续补点代码”，而是把当前后端 MVP 从假链路推进到真链路。

真正的优先顺序应该是：

1. 真实环境可联调
2. 真实 API 可验收
3. 再做前端

如果这个顺序不变，后续前端建设和生产化工作都会更稳。
