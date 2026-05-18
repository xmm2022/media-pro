from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.api.admin import summarize_routes
from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
from gateway.config import Settings
from gateway.integrations.openlist_client import OpenListClient
from gateway.integrations.rapid_copy_client import RapidCopyClient
from gateway.models import MediaItem, PlaybackRecord, User, UserDriveAccount
from gateway.playback import PlaybackService
from gateway.playback_resolver import PlaybackResolver
from gateway.script_inputs import build_rapid_copy_probe
from gateway.security import CookieCipher


async def run_real_integration_probe(
    session: Session,
    *,
    app_settings: Settings,
    openlist_client: OpenListClient,
    rapid_copy_client: RapidCopyClient,
) -> dict[str, object]:
    probe = build_rapid_copy_probe(app_settings)
    probe_user = session.scalar(select(User).where(User.username == "probe-user"))
    if probe_user is None:
        probe_user = User(username="probe-user", status="active")
        session.add(probe_user)
        session.flush()

    drive = session.scalar(
        select(UserDriveAccount).where(UserDriveAccount.user_id == probe_user.id)
    )
    if drive is None:
        drive = UserDriveAccount(
            user_id=probe_user.id,
            drive_type="115",
            cookie_encrypted=CookieCipher(app_settings.cookie_secret).encrypt(
                app_settings.rapid_copy_target_cookie
            ),
            root_dir=str(PurePosixPath(app_settings.rapid_copy_target_path).parent),
            share_pool_enabled=True,
        )
        session.add(drive)

    sync_summary = await CatalogSyncService(CatalogService(), openlist_client).sync_root(
        session,
        app_settings.catalog_root_path,
    )
    media_item = session.scalar(
        select(MediaItem).where(MediaItem.openlist_path == app_settings.openlist_probe_path)
    )
    if media_item is None:
        raise LookupError(f"media not synced for {app_settings.openlist_probe_path}")

    playback = await PlaybackResolver(PlaybackService(), openlist_client).resolve(
        session,
        user_id=probe_user.id,
        media_id=media_item.id,
    )
    copy_result = await rapid_copy_client.copy(
        probe.donor_cookie,
        probe.target_cookie,
        probe.source_path,
        probe.target_path,
    )
    routes = session.scalars(select(PlaybackRecord.route)).all()
    normalized_routes = [
        route.value if hasattr(route, "value") else str(route) for route in routes
    ]
    return {
        "sync": {"created": sync_summary.created, "updated": sync_summary.updated},
        "playback": {"route": playback.route, "stream_url": playback.stream_url},
        "rapid_copy": {
            "ok": copy_result.ok,
            "error_code": copy_result.error_code,
        },
        "stats": summarize_routes(normalized_routes),
    }
