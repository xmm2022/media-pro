import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.openlist_client import OpenListClient
from gateway.script_inputs import build_openlist_probe_path


async def main() -> None:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    try:
        info = await client.get_stream_info(build_openlist_probe_path(settings))
        print({"url": info.raw_url, "accepts_ranges": info.accepts_ranges})
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
