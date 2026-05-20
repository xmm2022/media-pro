import httpx
import pytest
import respx

from gateway.integrations.openlist_client import OpenListObjectInfo
from gateway.integrations.rapid_copy_client import SourceCopyRequest, SourceObjectRef
from gateway.integrations.source_copy_115_client import SourceCopy115Client


class StubOpenListClient:
    def __init__(self, info: OpenListObjectInfo) -> None:
        self.info = info
        self.calls: list[str] = []

    async def get_object_info(self, source_path: str) -> OpenListObjectInfo:
        self.calls.append(source_path)
        return self.info


class StubP115Client:
    def __init__(self, *, upload_response: dict[str, object]) -> None:
        self.upload_response = upload_response
        self.user_key = ""
        self.mkdir_calls: list[dict[str, object]] = []
        self.getid_calls: list[dict[str, object]] = []
        self.upload_info_calls = 0
        self.upload_calls: list[dict[str, object]] = []
        self.range_sample: bytes | None = None

    def upload_info(self) -> dict[str, object]:
        self.upload_info_calls += 1
        return {"state": True, "userkey": "userkey-value"}

    def fs_makedirs_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.mkdir_calls.append(payload)
        return {"state": True, "cid": "dir-123"}

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.getid_calls.append(payload)
        return {"state": True, "id": "dir-123"}

    def upload_file_init(
        self,
        filename: str,
        filesize: int,
        filesha1: str,
        read_range_bytes_or_hash,
        pid: str,
    ) -> dict[str, object]:
        self.upload_calls.append(
            {
                "filename": filename,
                "filesize": filesize,
                "filesha1": filesha1,
                "pid": pid,
            }
        )
        self.range_sample = read_range_bytes_or_hash("0-15")
        return self.upload_response


@pytest.mark.asyncio
@respx.mock
async def test_source_copy_115_client_uses_openlist_hashes_and_range_probe() -> None:
    route = respx.get("https://openlist.local/raw/movie.mkv").mock(
        return_value=httpx.Response(206, content=b"0123456789abcdef")
    )
    openlist_client = StubOpenListClient(
        OpenListObjectInfo(
            path="/Movies/Movie.2024.mkv",
            name="Movie.2024.mkv",
            size=2048,
            raw_url="https://openlist.local/raw/movie.mkv",
            provider="GoogleDrive",
            md5="md5-value",
            sha1="sha1-value",
            sha256="sha256-value",
        )
    )
    p115_client = StubP115Client(upload_response={"state": True, "reuse": True})
    cookies: list[str] = []
    client = SourceCopy115Client(
        openlist_client,
        client_factory=lambda cookie: cookies.append(cookie) or p115_client,
    )

    result = await client.copy_from_source(
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(openlist_path="/Movies/Movie.2024.mkv"),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is True
    assert result.error_code is None
    assert result.target_path == "/EmbyCache/alice/Movies/Movie.2024.mkv"
    assert openlist_client.calls == ["/Movies/Movie.2024.mkv"]
    assert cookies == ["UID=alice"]
    assert p115_client.upload_info_calls == 1
    assert p115_client.user_key == "userkey-value"
    assert p115_client.mkdir_calls == [{"path": "/EmbyCache/alice/Movies"}]
    assert p115_client.getid_calls == []
    assert p115_client.upload_calls == [
        {
            "filename": "Movie.2024.mkv",
            "filesize": 2048,
            "filesha1": "sha1-value",
            "pid": "dir-123",
        }
    ]
    assert p115_client.range_sample == b"0123456789abcdef"
    assert route.calls.last.request.headers["Range"] == "bytes=0-15"


@pytest.mark.asyncio
async def test_source_copy_115_client_rejects_sources_without_sha1() -> None:
    client = SourceCopy115Client(
        StubOpenListClient(
            OpenListObjectInfo(
                path="/Movies/Movie.2024.mkv",
                name="Movie.2024.mkv",
                size=2048,
                raw_url="https://openlist.local/raw/movie.mkv",
                provider="GoogleDrive",
                md5=None,
                sha1=None,
                sha256=None,
            )
        ),
        client_factory=lambda _cookie: (_ for _ in ()).throw(AssertionError("factory should not be called")),
    )

    result = await client.copy_from_source(
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(openlist_path="/Movies/Movie.2024.mkv"),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is False
    assert result.error_code == "missing_source_hash"


@pytest.mark.asyncio
@respx.mock
async def test_source_copy_115_client_marks_non_reuse_upload_as_unsupported() -> None:
    respx.get("https://openlist.local/raw/movie.mkv").mock(
        return_value=httpx.Response(206, content=b"0123456789abcdef")
    )
    client = SourceCopy115Client(
        StubOpenListClient(
            OpenListObjectInfo(
                path="/Movies/Movie.2024.mkv",
                name="Movie.2024.mkv",
                size=2048,
                raw_url="https://openlist.local/raw/movie.mkv",
                provider="GoogleDrive",
                md5="md5-value",
                sha1="sha1-value",
                sha256="sha256-value",
            )
        ),
        client_factory=lambda _cookie: StubP115Client(
            upload_response={"state": True, "reuse": False}
        ),
    )

    result = await client.copy_from_source(
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(openlist_path="/Movies/Movie.2024.mkv"),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is False
    assert result.error_code == "quick_upload_unavailable"


@pytest.mark.asyncio
async def test_source_copy_115_client_uses_root_pid_without_mkdir() -> None:
    p115_client = StubP115Client(upload_response={"state": True, "reuse": True})
    client = SourceCopy115Client(
        StubOpenListClient(
            OpenListObjectInfo(
                path="/Movies/Movie.2024.mkv",
                name="Movie.2024.mkv",
                size=512,
                raw_url="https://openlist.local/raw/movie.mkv",
                provider="GoogleDrive",
                md5="md5-value",
                sha1="sha1-value",
                sha256="sha256-value",
            )
        ),
        client_factory=lambda _cookie: p115_client,
        range_client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(206, content=b"x"))),
    )

    result = await client.copy_from_source(
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(openlist_path="/Movies/Movie.2024.mkv"),
            target_path="/Movie.2024.mkv",
        )
    )

    assert result.ok is True
    assert p115_client.mkdir_calls == []
    assert p115_client.getid_calls == []
    assert p115_client.upload_calls[0]["pid"] == "0"


@pytest.mark.asyncio
async def test_source_copy_115_client_maps_115_large_file_limit() -> None:
    client = SourceCopy115Client(
        StubOpenListClient(
            OpenListObjectInfo(
                path="/Movies/Movie.2024.mkv",
                name="Movie.2024.mkv",
                size=2048,
                raw_url="https://openlist.local/raw/movie.mkv",
                provider="GoogleDrive",
                md5="md5-value",
                sha1="sha1-value",
                sha256="sha256-value",
            )
        ),
        client_factory=lambda _cookie: StubP115Client(
            upload_response={
                "state": False,
                "statuscode": 10005,
                "statusmsg": "单文件大于5GB不能上传",
            }
        ),
        range_client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(206, content=b"x"))),
    )

    result = await client.copy_from_source(
        SourceCopyRequest(
            target_cookie="UID=alice",
            source=SourceObjectRef(openlist_path="/Movies/Movie.2024.mkv"),
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is False
    assert result.error_code == "file_too_large_for_account"
    assert result.detail == "单文件大于5GB不能上传"
