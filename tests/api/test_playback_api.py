from fastapi.testclient import TestClient

from gateway.main import create_app


def test_playback_api_returns_source_stream_payload() -> None:
    client = TestClient(create_app())

    response = client.get("/api/playback/42")

    assert response.status_code == 200
    assert response.json()["route"] in {"self", "pool", "source_copy", "source_stream"}
