import pytest

from gateway.integrations.drive115_health_client import Drive115HealthClient, DriveHealthResult


class StubP115Client:
    def __init__(
        self,
        *,
        upload_info_response: dict[str, object] | None = None,
        mkdir_response: dict[str, object] | None = None,
        getid_response: dict[str, object] | None = None,
    ) -> None:
        self.user_key = ""
        self.upload_info_response = upload_info_response or {"state": True, "userkey": "userkey-value"}
        self.mkdir_response = mkdir_response or {"state": True, "cid": "dir-123"}
        self.getid_response = getid_response or {"state": True, "id": "dir-123"}
        self.upload_info_calls = 0
        self.mkdir_calls: list[dict[str, object]] = []
        self.getid_calls: list[dict[str, object]] = []

    def upload_info(self) -> dict[str, object]:
        self.upload_info_calls += 1
        return self.upload_info_response

    def fs_makedirs_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.mkdir_calls.append(payload)
        return self.mkdir_response

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]:
        self.getid_calls.append(payload)
        return self.getid_response


@pytest.mark.asyncio
async def test_drive115_health_client_probes_upload_and_root_dir_access() -> None:
    p115_client = StubP115Client()
    client = Drive115HealthClient(client_factory=lambda _cookie: p115_client)

    result = await client.probe("UID=alice", "/EmbyCache/alice")

    assert result == DriveHealthResult(ok=True, error_code=None, detail=None)
    assert p115_client.upload_info_calls == 1
    assert p115_client.user_key == "userkey-value"
    assert p115_client.mkdir_calls == [{"path": "/EmbyCache/alice"}]
    assert p115_client.getid_calls == []


@pytest.mark.asyncio
async def test_drive115_health_client_falls_back_to_dir_lookup_when_mkdir_has_no_id() -> None:
    p115_client = StubP115Client(
        mkdir_response={"state": True},
        getid_response={"state": True, "id": "dir-123"},
    )
    client = Drive115HealthClient(client_factory=lambda _cookie: p115_client)

    result = await client.probe("UID=alice", "/EmbyCache/alice")

    assert result == DriveHealthResult(ok=True, error_code=None, detail=None)
    assert p115_client.mkdir_calls == [{"path": "/EmbyCache/alice"}]
    assert p115_client.getid_calls == [{"path": "/EmbyCache/alice"}]


@pytest.mark.asyncio
async def test_drive115_health_client_marks_missing_user_key_as_invalid_cookie() -> None:
    p115_client = StubP115Client(upload_info_response={"state": False})
    client = Drive115HealthClient(client_factory=lambda _cookie: p115_client)

    result = await client.probe("UID=alice", "/EmbyCache/alice")

    assert result.ok is False
    assert result.error_code == "invalid_cookie"
    assert result.detail == "115 upload_info missing userkey"
    assert p115_client.mkdir_calls == []


@pytest.mark.asyncio
async def test_drive115_health_client_marks_missing_root_dir_as_unavailable() -> None:
    p115_client = StubP115Client(
        mkdir_response={"state": False},
        getid_response={"state": False},
    )
    client = Drive115HealthClient(client_factory=lambda _cookie: p115_client)

    result = await client.probe("UID=alice", "/EmbyCache/alice")

    assert result.ok is False
    assert result.error_code == "root_dir_unavailable"
    assert result.detail == "115 root dir unavailable: /EmbyCache/alice"
