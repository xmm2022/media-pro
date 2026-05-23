from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gateway.catalog import CatalogService
from gateway.catalog_sync import CatalogSyncService
from gateway.config import settings
from gateway.db import get_session
from gateway.integrations.drive115_health_client import Drive115HealthClient, DriveHealthResult
from gateway.integrations.openlist_admin_client import OpenListAdminClient, OpenListAdminError
from gateway.integrations.openlist_client import OpenListClient
from gateway.models import PlaybackRecord, PoolObject, PoolObjectStatus, User, UserDriveAccount
from gateway.schemas import (
    CatalogSyncRequest,
    CatalogSyncResponse,
    AdminOverviewRead,
    DriveAccountBulkActionRequest,
    DriveAccountBulkActionResponse,
    DriveAccountCreate,
    DriveAccountDeleteResponse,
    DriveProbeBulkResponse,
    DriveProbeRead,
    DriveAccountRead,
    DriveStatsRead,
    DriveAccountUpdate,
    PoolObjectBulkActionRequest,
    PoolObjectBulkActionResponse,
    PoolObjectRead,
    PoolObjectStatsRead,
    UserCreate,
    UserRead,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def admin_stats(session: Session = Depends(get_session)) -> dict[str, int]:
    routes = session.scalars(select(PlaybackRecord.route)).all()
    normalized_routes = [
        route.value if hasattr(route, "value") else str(route) for route in routes
    ]
    return summarize_routes(normalized_routes)


@router.get("/overview", response_model=AdminOverviewRead)
def admin_overview(
    request: Request,
    drive_limit: int = Query(default=10, ge=0, le=100),
    pool_object_limit: int = Query(default=10, ge=0, le=100),
    stale_probe_after_hours: int = Query(default=24, ge=1, le=720),
    session: Session = Depends(get_session),
) -> AdminOverviewRead:
    routes = session.scalars(select(PlaybackRecord.route)).all()
    drives = session.scalars(_build_drive_select_statement()).all()
    pool_objects = session.scalars(_build_pool_object_select_statement()).all()
    normalized_routes = [
        route.value if hasattr(route, "value") else str(route) for route in routes
    ]
    return AdminOverviewRead(
        routes=summarize_routes(normalized_routes),
        drives=_build_drive_overview_section(
            drives,
            request=request,
            limit=drive_limit,
            stale_probe_after_hours=stale_probe_after_hours,
        ),
        pool_objects=_build_pool_object_overview_section(
            pool_objects,
            limit=pool_object_limit,
        ),
    )


@router.get("/drives/stats", response_model=DriveStatsRead)
def admin_drive_stats(session: Session = Depends(get_session)) -> DriveStatsRead:
    drives = session.scalars(select(UserDriveAccount)).all()
    return DriveStatsRead.model_validate(summarize_drives(drives))


@router.get("/pool-objects/stats", response_model=PoolObjectStatsRead)
def admin_pool_object_stats(session: Session = Depends(get_session)) -> PoolObjectStatsRead:
    pool_objects = session.scalars(select(PoolObject)).all()
    return PoolObjectStatsRead.model_validate(summarize_pool_objects(pool_objects))


def summarize_routes(routes: list[str]) -> dict[str, int]:
    summary = {"self": 0, "pool": 0, "source_copy": 0, "source_stream": 0}
    for route in routes:
        if route in summary:
            summary[route] += 1
    return summary


def summarize_pool_object_statuses(statuses: list[str]) -> dict[str, int]:
    summary = {pool_status.value: 0 for pool_status in PoolObjectStatus}
    for status_name in statuses:
        if status_name in summary:
            summary[status_name] += 1
    return summary


def summarize_drives(drives: list[UserDriveAccount]) -> dict[str, object]:
    by_drive_type: dict[str, int] = {}
    by_health_status: dict[str, int] = {}
    for drive in drives:
        by_drive_type[drive.drive_type] = by_drive_type.get(drive.drive_type, 0) + 1
        by_health_status[drive.health_status] = by_health_status.get(drive.health_status, 0) + 1

    return {
        "total": len(drives),
        "users": len({drive.user_id for drive in drives}),
        "enabled": sum(1 for drive in drives if drive.enabled),
        "disabled": sum(1 for drive in drives if not drive.enabled),
        "share_pool_enabled": sum(1 for drive in drives if drive.share_pool_enabled),
        "by_drive_type": by_drive_type,
        "by_health_status": by_health_status,
    }


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def summarize_pool_objects(
    pool_objects: list[PoolObject],
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    by_drive_type: dict[str, int] = {}
    normalized_now = now or datetime.now(timezone.utc)
    cooldown_active = 0
    cooldown_expired = 0
    for pool_object in pool_objects:
        by_drive_type[pool_object.drive_type] = by_drive_type.get(pool_object.drive_type, 0) + 1
        if pool_object.status != PoolObjectStatus.COOLDOWN:
            continue
        cooldown_until = _normalize_timestamp(pool_object.cooldown_until)
        if cooldown_until is None or cooldown_until > normalized_now:
            cooldown_active += 1
        else:
            cooldown_expired += 1

    return {
        "total": len(pool_objects),
        "owners": len({pool_object.owner_user_id for pool_object in pool_objects}),
        "media_items": len({pool_object.media_id for pool_object in pool_objects}),
        "by_status": summarize_pool_object_statuses(
            [
                pool_object.status.value
                if hasattr(pool_object.status, "value")
                else str(pool_object.status)
                for pool_object in pool_objects
            ]
        ),
        "by_drive_type": by_drive_type,
        "cooldown_active": cooldown_active,
        "cooldown_expired": cooldown_expired,
    }


def _drive_needs_attention(drive: UserDriveAccount) -> bool:
    return not drive.enabled or drive.health_status != "healthy"


def _pool_object_needs_attention(pool_object: PoolObject) -> bool:
    return pool_object.status != PoolObjectStatus.READY


def _build_drive_overview_section(
    drives: list[UserDriveAccount],
    *,
    request: Request,
    limit: int,
    stale_probe_after_hours: int,
):
    attention_drives = [drive for drive in drives if _drive_needs_attention(drive)]
    return {
        "stats": summarize_drives(drives),
        "attention_total": len(attention_drives),
        "probe_error_distribution": summarize_drive_probe_errors(drives),
        "stale_probe_count": count_stale_drive_probes(
            drives,
            stale_probe_after_hours=stale_probe_after_hours,
        ),
        "stale_probe_threshold_hours": stale_probe_after_hours,
        "items": [
            _build_drive_account_read(drive, request=request)
            for drive in attention_drives[:limit]
        ],
    }


def _build_pool_object_overview_section(
    pool_objects: list[PoolObject],
    *,
    limit: int,
):
    attention_pool_objects = [
        pool_object
        for pool_object in pool_objects
        if _pool_object_needs_attention(pool_object)
    ]
    return {
        "stats": summarize_pool_objects(pool_objects),
        "attention_total": len(attention_pool_objects),
        "items": [
            PoolObjectRead.model_validate(pool_object)
            for pool_object in attention_pool_objects[:limit]
        ],
    }


def _successful_drive_probe() -> DriveHealthResult:
    return DriveHealthResult(ok=True, error_code=None)


def summarize_drive_probe_errors(drives: list[UserDriveAccount]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for drive in drives:
        if drive.last_checked_at is None:
            continue
        if drive.health_status == "healthy":
            continue
        summary[drive.health_status] = summary.get(drive.health_status, 0) + 1
    return summary


def count_stale_drive_probes(
    drives: list[UserDriveAccount],
    *,
    stale_probe_after_hours: int,
    now: datetime | None = None,
) -> int:
    normalized_now = now or datetime.now(timezone.utc)
    stale_cutoff = normalized_now - timedelta(hours=stale_probe_after_hours)
    stale_count = 0
    for drive in drives:
        last_checked_at = _normalize_timestamp(drive.last_checked_at)
        if last_checked_at is None or last_checked_at < stale_cutoff:
            stale_count += 1
    return stale_count


def _finalize_drive_probe(
    drive: UserDriveAccount,
    *,
    probe_result: DriveHealthResult,
) -> None:
    drive.health_status = "healthy" if probe_result.ok else (probe_result.error_code or "probe_failed")
    drive.last_checked_at = datetime.now(timezone.utc)


async def _probe_alist_drive(root_dir: str) -> DriveHealthResult:
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    try:
        await client.list_catalog(root_dir)
        return _successful_drive_probe()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return DriveHealthResult(
                ok=False,
                error_code="root_dir_unavailable",
                detail=f"OpenList root dir unavailable: {root_dir}",
            )
        if exc.response.status_code in {401, 403}:
            return DriveHealthResult(
                ok=False,
                error_code="openlist_auth_failed",
                detail=str(exc),
            )
        return DriveHealthResult(
            ok=False,
            error_code="openlist_http_error",
            detail=str(exc),
        )
    except httpx.HTTPError as exc:
        return DriveHealthResult(
            ok=False,
            error_code="probe_failed",
            detail=str(exc),
        )
    finally:
        await client.aclose()


async def _probe_drive(
    request: Request,
    drive: UserDriveAccount,
) -> DriveHealthResult:
    if drive.drive_type == "115":
        cookie = request.app.state.cookie_cipher.decrypt(drive.cookie_encrypted)
        return await Drive115HealthClient().probe(cookie, drive.root_dir)
    if drive.drive_type == "alist":
        return await _probe_alist_drive(drive.root_dir)
    if drive.drive_type == "caiyun":
        return await _probe_caiyun_drive(drive)
    return DriveHealthResult(
        ok=False,
        error_code="unsupported_drive_type",
        detail=f"Drive type is not probeable: {drive.drive_type}",
    )


async def _probe_caiyun_drive(drive: UserDriveAccount) -> DriveHealthResult:
    if not drive.openlist_mount_path:
        return DriveHealthResult(
            ok=False,
            error_code="mount_missing",
            detail="drive has no mount_path",
        )
    admin_client = _build_openlist_admin_client()
    try:
        try:
            await admin_client.fs_list(drive.openlist_mount_path)
        except OpenListAdminError as exc:
            if exc.status_code == 404:
                return DriveHealthResult(ok=False, error_code="mount_missing", detail=exc.message)
            if exc.status_code in {401, 403}:
                return DriveHealthResult(ok=False, error_code="invalid_token", detail=exc.message)
            return DriveHealthResult(ok=False, error_code="openlist_http_error", detail=exc.message)
        except httpx.HTTPError as exc:
            return DriveHealthResult(ok=False, error_code="openlist_admin_failed", detail=str(exc))
    finally:
        await admin_client.aclose()
    return _successful_drive_probe()


def _build_drive_probe_read(
    *,
    probe_result: DriveHealthResult,
    drive: UserDriveAccount,
    request: Request,
) -> DriveProbeRead:
    return DriveProbeRead(
        ok=probe_result.ok,
        error_code=probe_result.error_code,
        detail=probe_result.detail,
        drive=_build_drive_account_read(drive, request=request),
    )


def _build_pool_object_select_statement(
    *,
    ids: list[int] | None = None,
    statuses: list[PoolObjectStatus] | None = None,
    owner_user_id: int | None = None,
    media_id: int | None = None,
):
    statement = select(PoolObject).order_by(
        PoolObject.owner_user_id,
        PoolObject.media_id,
        PoolObject.id,
    )
    if ids:
        statement = statement.where(PoolObject.id.in_(ids))
    if statuses:
        statement = statement.where(PoolObject.status.in_(statuses))
    if owner_user_id is not None:
        statement = statement.where(PoolObject.owner_user_id == owner_user_id)
    if media_id is not None:
        statement = statement.where(PoolObject.media_id == media_id)
    return statement


def _build_drive_select_statement(
    *,
    ids: list[int] | None = None,
    user_id: int | None = None,
    drive_type: str | None = None,
    enabled: bool | None = None,
    share_pool_enabled: bool | None = None,
):
    statement = select(UserDriveAccount).order_by(
        UserDriveAccount.user_id,
        UserDriveAccount.id,
    )
    if ids:
        statement = statement.where(UserDriveAccount.id.in_(ids))
    if user_id is not None:
        statement = statement.where(UserDriveAccount.user_id == user_id)
    if drive_type is not None:
        statement = statement.where(UserDriveAccount.drive_type == drive_type)
    if enabled is not None:
        statement = statement.where(UserDriveAccount.enabled.is_(enabled))
    if share_pool_enabled is not None:
        statement = statement.where(UserDriveAccount.share_pool_enabled.is_(share_pool_enabled))
    return statement


def _mark_pool_object_ready(pool_object: PoolObject) -> None:
    pool_object.status = PoolObjectStatus.READY
    pool_object.failure_count = 0
    pool_object.cooldown_until = None


def _mark_pool_object_disabled(pool_object: PoolObject) -> None:
    pool_object.status = PoolObjectStatus.DISABLED
    pool_object.cooldown_until = None


def _path_is_within_root(target_path: str, root_dir: str) -> bool:
    target = PurePosixPath(target_path)
    root = PurePosixPath(root_dir)
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _load_drive_pool_objects(
    session: Session,
    *,
    drive: UserDriveAccount,
    root_dirs: list[str],
    statuses: list[PoolObjectStatus] | None = None,
) -> list[PoolObject]:
    statement = (
        select(PoolObject)
        .where(
            PoolObject.owner_user_id == drive.user_id,
            PoolObject.drive_type == drive.drive_type,
        )
        .order_by(PoolObject.id)
    )
    if statuses:
        statement = statement.where(PoolObject.status.in_(statuses))
    pool_objects = session.scalars(statement).all()
    return [
        pool_object
        for pool_object in pool_objects
        if any(_path_is_within_root(pool_object.target_path, root_dir) for root_dir in root_dirs)
    ]


def _build_drive_account_read(
    drive: UserDriveAccount,
    *,
    request: Request,
) -> DriveAccountRead:
    cookie_preview = None
    if drive.cookie_encrypted is not None:
        cookie = request.app.state.cookie_cipher.decrypt(drive.cookie_encrypted)
        cookie_preview = f"{cookie[:5]}..."
    return DriveAccountRead(
        id=drive.id,
        user_id=drive.user_id,
        drive_type=drive.drive_type,
        root_dir=drive.root_dir,
        enabled=drive.enabled,
        share_pool_enabled=drive.share_pool_enabled,
        health_status=drive.health_status,
        last_checked_at=drive.last_checked_at,
        cookie_preview=cookie_preview,
        openlist_mount_path=drive.openlist_mount_path,
    )


def _disable_drive_pool_objects(
    session: Session,
    *,
    drive: UserDriveAccount,
    root_dirs: list[str],
) -> int:
    updated = 0
    for pool_object in _load_drive_pool_objects(
        session,
        drive=drive,
        root_dirs=root_dirs,
    ):
        if pool_object.status == PoolObjectStatus.DISABLED:
            continue
        _mark_pool_object_disabled(pool_object)
        updated += 1
    return updated


def _enable_drive_pool_objects(
    session: Session,
    *,
    drive: UserDriveAccount,
    root_dir: str,
) -> int:
    updated = 0
    for pool_object in _load_drive_pool_objects(
        session,
        drive=drive,
        root_dirs=[root_dir],
        statuses=[PoolObjectStatus.DISABLED],
    ):
        _mark_pool_object_ready(pool_object)
        updated += 1
    return updated


def _load_pool_objects_for_drives(
    session: Session,
    *,
    drives: list[UserDriveAccount],
    statuses: list[PoolObjectStatus] | None = None,
) -> list[PoolObject]:
    pool_objects: list[PoolObject] = []
    seen_ids: set[int] = set()
    for drive in drives:
        for pool_object in _load_drive_pool_objects(
            session,
            drive=drive,
            root_dirs=[drive.root_dir],
            statuses=statuses,
        ):
            if pool_object.id in seen_ids:
                continue
            seen_ids.add(pool_object.id)
            pool_objects.append(pool_object)
    return pool_objects


def _disable_selected_drives_pool_objects(
    session: Session,
    *,
    drives: list[UserDriveAccount],
) -> int:
    updated = 0
    for pool_object in _load_pool_objects_for_drives(session, drives=drives):
        if pool_object.status == PoolObjectStatus.DISABLED:
            continue
        _mark_pool_object_disabled(pool_object)
        updated += 1
    return updated


def _enable_selected_drives_pool_objects(
    session: Session,
    *,
    drives: list[UserDriveAccount],
) -> int:
    updated = 0
    for pool_object in _load_pool_objects_for_drives(
        session,
        drives=drives,
        statuses=[PoolObjectStatus.DISABLED],
    ):
        _mark_pool_object_ready(pool_object)
        updated += 1
    return updated


@router.get("/pool-objects", response_model=list[PoolObjectRead])
def list_pool_objects(
    status: PoolObjectStatus | None = None,
    owner_user_id: int | None = None,
    media_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[PoolObjectRead]:
    pool_objects = session.scalars(
        _build_pool_object_select_statement(
            statuses=[status] if status is not None else None,
            owner_user_id=owner_user_id,
            media_id=media_id,
        )
    ).all()
    return [PoolObjectRead.model_validate(pool_object) for pool_object in pool_objects]


@router.post("/pool-objects/recover", response_model=PoolObjectBulkActionResponse)
def recover_pool_objects(
    payload: PoolObjectBulkActionRequest,
    session: Session = Depends(get_session),
) -> PoolObjectBulkActionResponse:
    recoverable_statuses = payload.statuses or [
        PoolObjectStatus.COOLDOWN,
        PoolObjectStatus.STALE,
        PoolObjectStatus.SUSPECT,
    ]
    pool_objects = session.scalars(
        _build_pool_object_select_statement(
            ids=payload.ids,
            statuses=recoverable_statuses,
            owner_user_id=payload.owner_user_id,
            media_id=payload.media_id,
        )
    ).all()
    for pool_object in pool_objects:
        _mark_pool_object_ready(pool_object)
    session.commit()
    for pool_object in pool_objects:
        session.refresh(pool_object)
    return PoolObjectBulkActionResponse(
        matched=len(pool_objects),
        updated=len(pool_objects),
        pool_objects=[PoolObjectRead.model_validate(pool_object) for pool_object in pool_objects],
    )


@router.post("/pool-objects/disable", response_model=PoolObjectBulkActionResponse)
def disable_pool_objects(
    payload: PoolObjectBulkActionRequest,
    session: Session = Depends(get_session),
) -> PoolObjectBulkActionResponse:
    pool_objects = session.scalars(
        _build_pool_object_select_statement(
            ids=payload.ids,
            statuses=payload.statuses,
            owner_user_id=payload.owner_user_id,
            media_id=payload.media_id,
        )
    ).all()
    updated = 0
    for pool_object in pool_objects:
        if pool_object.status == PoolObjectStatus.DISABLED:
            continue
        _mark_pool_object_disabled(pool_object)
        updated += 1
    session.commit()
    for pool_object in pool_objects:
        session.refresh(pool_object)
    return PoolObjectBulkActionResponse(
        matched=len(pool_objects),
        updated=updated,
        pool_objects=[PoolObjectRead.model_validate(pool_object) for pool_object in pool_objects],
    )


@router.post("/pool-objects/enable", response_model=PoolObjectBulkActionResponse)
def enable_pool_objects(
    payload: PoolObjectBulkActionRequest,
    session: Session = Depends(get_session),
) -> PoolObjectBulkActionResponse:
    pool_objects = session.scalars(
        _build_pool_object_select_statement(
            ids=payload.ids,
            statuses=payload.statuses or [PoolObjectStatus.DISABLED],
            owner_user_id=payload.owner_user_id,
            media_id=payload.media_id,
        )
    ).all()
    for pool_object in pool_objects:
        _mark_pool_object_ready(pool_object)
    session.commit()
    for pool_object in pool_objects:
        session.refresh(pool_object)
    return PoolObjectBulkActionResponse(
        matched=len(pool_objects),
        updated=len(pool_objects),
        pool_objects=[PoolObjectRead.model_validate(pool_object) for pool_object in pool_objects],
    )


@router.post("/pool-objects/{pool_object_id}/recover", response_model=PoolObjectRead)
def recover_pool_object(
    pool_object_id: int,
    session: Session = Depends(get_session),
) -> PoolObjectRead:
    pool_object = session.get(PoolObject, pool_object_id)
    if pool_object is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pool object not found")

    _mark_pool_object_ready(pool_object)
    session.commit()
    session.refresh(pool_object)
    return PoolObjectRead.model_validate(pool_object)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> UserRead:
    user = User(username=payload.username, status=payload.status)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from None
    session.refresh(user)
    return UserRead.model_validate(user)


@router.get("/drives", response_model=list[DriveAccountRead])
def list_drives(
    request: Request,
    user_id: int | None = None,
    drive_type: str | None = None,
    enabled: bool | None = None,
    share_pool_enabled: bool | None = None,
    session: Session = Depends(get_session),
) -> list[DriveAccountRead]:
    drives = session.scalars(
        _build_drive_select_statement(
            user_id=user_id,
            drive_type=drive_type,
            enabled=enabled,
            share_pool_enabled=share_pool_enabled,
        )
    ).all()
    return [_build_drive_account_read(drive, request=request) for drive in drives]


@router.post("/drives", response_model=DriveAccountRead, status_code=status.HTTP_201_CREATED)
async def create_drive(
    payload: DriveAccountCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveAccountRead:
    if session.get(User, payload.user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.drive_type == "caiyun":
        return await _create_caiyun_drive(payload, request=request, session=session)

    drive = UserDriveAccount(
        user_id=payload.user_id,
        drive_type=payload.drive_type,
        cookie_encrypted=request.app.state.cookie_cipher.encrypt(payload.cookie or ""),
        root_dir=payload.root_dir,
        share_pool_enabled=payload.share_pool_enabled,
    )
    session.add(drive)
    session.commit()
    session.refresh(drive)
    return _build_drive_account_read(drive, request=request)


async def _create_caiyun_drive(
    payload: DriveAccountCreate,
    *,
    request: Request,
    session: Session,
) -> DriveAccountRead:
    mount_path = payload.mount_path or f"/caiyun-{payload.user_id}"
    assert payload.caiyun is not None
    admin_client = _build_openlist_admin_client()
    try:
        try:
            await admin_client.create_storage(
                driver="139Yun",
                mount_path=mount_path,
                addition=_build_caiyun_addition(payload.caiyun),
            )
        except OpenListAdminError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "openlist_admin_failed", "message": exc.message},
            ) from None
    finally:
        await admin_client.aclose()

    drive = UserDriveAccount(
        user_id=payload.user_id,
        drive_type="caiyun",
        cookie_encrypted=None,
        root_dir=payload.root_dir,
        share_pool_enabled=False,
        openlist_mount_path=mount_path,
    )
    session.add(drive)
    session.commit()
    session.refresh(drive)
    return _build_drive_account_read(drive, request=request)


def _build_caiyun_addition(credentials) -> dict[str, str]:
    return {
        "authorization": credentials.access_token,
        "refresh_token": credentials.refresh_token,
        "type": credentials.account_type,
    }


def _build_openlist_admin_client() -> OpenListAdminClient:
    return OpenListAdminClient(
        base_url=settings.openlist_base_url,
        admin_token=settings.openlist_admin_token,
    )


@router.post("/drives/{drive_id}/probe", response_model=DriveProbeRead)
async def probe_drive(
    drive_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveProbeRead:
    drive = session.get(UserDriveAccount, drive_id)
    if drive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drive not found")

    probe_result = await _probe_drive(request, drive)
    _finalize_drive_probe(drive, probe_result=probe_result)
    session.commit()
    session.refresh(drive)
    return _build_drive_probe_read(
        probe_result=probe_result,
        drive=drive,
        request=request,
    )


@router.post("/drives/probe", response_model=DriveProbeBulkResponse)
async def probe_drives(
    payload: DriveAccountBulkActionRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveProbeBulkResponse:
    drives = session.scalars(
        _build_drive_select_statement(
            ids=payload.ids,
            user_id=payload.user_id,
            drive_type=payload.drive_type,
            enabled=payload.enabled,
            share_pool_enabled=payload.share_pool_enabled,
        )
    ).all()
    results: list[DriveProbeRead] = []
    for drive in drives:
        probe_result = await _probe_drive(request, drive)
        _finalize_drive_probe(drive, probe_result=probe_result)
        session.flush()
        session.refresh(drive)
        results.append(
            _build_drive_probe_read(
                probe_result=probe_result,
                drive=drive,
                request=request,
            )
        )
    session.commit()
    return DriveProbeBulkResponse(
        matched=len(drives),
        healthy=sum(1 for result in results if result.ok),
        unhealthy=sum(1 for result in results if not result.ok),
        drive_ids=[drive.id for drive in drives],
        results=results,
    )


@router.patch("/drives/{drive_id}", response_model=DriveAccountRead)
async def update_drive(
    drive_id: int,
    payload: DriveAccountUpdate,
    request: Request,
    session: Session = Depends(get_session),
) -> DriveAccountRead:
    drive = session.get(UserDriveAccount, drive_id)
    if drive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drive not found")

    previous_root_dir = drive.root_dir
    previous_enabled = drive.enabled

    if payload.cookie is not None:
        drive.cookie_encrypted = request.app.state.cookie_cipher.encrypt(payload.cookie)
    if payload.caiyun is not None and drive.drive_type == "caiyun":
        await _update_caiyun_drive_tokens(drive, payload=payload)
    if payload.root_dir is not None:
        drive.root_dir = payload.root_dir
    if payload.enabled is not None:
        drive.enabled = payload.enabled
    if payload.share_pool_enabled is not None:
        drive.share_pool_enabled = payload.share_pool_enabled
    if payload.health_status is not None:
        drive.health_status = payload.health_status

    disable_roots: list[str] = []
    if payload.root_dir is not None and payload.root_dir != previous_root_dir:
        disable_roots.append(previous_root_dir)
    if previous_enabled and payload.enabled is False:
        disable_roots.extend([previous_root_dir, drive.root_dir])
    if disable_roots:
        normalized_roots = list(dict.fromkeys(disable_roots))
        _disable_drive_pool_objects(
            session,
            drive=drive,
            root_dirs=normalized_roots,
        )

    if (not previous_enabled) and payload.enabled is True:
        _enable_drive_pool_objects(
            session,
            drive=drive,
            root_dir=drive.root_dir,
        )

    session.commit()
    session.refresh(drive)
    return _build_drive_account_read(drive, request=request)


async def _update_caiyun_drive_tokens(
    drive: UserDriveAccount,
    *,
    payload: DriveAccountUpdate,
) -> None:
    if not drive.openlist_mount_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "drive_missing_mount_path", "message": "caiyun drive has no mount_path"},
        )
    assert payload.caiyun is not None
    admin_client = _build_openlist_admin_client()
    try:
        storages = await admin_client.list_storages()
        match = next(
            (storage for storage in storages if storage.mount_path == drive.openlist_mount_path),
            None,
        )
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "mount_missing", "mount_path": drive.openlist_mount_path},
            )
        try:
            await admin_client.update_storage(match.id, addition=_build_caiyun_addition(payload.caiyun))
        except OpenListAdminError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": "openlist_admin_failed", "message": exc.message},
            ) from None
    finally:
        await admin_client.aclose()


@router.post("/drives/disable", response_model=DriveAccountBulkActionResponse)
def disable_drives(
    payload: DriveAccountBulkActionRequest,
    session: Session = Depends(get_session),
) -> DriveAccountBulkActionResponse:
    drives = session.scalars(
        _build_drive_select_statement(
            ids=payload.ids,
            user_id=payload.user_id,
            drive_type=payload.drive_type,
            enabled=payload.enabled,
            share_pool_enabled=payload.share_pool_enabled,
        )
    ).all()
    drive_ids = [drive.id for drive in drives]
    updated = 0
    for drive in drives:
        if drive.enabled:
            drive.enabled = False
            updated += 1
    updated_pool_objects = _disable_selected_drives_pool_objects(session, drives=drives)
    session.commit()
    return DriveAccountBulkActionResponse(
        matched=len(drives),
        updated=updated,
        deleted=0,
        updated_pool_objects=updated_pool_objects,
        drive_ids=drive_ids,
    )


@router.post("/drives/enable", response_model=DriveAccountBulkActionResponse)
def enable_drives(
    payload: DriveAccountBulkActionRequest,
    session: Session = Depends(get_session),
) -> DriveAccountBulkActionResponse:
    drives = session.scalars(
        _build_drive_select_statement(
            ids=payload.ids,
            user_id=payload.user_id,
            drive_type=payload.drive_type,
            enabled=payload.enabled,
            share_pool_enabled=payload.share_pool_enabled,
        )
    ).all()
    drive_ids = [drive.id for drive in drives]
    updated = 0
    for drive in drives:
        if not drive.enabled:
            drive.enabled = True
            updated += 1
    updated_pool_objects = _enable_selected_drives_pool_objects(session, drives=drives)
    session.commit()
    return DriveAccountBulkActionResponse(
        matched=len(drives),
        updated=updated,
        deleted=0,
        updated_pool_objects=updated_pool_objects,
        drive_ids=drive_ids,
    )


@router.post("/drives/delete", response_model=DriveAccountBulkActionResponse)
def delete_drives(
    payload: DriveAccountBulkActionRequest,
    session: Session = Depends(get_session),
) -> DriveAccountBulkActionResponse:
    drives = session.scalars(
        _build_drive_select_statement(
            ids=payload.ids,
            user_id=payload.user_id,
            drive_type=payload.drive_type,
            enabled=payload.enabled,
            share_pool_enabled=payload.share_pool_enabled,
        )
    ).all()
    drive_ids = [drive.id for drive in drives]
    updated_pool_objects = _disable_selected_drives_pool_objects(session, drives=drives)
    for drive in drives:
        session.delete(drive)
    session.commit()
    return DriveAccountBulkActionResponse(
        matched=len(drives),
        updated=0,
        deleted=len(drives),
        updated_pool_objects=updated_pool_objects,
        drive_ids=drive_ids,
    )


@router.delete("/drives/{drive_id}", response_model=DriveAccountDeleteResponse)
async def delete_drive(
    drive_id: int,
    session: Session = Depends(get_session),
) -> DriveAccountDeleteResponse:
    drive = session.get(UserDriveAccount, drive_id)
    if drive is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drive not found")

    if drive.drive_type == "caiyun" and drive.openlist_mount_path:
        admin_client = _build_openlist_admin_client()
        try:
            try:
                await admin_client.delete_storage_by_mount(drive.openlist_mount_path)
            except OpenListAdminError as exc:
                if exc.status_code != 404:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={"error": "openlist_admin_failed", "message": exc.message},
                    ) from None
        finally:
            await admin_client.aclose()

    disabled_pool_objects = _disable_drive_pool_objects(
        session,
        drive=drive,
        root_dirs=[drive.root_dir],
    )
    user_id = drive.user_id
    session.delete(drive)
    session.commit()
    return DriveAccountDeleteResponse(
        drive_id=drive_id,
        user_id=user_id,
        disabled_pool_objects=disabled_pool_objects,
    )


@router.post("/catalog/sync", response_model=CatalogSyncResponse)
async def sync_catalog(
    payload: CatalogSyncRequest,
    session: Session = Depends(get_session),
) -> CatalogSyncResponse:
    root_path = payload.root_path or settings.catalog_root_path
    client = OpenListClient(settings.openlist_base_url, settings.openlist_token)
    service = CatalogSyncService(CatalogService(), client)
    try:
        result = await service.sync(session, root_path=root_path)
    finally:
        await client.aclose()
    return CatalogSyncResponse(
        root_path=root_path,
        inserted=result.inserted,
        updated=result.updated,
    )
