from dataclasses import dataclass

import httpx


@dataclass(frozen=True, slots=True)
class PoolCopyRequest:
    donor_cookie: str
    target_cookie: str
    source_path: str
    target_path: str


@dataclass(frozen=True, slots=True)
class SourceObjectRef:
    openlist_path: str
    source_path: str | None = None
    source_file_id: str | None = None
    fingerprint: str | None = None

    def preferred_path(self) -> str:
        if self.openlist_path:
            return self.openlist_path
        if self.source_path:
            return self.source_path
        raise ValueError("source object reference is missing usable path")


@dataclass(frozen=True, slots=True)
class SourceCopyRequest:
    target_cookie: str
    source: SourceObjectRef
    target_path: str


@dataclass(slots=True)
class RapidCopyResult:
    ok: bool
    error_code: str | None
    target_path: str | None = None
    detail: str | None = None


class RapidCopyClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=2.0)

    async def copy_from_pool(self, request: PoolCopyRequest) -> RapidCopyResult:
        payload = {
            "donor_cookie": request.donor_cookie,
            "target_cookie": request.target_cookie,
            "source_path": request.source_path,
            "target_path": request.target_path,
        }
        return await self._post_copy(payload, fallback_target_path=request.target_path)

    async def copy_from_source(self, request: SourceCopyRequest) -> RapidCopyResult:
        payload = {
            "target_cookie": request.target_cookie,
            "source_path": request.source.preferred_path(),
            "target_path": request.target_path,
        }
        return await self._post_copy(payload, fallback_target_path=request.target_path)

    async def copy(
        self,
        donor_cookie: str | None,
        target_cookie: str,
        source_path: str,
        target_path: str,
    ) -> RapidCopyResult:
        if donor_cookie:
            return await self.copy_from_pool(
                PoolCopyRequest(
                    donor_cookie=donor_cookie,
                    target_cookie=target_cookie,
                    source_path=source_path,
                    target_path=target_path,
                )
            )
        return await self.copy_from_source(
            SourceCopyRequest(
                target_cookie=target_cookie,
                source=SourceObjectRef(
                    openlist_path=source_path,
                    source_path=source_path,
                ),
                target_path=target_path,
            )
        )

    async def _post_copy(
        self,
        payload: dict[str, str],
        *,
        fallback_target_path: str,
    ) -> RapidCopyResult:
        try:
            response = await self._client.post("/copy", json=payload)
        except httpx.TimeoutException as exc:
            return RapidCopyResult(ok=False, error_code="timeout", detail=str(exc))
        except httpx.HTTPError as exc:
            return RapidCopyResult(ok=False, error_code="unreachable", detail=str(exc))
        if response.status_code >= 400:
            return RapidCopyResult(
                ok=False,
                error_code=self._extract_error_code(response),
                detail=response.text,
            )
        return RapidCopyResult(
            ok=True,
            error_code=None,
            target_path=response.json().get("target_path", fallback_target_path),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _extract_error_code(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return f"http_{response.status_code}"
        error = data.get("error")
        if isinstance(error, str) and error:
            return error
        return f"http_{response.status_code}"
