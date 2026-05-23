from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PoolObjectStatus(str, Enum):
    READY = "ready"
    SUSPECT = "suspect"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"
    STALE = "stale"


class TransferRoute(str, Enum):
    SELF = "self"
    POOL = "pool"
    SOURCE_COPY = "source_copy"
    SOURCE_STREAM = "source_stream"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


SUPPORTED_DRIVE_TYPES: frozenset[str] = frozenset({"115", "caiyun"})
OPENLIST_BACKED_DRIVE_TYPES: frozenset[str] = frozenset({"caiyun"})


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class UserDriveAccount(Base):
    __tablename__ = "user_drive_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    drive_type: Mapped[str] = mapped_column(String(32), default="115")
    cookie_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_dir: Mapped[str] = mapped_column(String(255), default="/EmbyCache")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    share_pool_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    openlist_mount_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openlist_storage_managed: Mapped[bool] = mapped_column(Boolean, default=True)


class MediaItem(Base):
    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_path: Mapped[str] = mapped_column(String(1024), unique=True)
    source_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int] = mapped_column(Integer)
    mtime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    openlist_path: Mapped[str] = mapped_column(String(1024))


class PoolObject(Base):
    __tablename__ = "pool_objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    drive_type: Mapped[str] = mapped_column(String(32))
    target_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[PoolObjectStatus] = mapped_column(
        SqlEnum(
            PoolObjectStatus,
            values_callable=enum_values,
            native_enum=False,
            name="pool_object_status",
        ),
        default=PoolObjectStatus.READY,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransferJob(Base):
    __tablename__ = "transfer_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), index=True)
    donor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    route_stage: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)


class PlaybackRecord(Base):
    __tablename__ = "playback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media_items.id"), index=True)
    route: Mapped[TransferRoute] = mapped_column(
        SqlEnum(
            TransferRoute,
            values_callable=enum_values,
            native_enum=False,
            name="transfer_route",
        )
    )
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(120))
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
