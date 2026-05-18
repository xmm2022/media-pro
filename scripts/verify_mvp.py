from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from gateway.api import playback as playback_api
from gateway.main import create_app
from gateway.integrations.openlist_client import StreamInfo
from gateway.models import MediaItem, User


class StubOpenListClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        assert source_path == "/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://drive.local/Movie.2024.mkv",
            content_length=2048,
            accepts_ranges=True,
        )

    async def aclose(self) -> None:
        return None


def seed_mvp_data(client: TestClient) -> tuple[int, int]:
    with client.app.state.session_factory() as session:
        user = User(username="mvp-user", status="active")
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add_all([user, media])
        session.commit()
        return user.id, media.id


def main() -> None:
    original_client = playback_api.OpenListClient
    playback_api.OpenListClient = StubOpenListClient
    try:
        with TemporaryDirectory() as tmpdir:
            database_url = f"sqlite:///{Path(tmpdir) / 'verify-mvp.db'}"
            with TestClient(create_app(database_url=database_url)) as client:
                user_id, media_id = seed_mvp_data(client)
                health = client.get("/health")
                playback = client.get(f"/api/playback/{media_id}", params={"user_id": user_id})
                stats = client.get("/api/admin/stats")
                print(
                    {
                        "health": health.status_code,
                        "playback_route": playback.json()["route"],
                        "stats_keys": sorted(stats.json().keys()),
                    }
                )
    finally:
        playback_api.OpenListClient = original_client


if __name__ == "__main__":
    main()
