from fastapi.testclient import TestClient

from gateway.main import create_app


def main() -> None:
    client = TestClient(create_app())
    health = client.get("/health")
    playback = client.get("/api/playback/1")
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
