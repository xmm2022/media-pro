import asyncio
import sys
from pathlib import Path

from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateway.config import settings
from gateway.db import init_schema, make_engine
from gateway.integrations.openlist_client import OpenListClient
from gateway.integrations.rapid_copy_client import RapidCopyClient
from gateway.real_integration import run_real_integration_probe


async def main() -> None:
    engine = make_engine(settings.database_url)
    init_schema(engine)
    openlist_client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    rapid_copy_client = RapidCopyClient(settings.rapid_copy_base_url)
    try:
        with Session(engine) as session:
            summary = await run_real_integration_probe(
                session=session,
                app_settings=settings,
                openlist_client=openlist_client,
                rapid_copy_client=rapid_copy_client,
            )
        print(summary)
    finally:
        await openlist_client.aclose()
        await rapid_copy_client.aclose()
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
