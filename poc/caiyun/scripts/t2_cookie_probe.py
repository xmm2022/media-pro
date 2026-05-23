"""Track 2: cookie / token direct-call validation.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 2

Depends on T1 + T4 outputs. Run after API candidates exist.

Priority order:
  P1 — server-side same-account copy
  P1 — server-side cross-account copy / migration
  P1 — upload / hash dedup
  P2 — list / task status
  P3 — share recognition + share-save (fallback only)

Output:
  results/t2_cookie_probe.jsonl
"""
