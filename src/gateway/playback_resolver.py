from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.integrations.openlist_client import OpenListClient
from gateway.models import MediaItem, PlaybackRecord, PoolObject, TransferRoute, User, UserDriveAccount
from gateway.playback import PlaybackDecision, PlaybackService


class PlaybackResolver:
    def __init__(self, playback_service: PlaybackService, openlist_client: OpenListClient) -> None:
        self._playback_service = playback_service
        self._openlist_client = openlist_client

    async def resolve(self, session: Session, *, user_id: int, media_id: int) -> PlaybackDecision:
        user = session.get(User, user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")

        media = session.get(MediaItem, media_id)
        if media is None:
            raise LookupError(f"media {media_id} not found")

        self_hit = session.scalar(
            select(PoolObject.target_path).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id == user_id,
            )
        )
        donor_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id != user_id,
            )
        )
        donor_available = donor_pool is not None and session.scalar(
            select(UserDriveAccount.id).where(
                UserDriveAccount.user_id == donor_pool.owner_user_id,
                UserDriveAccount.enabled.is_(True),
                UserDriveAccount.share_pool_enabled.is_(True),
            )
        ) is not None
        target_drive = session.scalar(
            select(UserDriveAccount).where(
                UserDriveAccount.user_id == user_id,
                UserDriveAccount.enabled.is_(True),
            )
        )

        source_copy_stream_url = None
        if target_drive is not None:
            source_copy_stream_url = (
                f"{target_drive.root_dir.rstrip('/')}/{PurePosixPath(media.source_path).name}"
            )

        stream_info = await self._openlist_client.get_stream_info(media.openlist_path)
        decision = self._playback_service.resolve(
            self_hit=self_hit,
            donor_available=donor_available,
            source_copy_supported=target_drive is not None,
            source_stream_url=stream_info.raw_url,
            pool_stream_url=donor_pool.target_path if donor_pool is not None else None,
            source_copy_stream_url=source_copy_stream_url,
            elapsed_ms=0,
        )

        session.add(
            PlaybackRecord(
                user_id=user_id,
                media_id=media_id,
                route=TransferRoute(decision.route),
                success=True,
                latency_ms=0,
            )
        )
        session.commit()
        return decision
