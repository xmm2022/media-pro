from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class RapidCopyResult:
    ok: bool
    error_code: str | None
    target_path: str | None = None


class RapidCopyClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=2.0)

    async def copy(
        self,
        donor_cookie: str,
        target_cookie: str,
        source_path: str,
        target_path: str,
    ) -> RapidCopyResult:
        response = await self._client.post(
            "/copy",
            json={
                "donor_cookie": donor_cookie,
                "target_cookie": target_cookie,
                "source_path": source_path,
                "target_path": target_path,
            },
        )
        if response.status_code >= 400:
            return RapidCopyResult(ok=False, error_code=response.json()["error"])
        return RapidCopyResult(
            ok=True,
            error_code=None,
            target_path=response.json()["target_path"],
        )
