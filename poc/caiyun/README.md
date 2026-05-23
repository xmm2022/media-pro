# Caiyun POC

移动云盘（139）秒传可行性 POC。完整设计见 [`docs/superpowers/specs/2026-05-23-caiyun-poc-design.md`](../../docs/superpowers/specs/2026-05-23-caiyun-poc-design.md)。

## 接手者快速上手

```bash
cd poc/caiyun
cp .env.example .env             # 填入本机 OpenList 地址 + admin token
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
playwright install chromium      # T4 需要

# 推荐执行顺序
python scripts/t1_static_analysis.py    # 无需 OpenList，零成本
python scripts/t3_openlist_probe.py     # 与 T1 并行
python scripts/t4_playwright_probe.py   # 与 T1 并行
python scripts/t2_cookie_probe.py       # 依赖 T1 + T4 产出
```

## 目录

```
poc/caiyun/
  README.md
  requirements.txt
  .env.example
  docker-compose.yml         ← 可选：chromium 容器化
  scripts/
    t1_static_analysis.py    ← Track 1
    t2_cookie_probe.py       ← Track 2（依赖 T1/T4 输出）
    t3_openlist_probe.py     ← Track 3
    t4_playwright_probe.py   ← Track 4
    common/
      openlist_creds.py      ← 从 OpenList 取 139 凭据
      caiyun_api.py          ← 139 API 薄封装
  results/                   ← 各 track 原始数据（git 跟踪）
  reports/
    2026-05-23-caiyun-poc-report.md  ← 最终可行性报告（POC 完成后产出）
```

## 边界

- POC 阶段不修改 `src/gateway/` 任何业务代码
- 报告完成前不开始 caiyun gateway 接入
