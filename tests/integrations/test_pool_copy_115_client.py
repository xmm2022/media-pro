import httpx
import pytest
import respx

from gateway.integrations.pool_copy_115_client import PoolCopy115Client
from gateway.integrations.rapid_copy_client import PoolCopyRequest


class StubP115Url(str):
    def __new__(cls, value: str, *, headers: dict[str, str] | None = None):
        instance = str.__new__(cls, value)
        instance.headers = headers or {}
        return instance


class StubDonor115Client:
    def __init__(self) -> None:
        self.dir_calls: list[dict[str, object]] = []
        self.search_calls: list[dict[str, object]] = []
        self.supervision_calls: list[str] = []
        self.download_calls: list[tuple[str, str]] = []

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.dir_calls.append(payload)
        return {"id": "donor-dir-123"}

    def fs_search(self, payload: dict[str, object]) -> dict[str, object]:
        self.search_calls.append(payload)
        return {
            "data": [
                {"n": "Movie.2024.mkv", "pc": "other-pickcode", "cid": "other-dir"},
                {"n": "Movie.2024.mkv", "pc": "pickcode-123", "cid": "donor-dir-123"},
            ]
        }

    def fs_supervision(self, pickcode: str) -> dict[str, object]:
        self.supervision_calls.append(pickcode)
        return {
            "state": True,
            "data": {
                "file_name": "Movie.2024.mkv",
                "file_sha1": "sha1-value",
                "file_size": 2048,
            },
        }

    def download_url(self, pickcode: str, *, app: str) -> StubP115Url:
        self.download_calls.append((pickcode, app))
        return StubP115Url(
            "https://115.local/download/movie.mkv",
            headers={"user-agent": ""},
        )


class StubTarget115Client:
    def __init__(self, *, upload_response: dict[str, object]) -> None:
        self.user_key = ""
        self.upload_response = upload_response
        self.upload_info_calls = 0
        self.mkdir_calls: list[dict[str, object]] = []
        self.getid_calls: list[dict[str, object]] = []
        self.upload_calls: list[dict[str, object]] = []
        self.range_sample: bytes | None = None

    def upload_info(self) -> dict[str, object]:
        self.upload_info_calls += 1
        return {"state": True, "userkey": "userkey-value"}

    def fs_makedirs_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.mkdir_calls.append(payload)
        return {"state": True, "cid": "target-dir-123"}

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.getid_calls.append(payload)
        return {"state": True, "id": "target-dir-123"}

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
async def test_pool_copy_115_client_reads_donor_range_and_uploads_to_target() -> None:
    route = respx.get("https://115.local/download/movie.mkv").mock(
        return_value=httpx.Response(206, content=b"0123456789abcdef")
    )
    donor = StubDonor115Client()
    target = StubTarget115Client(upload_response={"state": True, "reuse": True})
    client = PoolCopy115Client(
        client_factory=lambda cookie: donor if cookie == "UID=donor" else target,
    )

    result = await client.copy_from_pool(
        PoolCopyRequest(
            donor_cookie="UID=donor",
            target_cookie="UID=target",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is True
    assert result.target_path == "/EmbyCache/alice/Movies/Movie.2024.mkv"
    assert donor.dir_calls == [{"path": "/EmbyCache/bob/Movies"}]
    assert donor.search_calls == [
        {
            "cid": "donor-dir-123",
            "search_value": "Movie.2024.mkv",
            "limit": 32,
            "offset": 0,
            "fc": 2,
            "show_dir": 0,
        }
    ]
    assert donor.supervision_calls == ["pickcode-123"]
    assert donor.download_calls == [("pickcode-123", "chrome")]
    assert target.upload_info_calls == 1
    assert target.user_key == "userkey-value"
    assert target.mkdir_calls == [{"path": "/EmbyCache/alice/Movies"}]
    assert target.getid_calls == []
    assert target.upload_calls == [
        {
            "filename": "Movie.2024.mkv",
            "filesize": 2048,
            "filesha1": "sha1-value",
            "pid": "target-dir-123",
        }
    ]
    assert target.range_sample == b"0123456789abcdef"
    assert route.calls.last.request.headers["Range"] == "bytes=0-15"
    assert route.calls.last.request.headers["user-agent"] == ""


@pytest.mark.asyncio
async def test_pool_copy_115_client_maps_missing_donor_file() -> None:
    class MissingDonorClient(StubDonor115Client):
        def fs_search(self, payload: dict[str, object]) -> dict[str, object]:
            self.search_calls.append(payload)
            return {"data": []}

    target = StubTarget115Client(upload_response={"state": True, "reuse": True})
    client = PoolCopy115Client(
        client_factory=lambda cookie: MissingDonorClient() if cookie == "UID=donor" else target,
    )

    result = await client.copy_from_pool(
        PoolCopyRequest(
            donor_cookie="UID=donor",
            target_cookie="UID=target",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is False
    assert result.error_code == "missing_donor_file"


@pytest.mark.asyncio
async def test_pool_copy_115_client_maps_large_file_limit() -> None:
    donor = StubDonor115Client()
    target = StubTarget115Client(
        upload_response={
            "state": False,
            "statuscode": 10005,
            "statusmsg": "单文件大于5GB不能上传",
        }
    )
    client = PoolCopy115Client(
        client_factory=lambda cookie: donor if cookie == "UID=donor" else target,
        range_client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(206, content=b"x"))),
    )

    result = await client.copy_from_pool(
        PoolCopyRequest(
            donor_cookie="UID=donor",
            target_cookie="UID=target",
            source_path="/EmbyCache/bob/Movies/Movie.2024.mkv",
            target_path="/EmbyCache/alice/Movies/Movie.2024.mkv",
        )
    )

    assert result.ok is False
    assert result.error_code == "file_too_large_for_account"
    assert result.detail == "单文件大于5GB不能上传"
