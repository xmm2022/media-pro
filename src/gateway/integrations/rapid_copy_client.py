from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class RapidCopyResult:
    ok: bool
    error_code: str | None
    target_path: str | None = None
    detail: str | None = None


class RapidCopyClient:
    _STATUS_MAP = {
        400: "invalid_request",
        401: "permission_denied",
        403: "permission_denied",
        404: "endpoint_not_found",
        409: "target_conflict",
        422: "invalid_request",
    }

    def __init__(self, base_url: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=2.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _json_payload(self, response: httpx.Response) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    async def copy(
        self,
        donor_cookie: str,
        target_cookie: str,
        source_path: str,
        target_path: str,
    ) -> RapidCopyResult:
        try:
            response = await self._client.post(
                "/copy",
                json={
                    "donor_cookie": donor_cookie,
                    "target_cookie": target_cookie,
                    "source_path": source_path,
                    "target_path": target_path,
                },
            )
        except httpx.HTTPError as exc:
            return RapidCopyResult(
                ok=False,
                error_code="service_unreachable",
                detail=str(exc),
            )

        payload = self._json_payload(response)
        if response.status_code >= 400:
            if "error" in payload:
                mapped_error = payload["error"]
            else:
                mapped_error = self._STATUS_MAP.get(
                    response.status_code,
                    "upstream_error",
                )
            detail = payload.get("detail")
            return RapidCopyResult(
                ok=False,
                error_code=str(mapped_error),
                detail=str(detail) if detail else None,
            )

        if "target_path" not in payload:
            return RapidCopyResult(
                ok=False,
                error_code="upstream_error",
                detail="missing target_path in rapid-copy response",
            )

        return RapidCopyResult(
            ok=True,
            error_code=None,
            target_path=str(payload["target_path"]),
        )
