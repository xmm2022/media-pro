import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.integrations.rapid_copy_client import RapidCopyClient


async def main() -> None:
    client = RapidCopyClient(settings.rapid_copy_base_url)
    result = await client.copy(
        "donor",
        "target",
        "/Movies/sample.mkv",
        "/EmbyCache/sample.mkv",
    )
    print({"ok": result.ok, "error_code": result.error_code})


if __name__ == "__main__":
    asyncio.run(main())
