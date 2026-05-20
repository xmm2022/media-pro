from pathlib import Path
from tempfile import TemporaryDirectory

import gateway.api.playback as playback_module
from fastapi.testclient import TestClient

from gateway.integrations.openlist_client import StreamInfo
from gateway.integrations.rapid_copy_client import RapidCopyResult
from gateway.main import create_app
from gateway.models import MediaItem


class StubOpenListClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        stream_urls = {
            "/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv",
            "/EmbyCache/verify-user/Movies/Movie.2024.mkv": "https://115.local/verify-user/movie.mkv",
        }
        return StreamInfo(
            raw_url=stream_urls[source_path],
            content_length=2048,
            accepts_ranges=True,
        )

    async def aclose(self) -> None:
        return None


class StubSourceCopy115Client:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def copy_from_source(self, request) -> RapidCopyResult:
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None:
        return None


class StubPoolCopy115Client:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def copy_from_pool(self, _request) -> RapidCopyResult:
        raise AssertionError("pool copy should not be used in verify_mvp")

    async def aclose(self) -> None:
        return None


def main() -> None:
    playback_module.OpenListClient = StubOpenListClient
    playback_module.SourceCopy115Client = StubSourceCopy115Client
    playback_module.PoolCopy115Client = StubPoolCopy115Client

    with TemporaryDirectory() as tmp_dir:
        database_url = f"sqlite:///{Path(tmp_dir) / 'verify-mvp.db'}"
        with TestClient(create_app(database_url=database_url, cookie_secret="x" * 32)) as client:
            user = client.post("/api/admin/users", json={"username": "verify-user", "status": "active"}).json()
            client.post(
                "/api/admin/drives",
                json={
                    "user_id": user["id"],
                    "drive_type": "115",
                    "cookie": "UID=verify-user",
                    "root_dir": "/EmbyCache/verify-user",
                    "share_pool_enabled": False,
                },
            )
            with client.app.state.session_factory() as session:
                session.add(
                    MediaItem(
                        source_path="/Movies/Movie.2024.mkv",
                        source_file_id="gd-1",
                        size=2048,
                        fingerprint="2048:movie.2024:mkv",
                        openlist_path="/Movies/Movie.2024.mkv",
                    )
                )
                session.commit()
            health = client.get("/health")
            playback = client.get("/api/playback/1", params={"user_id": user["id"]})
            stats = client.get("/api/admin/stats")
            print(
                {
                    "health": health.status_code,
                    "playback_route": playback.json()["route"],
                    "stats_keys": sorted(stats.json().keys()),
                }
            )


if __name__ == "__main__":
    main()
