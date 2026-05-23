# Caiyun POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate whether "GD source → user 139 cloud" rapid copy is feasible via direct 139 API, OpenList facilities, or Playwright capture, and produce a feasibility report plus PR sketch for the eventual media-pro caiyun integration. No changes to `src/gateway/`.

**Architecture:** Four exploration tracks share a centralised OpenList credential helper. T1 (static) + T3 (OpenList probe) + T4 (Playwright capture) run independently; T2 (cookie direct-call) depends on T1+T4 producing a merged API candidate list. All artefacts land in `poc/caiyun/results/`, final report in `poc/caiyun/reports/`. `src/gateway/` must stay untouched (verified by `git diff src/` before every commit).

**Tech Stack:** Python 3.12, httpx, pydantic, python-dotenv, playwright, pytest, respx

---

## File Map

- `poc/caiyun/scripts/common/openlist_creds.py` — fetch 139 storage credentials from local OpenList admin API.
- `poc/caiyun/scripts/common/caiyun_api.py` — thin 139 wrapper, populated incrementally as T1/T4 discover endpoints.
- `poc/caiyun/scripts/t1_static_analysis.py` — static analysis of `/root/mobile-caiyun-autosave`; outputs `results/t1_api_inventory.md`.
- `poc/caiyun/scripts/t3_openlist_probe.py` — OpenList copy probe; outputs `results/t3_openlist_probe.md`.
- `poc/caiyun/scripts/t4_playwright_probe.py` — Playwright dynamic capture; outputs `results/t4_playwright_capture.har` + `results/t4_api_findings.md`.
- `poc/caiyun/scripts/merge_api_candidates.py` — merge T1+T4 outputs into a single candidate list consumed by T2; outputs `results/api_candidates.json`.
- `poc/caiyun/scripts/t2_cookie_probe.py` — cookie/token direct-call probe; outputs `results/t2_cookie_probe.jsonl`.
- `poc/caiyun/tests/test_openlist_creds.py` — unit tests for credential parsing.
- `poc/caiyun/tests/test_merge_api_candidates.py` — unit tests for merge logic.
- `poc/caiyun/conftest.py` — pytest config (pythonpath = `scripts`).
- `poc/caiyun/reports/2026-05-23-caiyun-poc-report.md` — final feasibility report + PR sketch.

---

### Task 1: OpenList credential helper

**Files:**
- Modify: `poc/caiyun/scripts/common/openlist_creds.py`
- Create: `poc/caiyun/tests/__init__.py`
- Create: `poc/caiyun/tests/test_openlist_creds.py`
- Create: `poc/caiyun/conftest.py`
- Modify: `poc/caiyun/requirements.txt`

- [ ] **Step 1: Add test dependencies and pytest config**

Append to `poc/caiyun/requirements.txt`:

```
pytest>=8.3,<9
pytest-asyncio>=0.23,<0.24
respx>=0.21,<0.22
```

Create `poc/caiyun/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
```

Create `poc/caiyun/tests/__init__.py` (empty).

Add `[tool.pytest.ini_options]` section to `poc/caiyun/pyproject.toml` (create file if absent):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write the failing test**

Create `poc/caiyun/tests/test_openlist_creds.py`:

```python
import json

import httpx
import pytest
import respx

from common.openlist_creds import CaiyunCredential, fetch_caiyun_credentials


@respx.mock
async def test_fetch_caiyun_credentials_filters_139_storages_and_parses_addition() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "id": 1,
                            "mount_path": "/caiyun-a",
                            "driver": "139Yun",
                            "addition": json.dumps({
                                "access_token": "tok-a",
                                "refresh_token": "rt-a",
                                "type": "personal",
                            }),
                        },
                        {
                            "id": 2,
                            "mount_path": "/gd",
                            "driver": "GoogleDrive",
                            "addition": "{}",
                        },
                    ]
                }
            },
        )
    )

    creds = await fetch_caiyun_credentials(
        base_url="http://openlist.local",
        admin_token="admin-token",
    )

    assert creds == [
        CaiyunCredential(
            mount_path="/caiyun-a",
            access_token="tok-a",
            refresh_token="rt-a",
            extra={"type": "personal"},
        ),
    ]


@respx.mock
async def test_fetch_caiyun_credentials_skips_entries_without_access_token() -> None:
    respx.get("http://openlist.local/api/admin/storage/list").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "content": [
                        {
                            "mount_path": "/caiyun-bad",
                            "driver": "139Yun",
                            "addition": json.dumps({"refresh_token": "rt"}),
                        }
                    ]
                }
            },
        )
    )

    creds = await fetch_caiyun_credentials(
        base_url="http://openlist.local",
        admin_token="admin-token",
    )

    assert creds == []
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
cd poc/caiyun && pip install -r requirements.txt && pytest tests/test_openlist_creds.py -v
```

Expected: FAIL with `ImportError` because `fetch_caiyun_credentials` / `CaiyunCredential` are not yet defined.

- [ ] **Step 4: Write minimal implementation**

Replace `poc/caiyun/scripts/common/openlist_creds.py`:

