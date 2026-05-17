from fastapi import APIRouter

from gateway.playback import PlaybackService

router = APIRouter(prefix="/api/playback", tags=["playback"])


@router.get("/{media_id}")
def resolve_playback(media_id: int) -> dict[str, str | int]:
    service = PlaybackService()
    decision = service.resolve(
        self_hit=None,
        donor_available=False,
        source_copy_supported=False,
        source_stream_url=f"https://openlist.local/media/{media_id}.mkv",
    )
    return {"media_id": media_id, "route": decision.route, "stream_url": decision.stream_url}
