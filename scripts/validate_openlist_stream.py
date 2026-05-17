import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.openlist_client import OpenListClient


async def main() -> None:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    info = await client.get_stream_info("/Movies/sample.mkv")
    print({"url": info.raw_url, "accepts_ranges": info.accepts_ranges})


if __name__ == "__main__":
    asyncio.run(main())