```python
"""Fetch 139 storage credentials from the local OpenList admin API.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Cookie 凭据获取流程
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


_CAIYUN_DRIVERS = {"139Yun", "Yun139", "Mobile139", "139", "Caiyun"}


@dataclass(frozen=True)
class CaiyunCredential:
    mount_path: str
    access_token: str
    refresh_token: str
    extra: dict[str, Any] = field(default_factory=dict)


async def fetch_caiyun_credentials(
    *,
    base_url: str,
    admin_token: str,
) -> list[CaiyunCredential]:
    headers = {"Authorization": admin_token}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
        response = await client.get("/api/admin/storage/list")
        response.raise_for_status()
        items = response.json().get("data", {}).get("content") or []
    result: list[CaiyunCredential] = []
    for item in items:
        if item.get("driver") not in _CAIYUN_DRIVERS:
            continue
        addition = item.get("addition") or "{}"
        parsed = json.loads(addition) if isinstance(addition, str) else dict(addition)
        access = parsed.pop("access_token", "")
        refresh = parsed.pop("refresh_token", "")
        if not access:
            continue
        result.append(
            CaiyunCredential(
                mount_path=item.get("mount_path", ""),
                access_token=access,
                refresh_token=refresh,
                extra=parsed,
            )
        )
    return result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd poc/caiyun && pytest tests/test_openlist_creds.py -v`
Expected: PASS for both tests.

- [ ] **Step 6: Verify src/ untouched and commit**

Run: `git diff src/ | wc -l`
Expected: `0`.

```bash
git add poc/caiyun/scripts/common/openlist_creds.py poc/caiyun/tests/__init__.py poc/caiyun/tests/test_openlist_creds.py poc/caiyun/conftest.py poc/caiyun/requirements.txt poc/caiyun/pyproject.toml
git commit -m "feat(poc): add openlist credential helper"
```

---

### Task 2: T1 static analysis script

**Files:**
- Modify: `poc/caiyun/scripts/t1_static_analysis.py`
- Create: `poc/caiyun/results/t1_api_inventory.md`

- [ ] **Step 1: Write the static analysis script**

Replace `poc/caiyun/scripts/t1_static_analysis.py`:

