from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from gateway.config import settings
from gateway.db import get_session
from gateway.integrations.openlist_client import OpenListClient
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver

router = APIRouter(prefix="/api/playback", tags=["playback"])


@router.get("/{media_id}")
async def resolve_playback(
    media_id: int,
    user_id: int,
    session: Session = Depends(get_session),
) -> dict[str, str | int]:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    resolver = PlaybackResolver(PlaybackService(total_budget_ms=2000), client)
    try:
        try:
            decision = await resolver.resolve(session, user_id=user_id, media_id=media_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
    finally:
        await client.aclose()

    return {
        "user_id": user_id,
        "media_id": media_id,
        "route": decision.route,
        "stream_url": decision.stream_url,
    }
