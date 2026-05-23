"""Track 4: HAR parsing (no browser driver).

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 4

Operator captures a HAR file using any browser's DevTools (Chrome
Network panel "Save all as HAR with content" works), then this
script parses it into a candidate API list to feed T2.

Browser is driven manually because T4 runs at most a few times
in this POC; automating it with Playwright would add a 500 MB
Chromium dependency for zero throughput gain.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HAR_DEFAULT = ROOT / "results" / "t4_playwright_capture.har"
FINDINGS_PATH = ROOT / "results" / "t4_api_findings.md"


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
    lines.append("- Map each row above to scenario S1 (same-account copy) / S2 (cross-account migration) / S3 (upload).")
    lines.append("- Highlight rows whose body or response suggests hash-based dedup.")
    lines.append("- Flag rows requiring browser-only headers (e.g. signature, fingerprint).")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--har",
        type=Path,
        default=HAR_DEFAULT,
        help="Path to the HAR file exported from a browser DevTools session.",
    )
    args = parser.parse_args()
    if not args.har.exists():
        print(
            f"[t4] HAR file not found: {args.har}\n"
            "Open Chrome -> F12 -> Network -> log in to 139, trigger S1/S2/S3, "
            "right-click any request -> 'Save all as HAR with content' and save it "
            f"to that path before re-running.",
            file=sys.stderr,
        )
        return 1
    findings = parse_har(args.har)
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINDINGS_PATH.write_text(render_findings(findings), encoding="utf-8")
    print(f"[t4] parsed {args.har} -> {FINDINGS_PATH} ({len(findings)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