```python
"""Track 1: static analysis of /root/mobile-caiyun-autosave.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 1

Reads the Tampermonkey userscript and the Python CLI, extracts every
URL / fetch / api call it references, classifies each entry as
"server-callable" (real HTTP endpoint) or "browser-only" (DOM action,
window.location, click selectors), and writes a Markdown inventory.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_PATHS = [
    Path("/root/mobile-caiyun-autosave/userscripts/caiyun_share_autosave.user.js"),
    Path("/root/mobile-caiyun-autosave/src/cli.py"),
    Path("/root/mobile-caiyun-autosave/src/transfer_runner.py"),
    Path("/root/mobile-caiyun-autosave/src/cookie_loader.py"),
]

URL_PATTERN = re.compile(r"""['"]((?:https?:)?//[^'"\s]+|/[A-Za-z0-9_./-]+)['"]""")
DOM_HINTS = ("querySelector", "click(", "innerText", "innerHTML", "evaluate(", "wait_for_selector")


@dataclass(frozen=True)
class ApiCandidate:
    source_file: str
    raw: str
    classification: str  # "server-callable" or "browser-only"
    surrounding_line: str


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _classify(line: str) -> str:
    if any(hint in line for hint in DOM_HINTS):
        return "browser-only"
    if "fetch(" in line or "XMLHttpRequest" in line or "httpx" in line or "requests." in line or "axios" in line:
        return "server-callable"
    if "window.location" in line or "location.href" in line:
        return "browser-only"
    if line.strip().startswith("//") or line.strip().startswith("#"):
        return "browser-only"
    return "server-callable"


def collect_candidates() -> list[ApiCandidate]:
    candidates: list[ApiCandidate] = []
    for path in SOURCE_PATHS:
        text = _read_text(path)
        if not text:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in URL_PATTERN.finditer(line):
                raw = match.group(1)
                if raw.startswith("//"):
                    continue
                if not (raw.startswith("http") or raw.startswith("/")):
                    continue
                candidates.append(
                    ApiCandidate(
                        source_file=str(path),
                        raw=raw,
                        classification=_classify(line),
                        surrounding_line=f"L{lineno}: {line.strip()}",
                    )
                )
    return candidates


def render_inventory(candidates: list[ApiCandidate]) -> str:
    lines = [
        "# T1 静态分析：mobile-caiyun-autosave API 清单",
        "",
        "Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md (Track 1)",
        "",
        "## Server-callable 候选",
        "",
    ]
    server = [c for c in candidates if c.classification == "server-callable"]
    browser = [c for c in candidates if c.classification == "browser-only"]
    for c in server:
        lines.append(f"- `{c.raw}` ({Path(c.source_file).name})")
        lines.append(f"  - {c.surrounding_line}")
    if not server:
        lines.append("- (none discovered)")
    lines.extend(["", "## Browser-only（无法脱离浏览器）", ""])
    for c in browser:
        lines.append(f"- `{c.raw}` ({Path(c.source_file).name})")
        lines.append(f"  - {c.surrounding_line}")
    if not browser:
        lines.append("- (none discovered)")
    return "\n".join(lines) + "\n"


def main() -> int:
    missing = [p for p in SOURCE_PATHS if not p.exists()]
    if missing:
        print(f"[t1] missing source files: {missing}", file=sys.stderr)
        return 1
    candidates = collect_candidates()
    out = Path(__file__).resolve().parents[1] / "results" / "t1_api_inventory.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_inventory(candidates), encoding="utf-8")
    print(f"[t1] wrote {out} with {len(candidates)} candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the script (sudo required for /root/mobile-caiyun-autosave)**

The script reads `/root/mobile-caiyun-autosave`. Run as root or copy the source elsewhere first.

```bash
sudo cp -r /root/mobile-caiyun-autosave /tmp/mobile-caiyun-autosave-ro
sudo chown -R $USER:$USER /tmp/mobile-caiyun-autosave-ro
# Update SOURCE_PATHS to /tmp/mobile-caiyun-autosave-ro/... in the script if root access is unavailable.
cd poc/caiyun && python scripts/t1_static_analysis.py
```

Expected stdout: `[t1] wrote .../results/t1_api_inventory.md with N candidates` where `N > 0`.

If `/root/mobile-caiyun-autosave` is unreadable as the current user, change `SOURCE_PATHS` to point at the readable copy at `/tmp/mobile-caiyun-autosave-ro/...` before re-running. Document this in the inventory's first line.

- [ ] **Step 3: Hand-review the inventory**

Open `poc/caiyun/results/t1_api_inventory.md`. For each `server-callable` entry, verify:
- It is actually an HTTP path (not a CSS selector accidentally matching the URL pattern).
- The `surrounding_line` makes the auth form (cookie / token) inspectable.

If any entry is misclassified, edit the inventory inline with a `**Reclassified:**` note explaining why. Do not modify the script.

- [ ] **Step 4: Verify src/ untouched and commit**

Run: `git diff src/ | wc -l`
Expected: `0`.

```bash
git add poc/caiyun/scripts/t1_static_analysis.py poc/caiyun/results/t1_api_inventory.md
git commit -m "feat(poc): t1 static API inventory"
```

---

### Task 3: T3 OpenList copy probe

**Files:**
- Modify: `poc/caiyun/scripts/t3_openlist_probe.py`
- Create: `poc/caiyun/results/t3_openlist_probe.md`

- [ ] **Step 1: Write the probe script**

Replace `poc/caiyun/scripts/t3_openlist_probe.py`:

```python
"""Track 3: OpenList copy-behavior probe.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 3

Scenarios:
  S1 same-account 139 copy (storage A: file -> file2)
  S2 cross-account 139 copy (storage A file -> storage B dir)
  S3 cross-storage copy (GD storage -> storage A)
  S4 dedup hit (run S1 again with same file)
  S5 throughput at 100MB / 1GB / 10GB on S3
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OPENLIST_BASE_URL = os.environ["OPENLIST_BASE_URL"]
OPENLIST_ADMIN_TOKEN = os.environ["OPENLIST_ADMIN_TOKEN"]
STORAGE_A = os.environ["CAIYUN_STORAGE_A"]
STORAGE_B = os.environ["CAIYUN_STORAGE_B"]
GD_STORAGE = os.environ.get("GD_STORAGE_MOUNT", "/gd")
SAMPLE_FILE = os.environ.get("T3_SAMPLE_FILE", "/sample.mkv")
DRY_RUN = os.environ.get("T3_DRY_RUN") == "1"


@dataclass
class ProbeRecord:
    scenario: str
    request: dict
    status: int | None
    elapsed_ms: int
    response_excerpt: str
    verdict: str  # "ok" | "fail" | "skip"


async def _post(
    client: httpx.AsyncClient,
    path: str,
    body: dict,
) -> tuple[int | None, str, int]:
    start = time.monotonic()
    if DRY_RUN:
        print(f"[t3 dry-run] POST {path} body={body}")
        return None, "(dry-run)", 0
    try:
        response = await client.post(path, json=body, timeout=600.0)
    except httpx.HTTPError as exc:
        return None, f"transport error: {exc}", int((time.monotonic() - start) * 1000)
    elapsed = int((time.monotonic() - start) * 1000)
    return response.status_code, response.text[:1000], elapsed


def _copy_body(src_dir: str, dst_dir: str, names: list[str]) -> dict:
    return {"src_dir": src_dir, "dst_dir": dst_dir, "names": names}


async def run_scenarios() -> list[ProbeRecord]:
    headers = {"Authorization": OPENLIST_ADMIN_TOKEN}
    records: list[ProbeRecord] = []
    async with httpx.AsyncClient(base_url=OPENLIST_BASE_URL, headers=headers) as client:
        # S1 same-account copy
        body = _copy_body(STORAGE_A, f"{STORAGE_A}/poc-cache", [SAMPLE_FILE.lstrip("/")])
        status, body_text, elapsed = await _post(client, "/api/fs/copy", body)
        records.append(
            ProbeRecord(
                scenario="S1 same-account copy",
                request=body,
                status=status,
                elapsed_ms=elapsed,
                response_excerpt=body_text,
                verdict="ok" if status == 200 else "fail",
            )
        )

        # S2 cross-account copy
        body = _copy_body(STORAGE_A, f"{STORAGE_B}/poc-cache", [SAMPLE_FILE.lstrip("/")])
        status, body_text, elapsed = await _post(client, "/api/fs/copy", body)
        records.append(
            ProbeRecord(
                scenario="S2 cross-account copy",
                request=body,
                status=status,
                elapsed_ms=elapsed,
                response_excerpt=body_text,
                verdict="ok" if status == 200 else "fail",
            )
        )

        # S3 cross-storage GD -> caiyun
        body = _copy_body(GD_STORAGE, f"{STORAGE_A}/poc-cache", [SAMPLE_FILE.lstrip("/")])
        status, body_text, elapsed = await _post(client, "/api/fs/copy", body)
        records.append(
            ProbeRecord(
                scenario="S3 cross-storage GD->caiyun",
                request=body,
                status=status,
                elapsed_ms=elapsed,
                response_excerpt=body_text,
                verdict="ok" if status == 200 else "fail",
            )
        )

        # S4 dedup hit (re-run S1)
        body = _copy_body(STORAGE_A, f"{STORAGE_A}/poc-cache", [SAMPLE_FILE.lstrip("/")])
        status, body_text, elapsed = await _post(client, "/api/fs/copy", body)
        records.append(
            ProbeRecord(
                scenario="S4 dedup hit (S1 repeated)",
                request=body,
                status=status,
                elapsed_ms=elapsed,
                response_excerpt=body_text,
                verdict="ok" if status == 200 else "fail",
            )
        )
    return records


def render(records: list[ProbeRecord]) -> str:
    lines = [
        "# T3 OpenList copy probe",
        "",
        "Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md (Track 3)",
        "",
        "| Scenario | Status | Elapsed | Verdict |",
        "|---|---|---|---|",
    ]
    for r in records:
        lines.append(f"| {r.scenario} | {r.status} | {r.elapsed_ms} ms | {r.verdict} |")
    lines.append("")
    lines.append("## Raw responses")
    lines.append("")
    for r in records:
        lines.append(f"### {r.scenario}")
        lines.append("")
        lines.append(f"Request: `{r.request}`")
        lines.append("")
        lines.append("```")
        lines.append(r.response_excerpt)
        lines.append("```")
        lines.append("")
    lines.append("## Throughput (manual — fill in after S5 runs)")
    lines.append("")
    lines.append("| Size | Wall clock | MB/s | Notes |")
    lines.append("|---|---|---|---|")
    lines.append("| 100 MB | TODO | TODO | |")
    lines.append("| 1 GB | TODO | TODO | |")
    lines.append("| 10 GB | TODO | TODO | |")
    lines.append("")
    lines.append("## Server-side vs client-relay verdict")
    lines.append("")
    lines.append("Document outbound traffic observations here (use `iftop` / `nethogs` against the openlist container during S3).")
    return "\n".join(lines) + "\n"


def main() -> int:
    records = asyncio.run(run_scenarios())
    out = ROOT / "results" / "t3_openlist_probe.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(records), encoding="utf-8")
    print(f"[t3] wrote {out} with {len(records)} scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Dry-run to validate request shape**

Run:
```bash
cd poc/caiyun
cp .env.example .env  # if not done; fill in OPENLIST_BASE_URL, OPENLIST_ADMIN_TOKEN, CAIYUN_STORAGE_A/B, GD_STORAGE_MOUNT
T3_DRY_RUN=1 python scripts/t3_openlist_probe.py
```

Expected: 4 lines of `[t3 dry-run] POST /api/fs/copy body={...}` and final `[t3] wrote ...` line.

- [ ] **Step 3: Real run against local OpenList**

Pre-conditions (ask user to confirm before running):
- `SAMPLE_FILE` path exists under `STORAGE_A` and `GD_STORAGE`.
- A throwaway directory `poc-cache` under each storage will accept writes.

Run: `cd poc/caiyun && python scripts/t3_openlist_probe.py`

Expected: 4 scenarios with status codes, file written. If S3 throughput is to be measured, run S3 manually with 3 sample sizes and fill the table.

- [ ] **Step 4: Hand-review report**

Open `results/t3_openlist_probe.md`. For each FAIL scenario, add a one-line root-cause hypothesis below the raw response (e.g. `Cause: OpenList copies cross-storage by streaming through itself`).

- [ ] **Step 5: Verify src/ untouched and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/scripts/t3_openlist_probe.py poc/caiyun/results/t3_openlist_probe.md
git commit -m "feat(poc): t3 openlist copy probe"
```

---

### Task 4: T4 Playwright dynamic capture

**Files:**
- Modify: `poc/caiyun/scripts/t4_playwright_probe.py`
- Create: `poc/caiyun/results/t4_playwright_capture.har`
- Create: `poc/caiyun/results/t4_api_findings.md`

- [ ] **Step 1: Write the capture script**

Replace `poc/caiyun/scripts/t4_playwright_probe.py`:

```python
"""Track 4: Playwright dynamic API capture.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 4

