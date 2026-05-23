"""Track 4: Playwright dynamic API capture.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 4

Scope: non-share operations only.
  - same-account copy / move
  - cross-account migration (if 139 web exposes it)
  - upload (prepare + hash + put)

Capture outbound HTTP and feed candidates back into T2 input.

Output:
  results/t4_playwright_capture.har
  results/t4_api_findings.md
"""
