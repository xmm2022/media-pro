from pathlib import Path
from urllib.parse import parse_qs, urlparse

import gateway.api.playback as playback_module
import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import StreamInfo
from gateway.integrations.rapid_copy_client import RapidCopyResult
from gateway.main import create_app
from gateway.models import Base, MediaItem, User, UserDriveAccount
from gateway.security import CookieCipher


class StubOpenListClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def get_stream_info(self, source_path: str) -> StreamInfo:
        stream_urls = {
            "/Movies/Movie.2024.mkv": "https://openlist.local/source.mkv",
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
        assert request.target_cookie == "UID=alice"
        assert request.source.openlist_path == "/Movies/Movie.2024.mkv"
        assert request.source.source_path == "/Movies/Movie.2024.mkv"
        assert request.source.source_file_id == "gd-1"
        assert request.source.fingerprint == "2048:movie.2024:mkv"
        assert request.target_path == "/EmbyCache/alice/Movies/Movie.2024.mkv"
        return RapidCopyResult(ok=True, error_code=None, target_path=request.target_path)

    async def aclose(self) -> None:
        return None


class StubPoolCopy115Client:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def copy_from_pool(self, _request) -> RapidCopyResult:
        raise AssertionError("pool copy should not be used in this test")

    async def aclose(self) -> None:
        return None


class StubDrive115StreamClient:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def get_stream_info(self, target_cookie: str, target_path: str) -> StreamInfo:
        assert target_cookie == "UID=alice"
        assert target_path == "/EmbyCache/alice/Movies/Movie.2024.mkv"
        return StreamInfo(
            raw_url="https://115.local/alice/movie.mkv",
            content_length=2048,
            accepts_ranges=True,
            request_headers={"user-agent": ""},
        )


def test_playback_api_reads_real_user_context(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-api.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)
    monkeypatch.setattr(playback_module, "SourceCopy115Client", StubSourceCopy115Client)
    monkeypatch.setattr(playback_module, "PoolCopy115Client", StubPoolCopy115Client)
    monkeypatch.setattr(playback_module, "Drive115StreamClient", StubDrive115StreamClient)

    with Session(engine) as session:
        cipher = CookieCipher("x" * 32)
        user = User(username="alice", status="active")
        session.add(user)
        session.flush()
        session.add(
            UserDriveAccount(
                user_id=user.id,
                drive_type="115",
                cookie_encrypted=cipher.encrypt("UID=alice"),
                root_dir="/EmbyCache/alice",
                enabled=True,
                share_pool_enabled=False,
                health_status="healthy",
            )
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()
        user_id = user.id
        media_id = media.id

    with TestClient(create_app(database_url=database_url, cookie_secret="x" * 32)) as client:
        response = client.get(f"/api/playback/{media_id}", params={"user_id": user_id})

    assert response.status_code == 200
    payload = response.json()
    parsed = urlparse(payload["stream_url"])
    token = parse_qs(parsed.query)["token"][0]
    assert parsed.scheme == "http"
    assert parsed.netloc == "testserver"
    assert parsed.path == f"/api/playback/{media_id}/stream"
    assert payload == {
        "user_id": user_id,
        "media_id": media_id,
        "route": "source_copy",
        "stream_url": payload["stream_url"],
        "upstream_stream_url": "https://115.local/alice/movie.mkv",
        "upstream_stream_headers": {"user-agent": ""},
    }
    assert token


def test_playback_api_does_not_require_rapid_copy_runtime(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-api-no-rapid-copy.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)
    monkeypatch.setattr(playback_module, "SourceCopy115Client", StubSourceCopy115Client)
    monkeypatch.setattr(playback_module, "PoolCopy115Client", StubPoolCopy115Client)
    monkeypatch.setattr(playback_module, "Drive115StreamClient", StubDrive115StreamClient)

    with Session(engine) as session:
        cipher = CookieCipher("x" * 32)
        user = User(username="alice", status="active")
        session.add(user)
        session.flush()
        session.add(
            UserDriveAccount(
                user_id=user.id,
                drive_type="115",
                cookie_encrypted=cipher.encrypt("UID=alice"),
                root_dir="/EmbyCache/alice",
                enabled=True,
                share_pool_enabled=False,
                health_status="healthy",
            )
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()
        user_id = user.id
        media_id = media.id

    with TestClient(create_app(database_url=database_url, cookie_secret="x" * 32)) as client:
        response = client.get(f"/api/playback/{media_id}", params={"user_id": user_id})

    assert response.status_code == 200
    assert response.json()["route"] == "source_copy"


@respx.mock
def test_playback_stream_api_proxies_upstream_range_request(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-stream-api.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)
    monkeypatch.setattr(playback_module, "SourceCopy115Client", StubSourceCopy115Client)
    monkeypatch.setattr(playback_module, "PoolCopy115Client", StubPoolCopy115Client)
    monkeypatch.setattr(playback_module, "Drive115StreamClient", StubDrive115StreamClient)
    upstream = respx.get("https://115.local/alice/movie.mkv").mock(
        return_value=httpx.Response(
            206,
            content=b"0123456789abcdef",
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": "16",
                "Content-Range": "bytes 0-15/2048",
                "Accept-Ranges": "bytes",
            },
        )
    )

    with Session(engine) as session:
        cipher = CookieCipher("x" * 32)
        user = User(username="alice", status="active")
        session.add(user)
        session.flush()
        session.add(
            UserDriveAccount(
                user_id=user.id,
                drive_type="115",
                cookie_encrypted=cipher.encrypt("UID=alice"),
                root_dir="/EmbyCache/alice",
                enabled=True,
                share_pool_enabled=False,
                health_status="healthy",
            )
        )
        media = MediaItem(
            source_path="/Movies/Movie.2024.mkv",
            source_file_id="gd-1",
            size=2048,
            fingerprint="2048:movie.2024:mkv",
            openlist_path="/Movies/Movie.2024.mkv",
        )
        session.add(media)
        session.commit()
        user_id = user.id
        media_id = media.id

    with TestClient(create_app(database_url=database_url, cookie_secret="x" * 32)) as client:
        playback = client.get(f"/api/playback/{media_id}", params={"user_id": user_id})
        stream_url = playback.json()["stream_url"]
        response = client.get(stream_url, headers={"Range": "bytes=0-15"})

    assert response.status_code == 206
    assert response.content == b"0123456789abcdef"
    assert response.headers["content-type"] == "video/mp4"
    assert response.headers["content-length"] == "16"
    assert response.headers["content-range"] == "bytes 0-15/2048"
    assert response.headers["accept-ranges"] == "bytes"
    assert upstream.calls.last.request.headers["range"] == "bytes=0-15"
    assert upstream.calls.last.request.headers["user-agent"] == ""
    assert upstream.calls.last.request.headers["accept-encoding"] == "identity"


def test_playback_stream_api_rejects_invalid_token(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'playback-invalid-token.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(playback_module, "OpenListClient", StubOpenListClient)
    monkeypatch.setattr(playback_module, "SourceCopy115Client", StubSourceCopy115Client)
    monkeypatch.setattr(playback_module, "PoolCopy115Client", StubPoolCopy115Client)
    monkeypatch.setattr(playback_module, "Drive115StreamClient", StubDrive115StreamClient)

    with TestClient(create_app(database_url=database_url, cookie_secret="x" * 32)) as client:
        response = client.get("/api/playback/1/stream", params={"token": "broken-token"})

    assert response.status_code == 403
    assert response.json() == {"detail": "invalid playback token"}
