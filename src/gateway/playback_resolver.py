from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from time import perf_counter

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from gateway.integrations.drive115_stream_client import Drive115StreamClient
from gateway.integrations.openlist_client import OpenListClient, StreamInfo
from gateway.integrations.pool_copy_115_client import PoolCopy115Client
from gateway.integrations.rapid_copy_client import (
    PoolCopyRequest,
    RapidCopyClient,
    RapidCopyResult,
    SourceCopyRequest,
    SourceObjectRef,
)
from gateway.integrations.rapid_copy_strategy import (
    RapidCopyStrategy,
    RapidCopyStrategyRegistry,
    UnsupportedDriveType,
)
from gateway.integrations.source_copy_115_client import SourceCopy115Client
from gateway.models import (
    MediaItem,
    PlaybackRecord,
    PoolObject,
    PoolObjectStatus,
    TransferJob,
    TransferRoute,
    User,
    UserDriveAccount,
)
from gateway.playback import PlaybackDecision, PlaybackService
from gateway.pool import DonorCandidate, PoolService
from gateway.security import CookieCipher
from gateway.transfer import TransferService


@dataclass(frozen=True, slots=True)
class DonorBundle:
    candidate: DonorCandidate
    drive: UserDriveAccount
    pool_object: PoolObject


DONOR_STALE_ERROR_CODES = {"missing_donor_file"}
DONOR_COOLDOWN_ERROR_CODES = {"donor_range_unavailable", "source_range_signature_invalid"}
TARGET_COPY_BLOCKING_ERROR_CODES = {
    "file_too_large_for_account",
    "invalid_target_path",
    "quick_upload_unavailable",
}
DONOR_COOLDOWN_THRESHOLD = 2
DONOR_COOLDOWN_WINDOW = timedelta(minutes=10)