Loads two 139 sessions via OpenList-provided tokens, opens
https://yun.139.com/, lets the operator (or automation) trigger
three non-share scenarios:

  S1 same-account copy / move
  S2 cross-account migration (only if 139 web exposes the action)
  S3 upload (prepare + hash + put)

All outbound HTTP is captured to a HAR file. After the page closes
we parse the HAR and emit a candidate API list.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
HAR_PATH = ROOT / "results" / "t4_playwright_capture.har"
FINDINGS_PATH = ROOT / "results" / "t4_api_findings.md"
STORAGE_STATE_A = ROOT / ".cache" / "t4_storage_a.json"
STORAGE_STATE_B = ROOT / ".cache" / "t4_storage_b.json"


async def capture_session(storage_state: Path | None, har_path: Path) -> None:
    HAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            record_har_path=str(har_path),
            record_har_content="embed",
            storage_state=str(storage_state) if storage_state and storage_state.exists() else None,
        )
        page = await context.new_page()
        await page.goto("https://yun.139.com/")
        print(
            "[t4] browser open. Drive it through S1 same-account copy, "
            "S2 cross-account migration (if exists), S3 upload. "
            "Close the window when done.",
            file=sys.stderr,
        )
        await page.wait_for_event("close", timeout=0)
        await context.close()
        await browser.close()


def parse_har(har_path: Path) -> list[dict]:
    data = json.loads(har_path.read_text(encoding="utf-8"))
    entries = data.get("log", {}).get("entries", [])
    findings: list[dict] = []
    for e in entries:
        req = e.get("request", {})
        url = req.get("url", "")
        if "yun.139.com" not in url and "caiyun" not in url and "139cloud" not in url:
            continue
        findings.append(
            {
                "method": req.get("method"),
                "url": url,
                "headers": {h["name"].lower(): h["value"] for h in req.get("headers", [])},
                "post_data": (req.get("postData") or {}).get("text", ""),
                "status": e.get("response", {}).get("status"),
            }
        )
    return findings


def render_findings(findings: list[dict]) -> str:
    lines = [
        "# T4 抓包发现",
        "",
        "Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md (Track 4)",
        "",
        "| Method | URL | Status | Has body |",
        "|---|---|---|---|",
    ]
    for f in findings:
        lines.append(
            f"| {f['method']} | `{f['url']}` | {f['status']} | {'yes' if f['post_data'] else 'no'} |"
        )
    lines.append("")
    lines.append("## Operator notes")
    lines.append("")
    lines.append("- Map each row above to scenario S1 / S2 / S3 inline.")
    lines.append("- Highlight rows whose body or response suggests hash-based dedup.")
    lines.append("- Flag rows requiring browser-only headers (e.g. signature, fingerprint).")
    return "\n".join(lines) + "\n"


