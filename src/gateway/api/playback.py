from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from gateway.config import settings
from gateway.db import get_session
from gateway.integrations.drive115_health_client import Drive115HealthClient
from gateway.integrations.drive115_stream_client import Drive115StreamClient
from gateway.integrations.openlist_admin_client import OpenListAdminClient
from gateway.integrations.openlist_client import OpenListClient
from gateway.integrations.openlist_copy_strategy import OpenListCopyStrategy
from gateway.integrations.pool_copy_115_client import PoolCopy115Client
from gateway.integrations.rapid_copy_115_strategy import Rapid115Strategy
from gateway.integrations.rapid_copy_strategy import RapidCopyStrategyRegistry
from gateway.integrations.source_copy_115_client import SourceCopy115Client
from gateway.playback import PlaybackDecision, PlaybackService
from gateway.playback_resolver import PlaybackResolver

router = APIRouter(prefix="/api/playback", tags=["playback"])
PROXY_RESPONSE_HEADERS = {
    "accept-ranges",
    "cache-control",
    "content-disposition",
    "content-length",
    "content-range",
    "etag",
    "expires",
    "last-modified",
}


@router.get("/{media_id}")
async def resolve_playback(
    media_id: int,
    user_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    stream_token = request.app.state.playback_token_cipher.issue(user_id=user_id, media_id=media_id)
    decision = await _resolve_playback_decision(
        media_id=media_id,
        user_id=user_id,
        request=request,
        session=session,
    )
    return {
        "user_id": user_id,
        "media_id": media_id,
        "route": decision.route,
        "stream_url": str(request.url_for("stream_playback", media_id=media_id).include_query_params(token=stream_token)),
        "upstream_stream_url": decision.stream_url,
        "upstream_stream_headers": decision.stream_headers,
    }


@router.api_route("/{media_id}/stream", methods=["GET", "HEAD"])
async def stream_playback(
    media_id: int,
    request: Request,
    user_id: int | None = None,
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> Response:
    resolved_user_id = _resolve_stream_user_id(
        media_id=media_id,
        user_id=user_id,
        token=token,
        request=request,
    )
    decision = await _resolve_playback_decision(
        media_id=media_id,
        user_id=resolved_user_id,
        request=request,
        session=session,
    )
    upstream_client = httpx.AsyncClient(follow_redirects=True, timeout=None)
    try:
        upstream_response = await upstream_client.send(
            upstream_client.build_request(
                request.method,
                decision.stream_url,
                headers=_build_upstream_request_headers(
                    stream_headers=decision.stream_headers,
                    range_header=request.headers.get("range"),
                    if_range_header=request.headers.get("if-range"),
                ),
            ),
            stream=request.method != "HEAD",
        )
    except httpx.HTTPError as exc:
        await upstream_client.aclose()
        raise HTTPException(status_code=502, detail=f"upstream stream failed: {exc}") from None

    response_headers = _build_proxy_response_headers(upstream_response.headers)
    media_type = upstream_response.headers.get("content-type")
    if request.method == "HEAD":
        status_code = upstream_response.status_code
        await upstream_response.aclose()
        await upstream_client.aclose()
        return Response(status_code=status_code, headers=response_headers, media_type=media_type)

    return StreamingResponse(
        _stream_upstream_response(upstream_response, upstream_client),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=media_type,
    )


async def _resolve_playback_decision(
    *,
    media_id: int,
    user_id: int,
    request: Request,
    session: Session,
) -> PlaybackDecision:
    openlist_client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    pool_copy_client = PoolCopy115Client()
    source_copy_client = SourceCopy115Client(openlist_client)
    drive_stream_client = Drive115StreamClient()
    registry = RapidCopyStrategyRegistry()
    registry.register(
        Rapid115Strategy(
            pool_copy_client=pool_copy_client,
            source_copy_client=source_copy_client,
            health_client=Drive115HealthClient(),
            cookie_cipher=request.app.state.cookie_cipher,
        )
    )
    if settings.openlist_admin_token:
        registry.register(
            OpenListCopyStrategy(
                admin_client=OpenListAdminClient(
                    base_url=settings.openlist_base_url,
                    admin_token=settings.openlist_admin_token,
                ),
                drive_type="caiyun",
            )
        )
    resolver = PlaybackResolver(
        PlaybackService(total_budget_ms=2000),
        openlist_client,
        strategy_registry=registry,
        drive_stream_client=drive_stream_client,
        cookie_cipher=request.app.state.cookie_cipher,
    )
    try:
        try:
            return await resolver.resolve(session, user_id=user_id, media_id=media_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
    finally:
        await registry.aclose()
        await openlist_client.aclose()


def _resolve_stream_user_id(
    *,
    media_id: int,
    user_id: int | None,
    token: str | None,
    request: Request,
) -> int:
    if token:
        try:
            payload = request.app.state.playback_token_cipher.verify(token)
        except ValueError:
            raise HTTPException(status_code=403, detail="invalid playback token") from None
        if payload["media_id"] != media_id:
            raise HTTPException(status_code=403, detail="invalid playback token")
        return payload["user_id"]
    if user_id is None:
        raise HTTPException(status_code=422, detail="user_id or token is required")
    return user_id


def _build_upstream_request_headers(
    *,
    stream_headers: dict[str, str] | None,
    range_header: str | None,
    if_range_header: str | None,
) -> dict[str, str]:
    headers = {"accept-encoding": "identity"}
    if stream_headers:
        headers.update(stream_headers)
    if range_header:
        headers["range"] = range_header
    if if_range_header:
        headers["if-range"] = if_range_header
    return headers


def _build_proxy_response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() in PROXY_RESPONSE_HEADERS
    }


async def _stream_upstream_response(
    upstream_response: httpx.Response,
    upstream_client: httpx.AsyncClient,
) -> AsyncIterator[bytes]:
    try:
        async for chunk in upstream_response.aiter_raw():
            yield chunk
    finally:
        await upstream_response.aclose()
        await upstream_client.aclose()
