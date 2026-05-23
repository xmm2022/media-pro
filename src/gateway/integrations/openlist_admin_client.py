"""OpenList admin/storage and fs operation wrapper."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class StorageRecord:
    id: int
    mount_path: str
    driver: str
    addition: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CopyResult:
    ok: bool
    task_id: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FsItem:
    name: str
    is_dir: bool
    size: int


class OpenListAdminError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"openlist admin error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class OpenListAdminClient:
    def __init__(self, *, base_url: str, admin_token: str, timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": admin_token} if admin_token else {},
            timeout=timeout,
        )

    async def list_storages(self) -> list[StorageRecord]:
        payloads = await self._list_storage_payloads()
        return [self._parse_storage(item) for item in payloads]

    async def create_storage(
        self,
        *,
        driver: str,
        mount_path: str,
        addition: dict[str, Any],
    ) -> int:
        response = await self._client.post(
            "/api/admin/storage/create",
            json={
                "mount_path": mount_path,
                "driver": driver,
                "addition": json.dumps(addition),
            },
        )
        data = self._extract_data(response)
        storage_id = data.get("id")
        if not isinstance(storage_id, int):
            raise OpenListAdminError(
                response.status_code,
                f"create returned no id: {response.text[:200]}",
            )
        return storage_id

    async def update_storage(self, storage_id: int, *, addition: dict[str, Any]) -> None:
        storage = await self._get_storage_payload(storage_id)
        storage["addition"] = json.dumps(addition)
        response = await self._client.post("/api/admin/storage/update", json=storage)
        self._extract_data(response)

    async def delete_storage(self, storage_id: int) -> None:
        response = await self._client.post(
            "/api/admin/storage/delete",
            params={"id": str(storage_id)},
        )
        self._extract_data(response)

    async def delete_storage_by_mount(self, mount_path: str) -> None:
        storages = await self.list_storages()
        match = next((storage for storage in storages if storage.mount_path == mount_path), None)
        if match is None:
            raise OpenListAdminError(404, f"storage with mount_path {mount_path} not found")
        await self.delete_storage(match.id)

    async def fs_copy(self, *, src_dir: str, dst_dir: str, names: list[str]) -> CopyResult:
        response = await self._client.post(
            "/api/fs/copy",
            json={"src_dir": src_dir, "dst_dir": dst_dir, "names": names},
        )
        try:
            data = self._extract_data(response)
        except OpenListAdminError as exc:
            return CopyResult(ok=False, error=exc.message)
        return CopyResult(ok=True, task_id=self._optional_str(data.get("task_id")))

    async def fs_list(self, mount_path: str) -> list[FsItem]:
        response = await self._client.post(
            "/api/fs/list",
            json={"path": mount_path, "password": ""},
        )
        data = self._extract_data(response)
        items = data.get("content") or []
        return [
            FsItem(
                name=str(item.get("name", "")),
                is_dir=bool(item.get("is_dir", False)),
                size=self._to_int(item.get("size")) or 0,
            )
            for item in items
            if isinstance(item, dict)
        ]

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _list_storage_payloads(self) -> list[dict[str, Any]]:
        response = await self._client.get("/api/admin/storage/list")
        data = self._extract_data(response)
        items = data.get("content") or []
        return [dict(item) for item in items if isinstance(item, dict)]

    async def _get_storage_payload(self, storage_id: int) -> dict[str, Any]:
        storages = await self._list_storage_payloads()
        match = next((storage for storage in storages if storage.get("id") == storage_id), None)
        if match is None:
            raise OpenListAdminError(404, f"storage with id {storage_id} not found")
        return match

    def _extract_data(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise OpenListAdminError(response.status_code, self._extract_message(response))
        try:
            body = response.json()
        except ValueError as exc:
            raise OpenListAdminError(response.status_code, f"invalid json: {exc}") from exc

        code = body.get("code")
        if isinstance(code, int) and code != 200:
            raise OpenListAdminError(code, str(body.get("message") or "openlist error"))

        data = body.get("data")
        if isinstance(data, dict):
            return data
        return {}

    def _extract_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text[:200]
        return str(body.get("message") or body.get("error") or response.text[:200])

    def _parse_storage(self, item: dict[str, Any]) -> StorageRecord:
        return StorageRecord(
            id=self._to_int(item.get("id")) or 0,
            mount_path=str(item.get("mount_path", "")),
            driver=str(item.get("driver", "")),
            addition=self._parse_addition(item.get("addition")),
        )

    def _parse_addition(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if not isinstance(value, str) or not value:
            return {}
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(decoded) if isinstance(decoded, dict) else {}

    def _optional_str(self, value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    def _to_int(self, value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None
