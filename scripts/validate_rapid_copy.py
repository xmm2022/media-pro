import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.openlist_client import OpenListClient
from gateway.integrations.pool_copy_115_client import PoolCopy115Client
from gateway.integrations.source_copy_115_client import SourceCopy115Client
from gateway.script_inputs import build_pool_copy_probe, build_source_copy_probe


async def main() -> None:
    openlist_client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    source_copy_client = SourceCopy115Client(openlist_client)
    pool_copy_client = PoolCopy115Client()
    try:
        source_probe = build_source_copy_probe(settings)
        source_result = await source_copy_client.copy_from_source(source_probe)
        output: dict[str, object] = {
            "source_copy": {"ok": source_result.ok, "error_code": source_result.error_code}
        }
        try:
            pool_probe = build_pool_copy_probe(settings)
        except ValueError as exc:
            output["pool_copy"] = {"skipped": True, "reason": str(exc)}
        else:
            pool_result = await pool_copy_client.copy_from_pool(pool_probe)
            output["pool_copy"] = {"ok": pool_result.ok, "error_code": pool_result.error_code}
        print(output)
    finally:
        await source_copy_client.aclose()
        await pool_copy_client.aclose()
        await openlist_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
