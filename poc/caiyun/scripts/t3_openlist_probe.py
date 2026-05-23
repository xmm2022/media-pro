"""Track 3: OpenList copy-behavior probe.

Spec: docs/superpowers/specs/2026-05-23-caiyun-poc-design.md
section: 设计 / Track 3

Scenarios:
  - same-account 139 copy
  - cross-account 139 copy
  - GD storage -> 139 storage cross-storage copy
  - throughput at 100MB / 1GB / 10GB
  - dedup hit on second copy

Output:
  results/t3_openlist_probe.md
"""
