"""End-to-end smoke for caiyun source_copy.

Prereqs:
- Local OpenList running at GATEWAY_OPENLIST_BASE_URL
- One 139 storage mounted at CAIYUN_MOUNT_PATH
- One GD storage with a small sample file at GD_SOURCE_PATH

Usage:
    GATEWAY_OPENLIST_BASE_URL=http://localhost:5246 \\
    GATEWAY_OPENLIST_ADMIN_TOKEN=<token> \\
    CAIYUN_MOUNT_PATH=/caiyun-test \\
    GD_SOURCE_PATH=/gd/sample.mkv \\
    CAIYUN_TARGET_SUBDIR=/EmbyCache \\
    uv run python scripts/validate_caiyun_source_copy.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.integrations.openlist_admin_client import OpenListAdminClient


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


async def main() -> int:
    base_url = _env("GATEWAY_OPENLIST_BASE_URL")
    admin_token = _env("GATEWAY_OPENLIST_ADMIN_TOKEN")
    caiyun_mount = _env("CAIYUN_MOUNT_PATH")
    gd_source = _env("GD_SOURCE_PATH")
    target_subdir = os.environ.get("CAIYUN_TARGET_SUBDIR", "/EmbyCache")

    source = PurePosixPath(gd_source)
    target = PurePosixPath(caiyun_mount + target_subdir + "/" + source.name)

    admin = OpenListAdminClient(base_url=base_url, admin_token=admin_token)
    try:
        print(f"[smoke] copy {source} -> {target}")
        start = time.monotonic()
        result = await admin.fs_copy(
            src_dir=str(source.parent),
            dst_dir=str(target.parent),
            names=[source.name],
        )
        elapsed = time.monotonic() - start
        print(
            f"[smoke] result ok={result.ok} "
            f"task_id={result.task_id} error={result.error} ({elapsed:.2f}s)"
        )
        if not result.ok:
            return 1

        print(f"[smoke] verify target via fs_list {target.parent}")
        items = await admin.fs_list(str(target.parent))
        found = any(item.name == source.name for item in items)
        print(f"[smoke] target file present: {found}")
        return 0 if found else 2
    finally:
        await admin.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
