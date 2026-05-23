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