async def main() -> int:
    STORAGE_STATE_A.parent.mkdir(parents=True, exist_ok=True)
    await capture_session(STORAGE_STATE_A, HAR_PATH)
    findings = parse_har(HAR_PATH)
    FINDINGS_PATH.write_text(render_findings(findings), encoding="utf-8")
    print(f"[t4] wrote {HAR_PATH} and {FINDINGS_PATH} ({len(findings)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 2: Install Playwright Chromium**

```bash
cd poc/caiyun && pip install -r requirements.txt && playwright install chromium
```

Expected: `chromium-XXXX downloaded ...`.

- [ ] **Step 3: First run (headed, to log in if no storage state exists)**

```bash
cd poc/caiyun && PLAYWRIGHT_HEADLESS=false python scripts/t4_playwright_probe.py
```

When the browser opens:
1. Log in to 139 with account A.
2. Manually trigger S1 (copy a file within the same account).
3. Manually trigger S2 (try to migrate to account B if the web UI offers it; if not, note it).
4. Manually trigger S3 (upload a small file).
5. Close the browser.

Then save the session for re-runs (optional): run a small helper or use the captured HAR alone.

Expected: HAR file > 100 KB; findings markdown contains at least the S1/S3 endpoints.

- [ ] **Step 4: Hand-review findings**

Open `results/t4_api_findings.md`. Annotate each row inline:
- Tag with scenario (`S1`, `S2`, `S3`).
- Note any browser-only auth header that would block server-side replay.
- Flag candidate endpoints for T2.

- [ ] **Step 5: Verify src/ untouched and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/scripts/t4_playwright_probe.py poc/caiyun/results/t4_playwright_capture.har poc/caiyun/results/t4_api_findings.md
git commit -m "feat(poc): t4 playwright dynamic capture"
```

---

### Task 5: Merge T1 + T4 into API candidates JSON

**Files:**
- Create: `poc/caiyun/scripts/merge_api_candidates.py`
- Create: `poc/caiyun/tests/test_merge_api_candidates.py`
- Create: `poc/caiyun/results/api_candidates.json`

- [ ] **Step 1: Write the failing test**

Create `poc/caiyun/tests/test_merge_api_candidates.py`:

```python
from pathlib import Path

from merge_api_candidates import ApiCandidate, merge


def test_merge_dedupes_by_method_and_url_and_preserves_source_provenance() -> None:
    from_t1 = [
        ApiCandidate(method="GET", url="/orchestration/personalCloud/list", source="T1", note="cli.py:42"),
    ]
    from_t4 = [
        ApiCandidate(method="POST", url="/orchestration/personalCloud-rebuild/copy", source="T4", note="S1 copy"),
        ApiCandidate(method="GET", url="/orchestration/personalCloud/list", source="T4", note="S1 list before copy"),
    ]

    merged = merge(from_t1, from_t4)

    assert merged == [
        ApiCandidate(
            method="GET",
            url="/orchestration/personalCloud/list",
            source="T1+T4",
            note="cli.py:42 | S1 list before copy",
        ),
        ApiCandidate(
            method="POST",
            url="/orchestration/personalCloud-rebuild/copy",
            source="T4",
            note="S1 copy",
        ),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd poc/caiyun && pytest tests/test_merge_api_candidates.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement merge module**

Create `poc/caiyun/scripts/merge_api_candidates.py`:

```python
"""Merge T1 (static) + T4 (capture) outputs into one API candidate list.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 2 (depends on this merged input)
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T1_PATH = ROOT / "results" / "t1_api_inventory.md"
T4_PATH = ROOT / "results" / "t4_api_findings.md"
OUT_PATH = ROOT / "results" / "api_candidates.json"


@dataclass(frozen=True)
class ApiCandidate:
    method: str
    url: str
    source: str
    note: str


def _parse_t1(text: str) -> list[ApiCandidate]:
    candidates: list[ApiCandidate] = []
    in_server_section = False
    for line in text.splitlines():
        if line.startswith("## Server-callable"):
            in_server_section = True
            continue
        if line.startswith("## ") and in_server_section:
            in_server_section = False
        if not in_server_section:
            continue
        match = re.match(r"-\s+`([^`]+)`\s+\(([^)]+)\)", line)
        if match:
            url = match.group(1)
            source_file = match.group(2)
            candidates.append(ApiCandidate(method="?", url=url, source="T1", note=source_file))
    return candidates


def _parse_t4(text: str) -> list[ApiCandidate]:
    candidates: list[ApiCandidate] = []
    for line in text.splitlines():
        match = re.match(r"\|\s*(GET|POST|PUT|DELETE|PATCH|HEAD)\s*\|\s*`([^`]+)`\s*\|", line)
        if match:
            candidates.append(
                ApiCandidate(method=match.group(1), url=match.group(2), source="T4", note="t4_api_findings.md")
            )
    return candidates


def merge(t1: list[ApiCandidate], t4: list[ApiCandidate]) -> list[ApiCandidate]:
    by_key: dict[tuple[str, str], ApiCandidate] = {}
    for entry in [*t1, *t4]:
        key = (entry.method, entry.url)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = entry
        else:
            sources = sorted({existing.source, entry.source})
            notes = " | ".join(filter(None, [existing.note, entry.note]))
            by_key[key] = ApiCandidate(
                method=entry.method,
                url=entry.url,
                source="+".join(sources),
                note=notes,
            )
    return sorted(by_key.values(), key=lambda c: (c.url, c.method))


def main() -> int:
    t1 = _parse_t1(T1_PATH.read_text(encoding="utf-8")) if T1_PATH.exists() else []
    t4 = _parse_t4(T4_PATH.read_text(encoding="utf-8")) if T4_PATH.exists() else []
    merged = merge(t1, t4)
    OUT_PATH.write_text(json.dumps([asdict(m) for m in merged], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[merge] wrote {OUT_PATH} with {len(merged)} candidates (T1={len(t1)}, T4={len(t4)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd poc/caiyun && pytest tests/test_merge_api_candidates.py -v`
Expected: PASS.

- [ ] **Step 5: Run the merge against real T1/T4 outputs**

Run: `cd poc/caiyun && python scripts/merge_api_candidates.py`
Expected: `[merge] wrote .../api_candidates.json with N candidates (T1=..., T4=...)` where `N > 0`.

- [ ] **Step 6: Verify src/ untouched and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/scripts/merge_api_candidates.py poc/caiyun/tests/test_merge_api_candidates.py poc/caiyun/results/api_candidates.json
git commit -m "feat(poc): merge t1+t4 api candidates"
```

---

### Task 6: T2 P1 cookie probe (server-side copy / cross-account / upload+hash)

> **Exploratory task.** The plan cannot give exact request bodies — they depend on the real endpoints surfaced by Task 5. Treat `_run_p1_calls` as a scaffold; for each P1 family the operator must read `results/api_candidates.json`, pick the matching endpoint, and fill the JSON body using the shape suggested by the T1 surrounding line or the T4 captured `postData`. Re-run after each body adjustment; record failures verbatim — they are data, not errors.

**Files:**
- Modify: `poc/caiyun/scripts/common/caiyun_api.py`
- Modify: `poc/caiyun/scripts/t2_cookie_probe.py`
- Create: `poc/caiyun/results/t2_cookie_probe.jsonl`

- [ ] **Step 1: Populate the 139 API wrapper with endpoints selected from api_candidates.json**

Replace `poc/caiyun/scripts/common/caiyun_api.py`:

```python
"""Thin 139 API wrapper used across tracks.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 2

Endpoints are sourced from results/api_candidates.json. This file
is a thin call layer only — concrete URL paths and payload shapes
get filled in as T1/T4 confirm them.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class CaiyunCallResult:
    label: str  # P1/P2/P3-<name>
    method: str
    url: str
    request: dict[str, Any]
    status: int | None
    elapsed_ms: int
    response_excerpt: str
    rate_limited: bool


async def call(
    *,
    client: httpx.AsyncClient,
    label: str,
    method: str,
    url: str,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> CaiyunCallResult:
    start = time.monotonic()
    try:
        response = await client.request(
            method,
            url,
            json=json_body,
            headers=headers or {},
            timeout=60.0,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        excerpt = response.text[:1500]
        rate_limited = response.status_code in {429, 403} or "频繁" in excerpt or "rate" in excerpt.lower()
        return CaiyunCallResult(
            label=label,
            method=method,
            url=url,
            request=json_body or {},
            status=response.status_code,
            elapsed_ms=elapsed,
            response_excerpt=excerpt,
            rate_limited=rate_limited,
        )
    except httpx.HTTPError as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return CaiyunCallResult(
            label=label,
            method=method,
            url=url,
            request=json_body or {},
            status=None,
            elapsed_ms=elapsed,
            response_excerpt=f"transport error: {exc}",
            rate_limited=False,
        )
```

- [ ] **Step 2: Write the P1 probe script**

Replace `poc/caiyun/scripts/t2_cookie_probe.py`:

```python
"""Track 2: cookie / token direct-call validation.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 2

Priority order: P1 (this task) -> P2 (Task 7) -> P3 (Task 8).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path

import httpx
from dotenv import load_dotenv

from common.caiyun_api import CaiyunCallResult, call
from common.openlist_creds import fetch_caiyun_credentials

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OPENLIST_BASE_URL = os.environ["OPENLIST_BASE_URL"]
OPENLIST_ADMIN_TOKEN = os.environ["OPENLIST_ADMIN_TOKEN"]
CAIYUN_BASE_URL = os.environ.get("CAIYUN_BASE_URL", "https://yun.139.com")
OUT_PATH = ROOT / "results" / "t2_cookie_probe.jsonl"


def _load_candidates() -> list[dict]:
    raw = json.loads((ROOT / "results" / "api_candidates.json").read_text(encoding="utf-8"))
    return raw


async def _run_p1_calls(creds, candidates) -> list[CaiyunCallResult]:
    """Plug the actual API calls in here once Task 5 candidates are known.

    The skeleton below issues one call per P1 family using the first matching
    candidate; the exact body shape is intentionally minimal and must be
    expanded inline based on what T1/T4 revealed about each endpoint."""
    cred_a, *_rest = creds
    cred_b = _rest[0] if _rest else cred_a
    headers_a = {"Authorization": f"Bearer {cred_a.access_token}"}
    headers_b = {"Authorization": f"Bearer {cred_b.access_token}"}
    results: list[CaiyunCallResult] = []
    async with httpx.AsyncClient(base_url=CAIYUN_BASE_URL) as client:
        for family in ("same_account_copy", "cross_account_copy", "hash_upload_prepare"):
            match = next((c for c in candidates if family.split("_")[0] in c["url"].lower()), None)
            if match is None:
                continue
            label = f"P1-{family}"
            json_body = {}  # operator: fill the body shape per family using Task 5 candidates
            headers = headers_a if family != "cross_account_copy" else headers_b
            result = await call(
                client=client,
                label=label,
                method=match["method"] if match["method"] != "?" else "POST",
                url=match["url"],
                json_body=json_body,
                headers=headers,
            )
            results.append(result)
    return results


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority", choices=["P1", "P2", "P3"], default="P1")
    args = parser.parse_args()
    if args.priority != "P1":
        print("Task 6 only handles P1; P2/P3 added by Task 7/8.")
        return 2

    creds = await fetch_caiyun_credentials(
        base_url=OPENLIST_BASE_URL,
        admin_token=OPENLIST_ADMIN_TOKEN,
    )
    if len(creds) < 2:
        print(f"Expected 2 caiyun credentials from OpenList, got {len(creds)}", flush=True)
        return 1

    candidates = _load_candidates()
    results = await _run_p1_calls(creds, candidates)
    with OUT_PATH.open("a", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    print(f"[t2] appended {len(results)} P1 results to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 3: Dry-run with empty candidates allowed**

```bash
cd poc/caiyun && python scripts/t2_cookie_probe.py --priority P1
```

Expected (when api_candidates.json contains real entries from Task 5): `[t2] appended N P1 results to ...` where `N > 0`.

If the script exits with "Expected 2 caiyun credentials from OpenList, got 1", confirm `CAIYUN_STORAGE_A/B` are both real 139 storages in the running OpenList.

- [ ] **Step 4: Annotate jsonl with verdicts**

For each line in `results/t2_cookie_probe.jsonl`, manually append the verdict by re-saving the file with one extra column at the end of each line, e.g. `{"verdict": "feasible"}` appended after the auto-fields. Use one of: `feasible | feasible-with-conditions | infeasible | needs-more-data`.

Document any rate-limit observations in a trailing `# notes:` block at the end of the file (`#` lines are comments, the script appends but never overwrites).

- [ ] **Step 5: Verify src/ untouched and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/scripts/common/caiyun_api.py poc/caiyun/scripts/t2_cookie_probe.py poc/caiyun/results/t2_cookie_probe.jsonl
git commit -m "feat(poc): t2 P1 server-side copy probe"
```

---

### Task 7: T2 P2 cookie probe (list dir + task status)

**Files:**
- Modify: `poc/caiyun/scripts/t2_cookie_probe.py`
- Append: `poc/caiyun/results/t2_cookie_probe.jsonl`

- [ ] **Step 1: Extend the probe script with P2 family**

Add inside `poc/caiyun/scripts/t2_cookie_probe.py`, next to `_run_p1_calls`:

```python
async def _run_p2_calls(creds, candidates) -> list[CaiyunCallResult]:
    cred_a, *_ = creds
    headers_a = {"Authorization": f"Bearer {cred_a.access_token}"}
    results: list[CaiyunCallResult] = []
    async with httpx.AsyncClient(base_url=CAIYUN_BASE_URL) as client:
        for family in ("list_dir", "task_status"):
            match = next((c for c in candidates if family.split("_")[0] in c["url"].lower()), None)
            if match is None:
                continue
            result = await call(
                client=client,
                label=f"P2-{family}",
                method=match["method"] if match["method"] != "?" else "POST",
                url=match["url"],
                json_body={},
                headers=headers_a,
            )
            results.append(result)
    return results
```

Update `main()`:

```python
    if args.priority == "P1":
        results = await _run_p1_calls(creds, candidates)
    elif args.priority == "P2":
        results = await _run_p2_calls(creds, candidates)
    else:
        print("P3 added by Task 8.")
        return 2
```

- [ ] **Step 2: Run P2 probe**

```bash
cd poc/caiyun && python scripts/t2_cookie_probe.py --priority P2
```

Expected: `[t2] appended N P2 results to ...`.

- [ ] **Step 3: Annotate and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/scripts/t2_cookie_probe.py poc/caiyun/results/t2_cookie_probe.jsonl
git commit -m "feat(poc): t2 P2 list + task status probe"
```

---

### Task 8: T2 P3 cookie probe (share-save fallback)

**Files:**
- Modify: `poc/caiyun/scripts/t2_cookie_probe.py`
- Append: `poc/caiyun/results/t2_cookie_probe.jsonl`

This is the share-transfer fallback — only run if Task 6 / Task 7 results do not already deliver a feasible path. If P1 succeeded, document `skipped: P1 already feasible` in the jsonl and commit only the script change.

- [ ] **Step 1: Decide whether to skip**

Read `results/t2_cookie_probe.jsonl`. If any P1 line has `"verdict": "feasible"`, skip to Step 4 and append an explicit `{"label":"P3","status":"skipped","reason":"P1 already feasible"}` line.

- [ ] **Step 2: Extend the probe script with P3 family**

Add inside `poc/caiyun/scripts/t2_cookie_probe.py`:

```python
async def _run_p3_calls(creds, candidates) -> list[CaiyunCallResult]:
    cred_a, *_rest = creds
    cred_b = _rest[0] if _rest else cred_a
    headers_b = {"Authorization": f"Bearer {cred_b.access_token}"}
    results: list[CaiyunCallResult] = []
    async with httpx.AsyncClient(base_url=CAIYUN_BASE_URL) as client:
        for family in ("share_recognize", "share_save"):
            match = next((c for c in candidates if "share" in c["url"].lower()), None)
            if match is None:
                continue
            result = await call(
                client=client,
                label=f"P3-{family}",
                method=match["method"] if match["method"] != "?" else "POST",
                url=match["url"],
                json_body={},
                headers=headers_b,
            )
            results.append(result)
    return results
```

Update `main()`:

```python
    elif args.priority == "P3":
        results = await _run_p3_calls(creds, candidates)
```

- [ ] **Step 3: Run P3 probe (only if not skipped)**

```bash
cd poc/caiyun && python scripts/t2_cookie_probe.py --priority P3
```

Expected: `[t2] appended N P3 results to ...`.

- [ ] **Step 4: Annotate and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/scripts/t2_cookie_probe.py poc/caiyun/results/t2_cookie_probe.jsonl
git commit -m "feat(poc): t2 P3 share fallback probe"
```

---

### Task 9: Write the feasibility report

**Files:**
- Modify: `poc/caiyun/reports/2026-05-23-caiyun-poc-report.md`

The report must follow the structure in the spec section "最终报告结构":
- 4.1 Path comparison table (T1 / T2 / T3 three-state verdict; T4 listed separately as capture findings)
- 4.2 Selected backend implementation path
- 4.3 media-pro PR sketch (file list, pseudocode, Alembic, test impact, size estimate)
- 4.4 Risks and outstanding items

- [ ] **Step 1: Draft the report skeleton**

Replace `poc/caiyun/reports/2026-05-23-caiyun-poc-report.md`:

```markdown
# Caiyun POC Feasibility Report

Spec: ../../docs/superpowers/specs/2026-05-23-caiyun-poc-design.md

## 4.1 Path comparison

| Path | API surface | Auth model | Dedup hit | Throughput | Rate limit | Verdict |
|---|---|---|---|---|---|---|
| T1 static-derived endpoints | _fill_ | _fill_ | _fill_ | n/a | n/a | _feasible / feasible-with-conditions / infeasible_ |
| T2 cookie direct-call P1 | _fill_ | _fill_ | _fill_ | _fill_ | _fill_ | _verdict_ |
| T3 OpenList copy | _fill_ | _fill_ | _fill_ | _fill_ | _fill_ | _verdict_ |

### T4 capture findings (not a path, used to feed T2)

- Captured N endpoints across S1 / S2 / S3 scenarios.
- Notable headers requiring browser context: _list any_.
- Endpoints handed to T2 that proved server-replayable: _list any_.

## 4.2 Selected backend implementation path

_Pick the winning path from 4.1. Justify the choice with hard numbers from the results files._

Recommended architecture for `caiyun-rapid-copy`:
- Deployment: _HTTP service vs Playwright sidecar_
- Auth strategy: _OpenList-managed token refresh vs cached cookie jar_
- Idempotency: _what does the upstream API guarantee_
- Failure modes: _per-API error codes and mappings_

## 4.3 media-pro PR sketch

### Files
- New: `src/gateway/integrations/caiyun_rapid_copy_client.py`
- New: `alembic/versions/<id>_add_caiyun_drive_type.py`
- Modify: `src/gateway/models.py` — extend `DRIVE_TYPE_VALUES`
- Modify: `src/gateway/playback_resolver.py` — replace three `== "115"` checks with capability dispatch
- Modify: `src/gateway/api/admin.py` — add `caiyun` branch to `probe`
- Tests: `tests/integrations/test_caiyun_rapid_copy_client.py`, `tests/playback/test_playback_resolver_caiyun.py`, `tests/api/test_admin_caiyun_probe.py`

### Pseudocode

`caiyun_rapid_copy_client.py`:

```python
class CaiyunRapidCopyClient:
    def __init__(self, base_url: str) -> None: ...
    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult: ...
    async def health_check(self, cookie: str) -> ProbeResult: ...
```

`playback_resolver.py` change:

```python
# was: UserDriveAccount.drive_type == "115"
# now: UserDriveAccount.drive_type.in_(SUPPORTED_DRIVE_TYPES)
```

### Alembic migration

```python
def upgrade() -> None:
    op.execute("UPDATE user_drive_accounts SET drive_type = drive_type")  # no schema change; values only
```

(Adjust depending on whether `drive_type` is an enum or a free string column.)

### Test impact

- Add `tests/integrations/test_caiyun_rapid_copy_client.py` (~80 LOC)
- Add `tests/playback/test_playback_resolver_caiyun.py` (~120 LOC)
- Add `tests/api/test_admin_caiyun_probe.py` (~60 LOC)
- Existing 115 tests remain untouched.

### Size estimate

- New files: ~250 LOC (client + tests)
- Modified files: ~30 LOC (resolver + admin + models)
- Migration: ~10 LOC

## 4.4 Risks and outstanding items

- _Token refresh ownership_: who refreshes the 139 access token — OpenList or the new caiyun service?
- _Rate-limit headroom_: production traffic vs POC sample size.
- _Cross-account migration legitimacy_: confirm 139 ToS permits server-side cross-account copy.
- _OpenList coupling_: should media-pro keep depending on OpenList for credentials, or take direct ownership?
```

- [ ] **Step 2: Fill the report from the results files**

Open each results file (`t1_api_inventory.md`, `t2_cookie_probe.jsonl`, `t3_openlist_probe.md`, `t4_api_findings.md`) and copy the relevant numbers / endpoints into the table and the prose sections. Replace every `_fill_` and `_verdict_` marker.

- [ ] **Step 3: Verify the report has no placeholders**

Run: `grep -nE '_fill_|_verdict_|TODO' poc/caiyun/reports/2026-05-23-caiyun-poc-report.md`
Expected: no output.

- [ ] **Step 4: Verify src/ untouched and commit**

```bash
git diff src/ | wc -l
git add poc/caiyun/reports/2026-05-23-caiyun-poc-report.md
git commit -m "docs(poc): caiyun feasibility report and PR sketch"
```

---

## Final acceptance

After all tasks complete, run:

```bash
git diff master --stat -- src/
```

Expected: empty. If anything under `src/` shows up, the POC has violated its boundary; revert before requesting review.

Open `poc/caiyun/reports/2026-05-23-caiyun-poc-report.md` and confirm it answers the three spec questions:
1. Which path does caiyun rapid-copy take?
2. Does gateway need provider abstraction now or later?
3. Which media-pro files change for caiyun integration?