class PlaybackResolver:
    def __init__(
        self,
        playback_service: PlaybackService,
        openlist_client: OpenListClient,
        *,
        strategy_registry: RapidCopyStrategyRegistry | None = None,
        rapid_copy_client: RapidCopyClient | None = None,
        pool_copy_client: PoolCopy115Client | None = None,
        source_copy_client: SourceCopy115Client | None = None,
        drive_stream_client: Drive115StreamClient | None = None,
        cookie_cipher: CookieCipher | None = None,
        pool_service: PoolService | None = None,
        transfer_service: TransferService | None = None,
    ) -> None:
        self._playback_service = playback_service
        self._openlist_client = openlist_client
        self._rapid_copy_client = rapid_copy_client
        self._pool_copy_client = pool_copy_client
        self._source_copy_client = source_copy_client
        self._drive_stream_client = drive_stream_client
        self._cookie_cipher = cookie_cipher
        self._strategy_registry = strategy_registry
        self._pool_service = pool_service or PoolService()
        self._transfer_service = transfer_service or TransferService()

    async def resolve(self, session: Session, *, user_id: int, media_id: int) -> PlaybackDecision:
        started = perf_counter()
        user = session.get(User, user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")

        media = session.get(MediaItem, media_id)
        if media is None:
            raise LookupError(f"media {media_id} not found")

        target_drive = self._load_target_drive(session, user_id=user_id)
        target_cookie = self._decrypt_cookie(target_drive)
        strategy = self._dispatch_strategy(target_drive) if target_drive is not None else None
        self_pool = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id == user_id,
                PoolObject.drive_type == target_drive.drive_type if target_drive is not None else False,
            )
        )
        if self_pool is not None and target_drive is not None:
            self._recover_expired_cooldown(self_pool)
            decision = await self._stream_decision(
                "self",
                source_path=media.openlist_path,
                target_path=self_pool.target_path,
                target_cookie=target_cookie,
            )
            if decision.route == "self":
                self._mark_pool_object_ready(self_pool)
                self._record_playback(
                    session,
                    user_id=user_id,
                    media_id=media_id,
                    route=decision.route,
                    started=started,
                )
                return decision
            self._mark_pool_object_stale(self_pool)

        donor_bundle = self._select_donor_bundle(session, user_id=user_id, media_id=media_id)

        can_attempt_source_copy = (
            strategy is not None
            or (
                target_cookie is not None
                and (self._source_copy_client is not None or self._rapid_copy_client is not None)
            )
        )
        if target_drive is not None and can_attempt_source_copy:
            target_path = self._build_target_path(target_drive, media.source_path)
            should_attempt_source_copy = True

            donor_cookie = None
            if donor_bundle is not None and self._cookie_cipher is not None:
                donor_cookie = self._cookie_cipher.decrypt(donor_bundle.drive.cookie_encrypted)

            can_attempt_pool_copy = (
                strategy is not None
                or (
                    target_cookie is not None
                    and (self._pool_copy_client is not None or self._rapid_copy_client is not None)
                )
            )
            if donor_bundle is not None and can_attempt_pool_copy:
                pool_request = PoolCopyRequest(
                    donor_cookie=donor_cookie or "",
                    target_cookie=target_cookie or "",
                    source_path=donor_bundle.pool_object.target_path,
                    target_path=target_path,
                )
                if strategy is not None:
                    try:
                        donor_result = await strategy.copy_from_pool(pool_request)
                    except NotImplementedError:
                        donor_result = RapidCopyResult(
                            ok=False,
                            error_code="pool_not_supported_for_drive_type",
                        )
                elif self._pool_copy_client is not None:
                    donor_result = await self._pool_copy_client.copy_from_pool(pool_request)
                else:
                    assert self._rapid_copy_client is not None
                    donor_result = await self._rapid_copy_client.copy_from_pool(pool_request)
                self._record_transfer_job(
                    session,
                    media_id=media_id,
                    donor_user_id=donor_bundle.candidate.user_id,
                    target_user_id=user_id,
                    route_stage="try_pool",
                    result=donor_result,
                )
                if donor_result.ok:
                    self._mark_pool_object_ready(donor_bundle.pool_object)
                    target_pool = self._upsert_pool_object(
                        session,
                        media_id=media_id,
                        owner_user_id=user_id,
                        target_path=donor_result.target_path or target_path,
                        drive_type=target_drive.drive_type,
                    )
                    decision = await self._stream_decision(
                        "pool",
                        source_path=media.openlist_path,
                        target_path=donor_result.target_path or target_path,
                        target_cookie=target_cookie,
                    )
                    if decision.route != "pool":
                        self._mark_pool_object_suspect(target_pool)
                    self._record_playback(
                        session,
                        user_id=user_id,
                        media_id=media_id,
                        route=decision.route,
                        started=started,
                    )
                    return decision
                self._mark_donor_pool_failure(donor_bundle.pool_object, donor_result.error_code)
                if donor_result.error_code in TARGET_COPY_BLOCKING_ERROR_CODES:
                    should_attempt_source_copy = False

            if should_attempt_source_copy:
                source_request = SourceCopyRequest(
                    target_cookie=target_cookie or "",
                    source=SourceObjectRef(
                        openlist_path=media.openlist_path,
                        source_path=media.source_path,
                        source_file_id=media.source_file_id,
                        fingerprint=media.fingerprint,
                    ),
                    target_path=target_path,
                )
                if strategy is not None:
                    source_result = await strategy.copy_from_source(source_request)
                elif self._source_copy_client is not None:
                    source_result = await self._source_copy_client.copy_from_source(source_request)
                else:
                    assert self._rapid_copy_client is not None
                    source_result = await self._rapid_copy_client.copy_from_source(source_request)
                self._record_transfer_job(
                    session,
                    media_id=media_id,
                    donor_user_id=None,
                    target_user_id=user_id,
                    route_stage="try_source_copy",
                    result=source_result,
                )
                if source_result.ok:
                    target_pool = self._upsert_pool_object(
                        session,
                        media_id=media_id,
                        owner_user_id=user_id,
                        target_path=source_result.target_path or target_path,
                        drive_type=target_drive.drive_type,
                    )
                    decision = await self._stream_decision(
                        "source_copy",
                        source_path=media.openlist_path,
                        target_path=source_result.target_path or target_path,
                        target_cookie=target_cookie,
                    )
                    if decision.route != "source_copy":
                        self._mark_pool_object_suspect(target_pool)
                    self._record_playback(
                        session,
                        user_id=user_id,
                        media_id=media_id,
                        route=decision.route,
                        started=started,
                    )
                    return decision

        decision = await self._source_stream_decision(media.openlist_path)
        self._record_playback(session, user_id=user_id, media_id=media_id, route=decision.route, started=started)
        return decision

    async def _stream_decision(
        self,
        route: str,
        *,
        source_path: str,
        target_path: str,
        target_cookie: str | None,
    ) -> PlaybackDecision:
        stream_info = await self._cached_stream_info(target_path=target_path, target_cookie=target_cookie)
        if stream_info is None:
            return await self._source_stream_decision(source_path)
        return PlaybackDecision(
            route=route,
            stream_url=stream_info.raw_url,
            stream_headers=stream_info.request_headers,
        )

    async def _source_stream_decision(self, source_path: str) -> PlaybackDecision:
        stream_info = await self._openlist_client.get_stream_info(source_path)
        return self._playback_service.resolve(
            self_hit=None,
            donor_available=False,
            source_copy_supported=False,
            source_stream_url=stream_info.raw_url,
        )

    async def _cached_stream_info(
        self,
        *,
        target_path: str,
        target_cookie: str | None,
    ) -> StreamInfo | None:
        if self._drive_stream_client is not None and target_cookie:
            try:
                return await self._drive_stream_client.get_stream_info(target_cookie, target_path)
            except Exception:
                pass

        try:
            return await self._openlist_client.get_stream_info(target_path)
        except Exception:
            return None

    def _load_target_drive(self, session: Session, *, user_id: int) -> UserDriveAccount | None:
        drive_type_preference = case(
            (UserDriveAccount.drive_type == "115", 0),
            else_=1,
        )
        return session.scalar(
            select(UserDriveAccount)
            .where(
                UserDriveAccount.user_id == user_id,
                UserDriveAccount.enabled.is_(True),
            )
            .order_by(drive_type_preference, UserDriveAccount.id.desc())
        )

    def _decrypt_cookie(self, drive: UserDriveAccount | None) -> str | None:
        if drive is None or self._cookie_cipher is None:
            return None
        if drive.cookie_encrypted is None:
            return None
        return self._cookie_cipher.decrypt(drive.cookie_encrypted)

    def _dispatch_strategy(self, target_drive: UserDriveAccount) -> RapidCopyStrategy | None:
        if self._strategy_registry is None:
            return None
        try:
            return self._strategy_registry.get(target_drive.drive_type)
        except UnsupportedDriveType:
            return None

    def _select_donor_bundle(self, session: Session, *, user_id: int, media_id: int) -> DonorBundle | None:
        pool_objects = session.scalars(
            select(PoolObject)
            .where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id != user_id,
                PoolObject.drive_type == "115",
            )
            .order_by(PoolObject.id)
        ).all()
        if not pool_objects:
            return None

        bundles: list[DonorBundle] = []
        candidates: list[DonorCandidate] = []
        for pool_object in pool_objects:
            self._recover_expired_cooldown(pool_object)
            drive = session.scalar(
                select(UserDriveAccount)
                .where(
                    UserDriveAccount.user_id == pool_object.owner_user_id,
                    UserDriveAccount.drive_type == "115",
                    UserDriveAccount.enabled.is_(True),
                    UserDriveAccount.share_pool_enabled.is_(True),
                )
                .order_by(UserDriveAccount.id.desc())
            )
            if drive is None:
                continue
            score = 0
            if pool_object.last_success_at is not None:
                score = int(pool_object.last_success_at.timestamp())
            candidate = DonorCandidate(
                user_id=pool_object.owner_user_id,
                target_path=pool_object.target_path,
                status=self._coerce_status(pool_object.status),
                last_success_score=score,
            )
            bundles.append(DonorBundle(candidate=candidate, drive=drive, pool_object=pool_object))
            candidates.append(candidate)

        if not candidates:
            return None

        selected = self._pool_service.select_donor(candidates)
        for bundle in bundles:
            if bundle.candidate.user_id == selected.user_id and bundle.candidate.target_path == selected.target_path:
                return bundle
        return None

    def _coerce_status(self, status: PoolObjectStatus | str) -> str:
        if hasattr(status, "value"):
            return status.value  # type: ignore[return-value]
        return str(status)

    def _build_target_path(self, target_drive: UserDriveAccount, source_path: str) -> str:
        target_path = PurePosixPath(target_drive.root_dir) / PurePosixPath(source_path.lstrip("/"))
        if target_drive.openlist_mount_path:
            return str(PurePosixPath(target_drive.openlist_mount_path) / str(target_path).lstrip("/"))
        return str(target_path)

    def _record_transfer_job(
        self,
        session: Session,
        *,
        media_id: int,
        donor_user_id: int | None,
        target_user_id: int,
        route_stage: str,
        result: RapidCopyResult,
    ) -> None:
        idempotency_key = self._transfer_service.build_idempotency_key(
            user_id=target_user_id,
            media_id=media_id,
            route_stage=route_stage,
        )
        job = session.scalar(
            select(TransferJob).where(TransferJob.idempotency_key == idempotency_key)
        )
        if job is None:
            session.add(
                TransferJob(
                    media_id=media_id,
                    donor_user_id=donor_user_id,
                    target_user_id=target_user_id,
                    route_stage=route_stage,
                    idempotency_key=idempotency_key,
                    attempt_no=1,
                    status="success" if result.ok else "failed",
                    error_code=result.error_code,
                )
            )
            return

        job.attempt_no += 1
        job.status = "success" if result.ok else "failed"
        job.error_code = result.error_code
        job.donor_user_id = donor_user_id

    def _upsert_pool_object(
        self,
        session: Session,
        *,
        media_id: int,
        owner_user_id: int,
        target_path: str,
        drive_type: str,
    ) -> PoolObject:
        pool_object = session.scalar(
            select(PoolObject).where(
                PoolObject.media_id == media_id,
                PoolObject.owner_user_id == owner_user_id,
            )
        )
        if pool_object is None:
            pool_object = PoolObject(
                media_id=media_id,
                owner_user_id=owner_user_id,
                drive_type=drive_type,
                target_path=target_path,
                status=PoolObjectStatus.READY,
            )
            session.add(pool_object)
            self._mark_pool_object_ready(pool_object)
            return pool_object

        pool_object.target_path = target_path
        self._mark_pool_object_ready(pool_object)
        return pool_object

    def _recover_expired_cooldown(self, pool_object: PoolObject) -> None:
        if self._coerce_status(pool_object.status) != PoolObjectStatus.COOLDOWN.value:
            return
        cooldown_until = self._normalize_timestamp(pool_object.cooldown_until)
        if cooldown_until is None or cooldown_until > self._utcnow():
            return
        pool_object.status = PoolObjectStatus.READY
        pool_object.cooldown_until = None
        pool_object.failure_count = 0

    def _mark_pool_object_ready(self, pool_object: PoolObject) -> None:
        now = self._utcnow()
        pool_object.status = PoolObjectStatus.READY
        pool_object.last_verified_at = now
        pool_object.last_success_at = now
        pool_object.last_failure_at = None
        pool_object.failure_count = 0
        pool_object.cooldown_until = None

    def _mark_pool_object_suspect(self, pool_object: PoolObject) -> None:
        now = self._utcnow()
        pool_object.status = PoolObjectStatus.SUSPECT
        pool_object.last_verified_at = now
        pool_object.last_failure_at = now
        pool_object.failure_count = max(pool_object.failure_count, 0) + 1
        pool_object.cooldown_until = None

    def _mark_pool_object_stale(self, pool_object: PoolObject) -> None:
        now = self._utcnow()
        pool_object.status = PoolObjectStatus.STALE
        pool_object.last_verified_at = now
        pool_object.last_failure_at = now
        pool_object.failure_count = max(pool_object.failure_count, 0) + 1
        pool_object.cooldown_until = None

    def _mark_donor_pool_failure(self, pool_object: PoolObject, error_code: str | None) -> None:
        if error_code in TARGET_COPY_BLOCKING_ERROR_CODES:
            return
        if error_code in DONOR_STALE_ERROR_CODES:
            self._mark_pool_object_stale(pool_object)
            return

        now = self._utcnow()
        next_failure_count = max(pool_object.failure_count, 0) + 1
        pool_object.last_verified_at = now
        pool_object.last_failure_at = now
        pool_object.failure_count = next_failure_count
        if error_code in DONOR_COOLDOWN_ERROR_CODES and next_failure_count >= DONOR_COOLDOWN_THRESHOLD:
            pool_object.status = PoolObjectStatus.COOLDOWN
            pool_object.cooldown_until = now + DONOR_COOLDOWN_WINDOW
            return

        pool_object.status = PoolObjectStatus.SUSPECT
        pool_object.cooldown_until = None

    def _normalize_timestamp(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _record_playback(
        self,
        session: Session,
        *,
        user_id: int,
        media_id: int,
        route: str,
        started: float,
    ) -> None:
        session.add(
            PlaybackRecord(
                user_id=user_id,
                media_id=media_id,
                route=TransferRoute(route),
                success=True,
                latency_ms=max(0, int((perf_counter() - started) * 1000)),
            )
        )
        session.commit()
