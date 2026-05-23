# Caiyun POC

移动云盘（139）秒传可行性 POC。完整设计见 [`docs/superpowers/specs/2026-05-23-caiyun-poc-design.md`](../../docs/superpowers/specs/2026-05-23-caiyun-poc-design.md)。执行计划见 [`docs/superpowers/plans/2026-05-23-caiyun-poc-plan.md`](../../docs/superpowers/plans/2026-05-23-caiyun-poc-plan.md)。

## 接手者上手清单

按顺序完成。每条都过了再开始跑脚本。

### 1. 本机有一个跑起来的 OpenList

POC 不打算重新发明 139 SDK，所有 139 凭据从本机 OpenList 取。

- OpenList 启动方式不在 POC 范围内 —— 任何你已经在用的部署都行（docker / 直跑 / systemd 都可以）。
- 默认监听 `http://127.0.0.1:5244`，如果不同请改 `.env` 里 `OPENLIST_BASE_URL`。
- 后续脚本要调 `GET /api/admin/storage/list`，所以**必须**是 OpenList 5.x 以上、并开放 admin API。

### 2. 拿到 OpenList admin token

- OpenList 控制面板登录 → 设置 → 全局 → Token → 复制。
- 写入 `.env` 的 `OPENLIST_ADMIN_TOKEN`。

### 3. 在 OpenList 里挂 2 个 139 storage（不同账号）+ 1 个 GD storage

- 2 个 139 账号分别按 OpenList 文档加为 storage，driver 通常是 `139Yun`。记下两个 storage 的 mount path（如 `/caiyun-a`、`/caiyun-b`），写入 `.env` 的 `CAIYUN_STORAGE_A` / `CAIYUN_STORAGE_B`。
- 1 个 GoogleDrive storage，记下 mount path（如 `/gd`），写入 `.env` 的 `GD_STORAGE_MOUNT`。

### 4. 准备一个共有样例文件

- GD storage 下任选一个 ≤ 100 MB 的文件，记下完整路径（如 `/sample.mkv`），写入 `.env` 的 `T3_SAMPLE_FILE`。
- 文件路径是相对 GD storage 根目录的。

### 5. 能读 `/root/mobile-caiyun-autosave`

T1 静态分析要扫油猴脚本和 Python CLI。如果当前用户读不到 `/root/`：

```bash
sudo cp -r /root/mobile-caiyun-autosave /tmp/mobile-caiyun-autosave-ro
sudo chown -R $USER:$USER /tmp/mobile-caiyun-autosave-ro
```

然后改 `scripts/t1_static_analysis.py` 顶部的 `SOURCE_PATHS`，把 `/root/...` 改成 `/tmp/mobile-caiyun-autosave-ro/...`。

### 6. 一个能开 DevTools 的浏览器（任意，Chrome/Edge/Firefox 都行）

T4 用浏览器抓 HAR，不需要 Playwright、不需要 Chromium 镜像。具体操作流程在 plan Task 4 里。

### 7. Python 3.12+ 与依赖

```bash
cd poc/caiyun
cp .env.example .env             # 按上面填入
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

## 推荐执行顺序

```bash
python scripts/t1_static_analysis.py          # 无外部依赖
python scripts/t3_openlist_probe.py           # 需要 OpenList + 样例文件
# T4 抓包：浏览器手动 → 保存到 results/t4_playwright_capture.har
python scripts/t4_har_parse.py                # 解析 HAR
python scripts/merge_api_candidates.py        # 合并 T1+T4 候选
python scripts/t2_cookie_probe.py --priority P1   # 跑 server-side copy 等 P1 路径
python scripts/t2_cookie_probe.py --priority P2   # 跑 list/task P2
python scripts/t2_cookie_probe.py --priority P3   # 仅在 P1 不可行时跑 share fallback
```

跑完所有 track 后，按 plan Task 9 整理 `reports/2026-05-23-caiyun-poc-report.md`。

## 目录

```
poc/caiyun/
  README.md                  ← 本文件
  requirements.txt
  .env.example
  scripts/
    t1_static_analysis.py    ← Track 1
    t2_cookie_probe.py       ← Track 2（依赖 T1/T4 输出）
    t3_openlist_probe.py     ← Track 3
    t4_har_parse.py          ← Track 4（解析浏览器导出的 HAR）
    merge_api_candidates.py  ← T1+T4 合并
    common/
      openlist_creds.py      ← 从 OpenList 取 139 凭据
      caiyun_api.py          ← 139 API 薄封装
  tests/                     ← 共用解析逻辑的单测
  results/                   ← 各 track 原始数据（git 跟踪除 .har）
  reports/
    2026-05-23-caiyun-poc-report.md  ← 最终可行性报告（POC 完成后产出）
```

## 边界

- POC 阶段**不**修改 `src/gateway/` 任何业务代码。每次 commit 前确认 `git diff src/ | wc -l` 为 `0`。
- 报告完成前**不**开始 caiyun gateway 接入。
- HAR 文件包含登录凭据，**不**入 git（`.gitignore` 已忽略 `results/*.har`）。
