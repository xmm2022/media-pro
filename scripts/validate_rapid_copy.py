import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.rapid_copy_client import RapidCopyClient
from gateway.script_inputs import build_rapid_copy_probe


async def main() -> None:
    probe = build_rapid_copy_probe(settings)
    client = RapidCopyClient(settings.rapid_copy_base_url)
    result = await client.copy(
        probe.donor_cookie,
        probe.target_cookie,
        probe.source_path,
        probe.target_path,
    )
    print({"ok": result.ok, "error_code": result.error_code})


if __name__ == "__main__":
    asyncio.run(main())
