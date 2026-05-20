from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(slots=True)
class DriveHealthResult:
    ok: bool
    error_code: str | None
    detail: str | None = None


class OneOneFiveClient(Protocol):
    user_key: str

    def fs_makedirs_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def fs_dir_getid_app(self, payload: dict[str, object]) -> dict[str, object]: ...

    def upload_info(self) -> dict[str, object]: ...


class Drive115HealthClient:
    def __init__(
        self,
        *,
        client_factory: Callable[[str], OneOneFiveClient] | None = None,
    ) -> None:
        self._client_factory = client_factory or self._build_client

    async def probe(self, target_cookie: str, root_dir: str) -> DriveHealthResult:
        return await asyncio.to_thread(self._probe, target_cookie, root_dir)

    def _probe(self, target_cookie: str, root_dir: str) -> DriveHealthResult:
        try:
            client = self._client_factory(target_cookie)
            upload_info = client.upload_info()
            user_key = self._extract_user_key(upload_info)
            if not user_key:
                return DriveHealthResult(
                    ok=False,
                    error_code="invalid_cookie",
                    detail="115 upload_info missing userkey",
                )
            setattr(client, "user_key", user_key)

            if root_dir in {"", ".", "/"}:
                return DriveHealthResult(ok=True, error_code=None)

            mkdir_response = client.fs_makedirs_app({"path": root_dir})
            if self._extract_dir_id(mkdir_response):
                return DriveHealthResult(ok=True, error_code=None)

            getid_response = client.fs_dir_getid_app({"path": root_dir})
            if self._extract_dir_id(getid_response):
                return DriveHealthResult(ok=True, error_code=None)

            return DriveHealthResult(
                ok=False,
                error_code="root_dir_unavailable",
                detail=f"115 root dir unavailable: {root_dir}",
            )
        except Exception as exc:  # pragma: no cover - defensive mapping
            return DriveHealthResult(
                ok=False,
                error_code="probe_failed",
                detail=str(exc),
            )

    def _extract_dir_id(self, response: dict[str, object]) -> str | None:
        for key in ("id", "cid", "file_id"):
            value = response.get(key)
            if value is not None:
                return str(value)

        data = response.get("data")
        if isinstance(data, dict):
            for key in ("id", "cid", "file_id"):
                value = data.get(key)
                if value is not None:
                    return str(value)
        return None

    def _extract_user_key(self, response: dict[str, object]) -> str | None:
        value = response.get("userkey")
        if isinstance(value, str) and value:
            return value

        data = response.get("data")
        if isinstance(data, dict):
            value = data.get("userkey")
            if isinstance(value, str) and value:
                return value
        return None

    def _build_client(self, target_cookie: str) -> OneOneFiveClient:
        from p115client import P115Client

        return P115Client(target_cookie, check_for_relogin=False)
