from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from gateway.models import PoolObjectStatus


class UserCreate(BaseModel):
    username: str
    status: str = "active"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    status: str


class CaiyunDriveCredentials(BaseModel):
    access_token: str
    refresh_token: str = ""
    account_type: str = "personal_new"


class DriveAccountCreate(BaseModel):
    user_id: int
    drive_type: str
    cookie: str | None = None
    root_dir: str
    share_pool_enabled: bool = False
    caiyun: CaiyunDriveCredentials | None = None
    mount_path: str | None = None
    adopt_existing: bool = False

    @model_validator(mode="after")
    def validate_credentials_match_drive_type(self) -> "DriveAccountCreate":
        if self.drive_type == "115":
            if not self.cookie:
                raise ValueError("cookie is required for drive_type=115")
            return self
        if self.drive_type == "caiyun":
            if self.adopt_existing:
                if not self.mount_path:
                    raise ValueError("mount_path is required when adopt_existing=true")
                return self
            if self.caiyun is None or not self.caiyun.access_token:
                raise ValueError("caiyun.access_token is required for drive_type=caiyun")
            return self
        raise ValueError(f"unsupported drive_type: {self.drive_type}")


class DriveAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    drive_type: str
    root_dir: str
    enabled: bool
    share_pool_enabled: bool
    health_status: str
    last_checked_at: datetime | None = None
    cookie_preview: str | None = None
    openlist_mount_path: str | None = None
    openlist_storage_managed: bool = True


class DriveAccountUpdate(BaseModel):
    cookie: str | None = None
    caiyun: CaiyunDriveCredentials | None = None
    root_dir: str | None = None
    enabled: bool | None = None
    share_pool_enabled: bool | None = None
    health_status: str | None = None

    @model_validator(mode="after")
    def validate_has_changes(self) -> "DriveAccountUpdate":
        if any(
            value is not None
            for value in (
                self.cookie,
                self.caiyun,
                self.root_dir,
                self.enabled,
                self.share_pool_enabled,
                self.health_status,
            )
        ):
            return self
        raise ValueError("at least one field must be provided")


class DriveAccountDeleteResponse(BaseModel):
    drive_id: int
    user_id: int
    disabled_pool_objects: int


class DriveAccountBulkActionRequest(BaseModel):
    ids: list[int] | None = None
    user_id: int | None = None
    drive_type: str | None = None
    enabled: bool | None = None
    share_pool_enabled: bool | None = None

    @model_validator(mode="after")
    def validate_has_selector(self) -> "DriveAccountBulkActionRequest":
        if (
            self.ids
            or self.user_id is not None
            or self.drive_type is not None
            or self.enabled is not None
            or self.share_pool_enabled is not None
        ):
            return self
        raise ValueError("at least one selector is required")


class DriveAccountBulkActionResponse(BaseModel):
    matched: int
    updated: int
    deleted: int
    updated_pool_objects: int
    drive_ids: list[int]


class DriveStatsRead(BaseModel):
    total: int
    users: int
    enabled: int
    disabled: int
    share_pool_enabled: int
    by_drive_type: dict[str, int]
    by_health_status: dict[str, int]


class DriveProbeRead(BaseModel):
    ok: bool
    error_code: str | None
    detail: str | None = None
    drive: DriveAccountRead


class DriveProbeBulkResponse(BaseModel):
    matched: int
    healthy: int
    unhealthy: int
    drive_ids: list[int]
    results: list[DriveProbeRead]


class CredentialFieldRead(BaseModel):
    name: str
    label: str
    secret: bool
    required: bool
    help_text: str | None = None


class DriveTypeCapabilitiesRead(BaseModel):
    can_stream: bool
    can_source_copy: bool
    can_pool_copy: bool
    managed_by_openlist: bool
    supports_health_probe: bool
    supports_user_bind: bool


class DriveTypeRead(BaseModel):
    drive_type: str
    label: str
    description: str
    credential_type: str
    default_root_dir: str
    capabilities: DriveTypeCapabilitiesRead
    credential_fields: list[CredentialFieldRead]


class CatalogSyncRequest(BaseModel):
    root_path: str | None = None


class CatalogSyncResponse(BaseModel):
    root_path: str
    inserted: int
    updated: int


class MediaItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_path: str
    source_file_id: str | None
    size: int
    mtime: datetime | None = None
    fingerprint: str
    openlist_path: str


class PoolObjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int
    owner_user_id: int
    drive_type: str
    target_path: str
    status: PoolObjectStatus
    last_verified_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    failure_count: int
    cooldown_until: datetime | None = None


class PoolObjectBulkActionRequest(BaseModel):
    ids: list[int] | None = None
    owner_user_id: int | None = None
    media_id: int | None = None
    statuses: list[PoolObjectStatus] | None = None

    @model_validator(mode="after")
    def validate_has_selector(self) -> "PoolObjectBulkActionRequest":
        if self.ids or self.owner_user_id is not None or self.media_id is not None or self.statuses:
            return self
        raise ValueError("at least one selector is required")


class PoolObjectBulkActionResponse(BaseModel):
    matched: int
    updated: int
    pool_objects: list[PoolObjectRead]


class PoolObjectStatsRead(BaseModel):
    total: int
    owners: int
    media_items: int
    by_status: dict[str, int]
    by_drive_type: dict[str, int]
    cooldown_active: int
    cooldown_expired: int


class DriveOverviewSectionRead(BaseModel):
    stats: DriveStatsRead
    attention_total: int
    probe_error_distribution: dict[str, int]
    stale_probe_count: int
    stale_probe_threshold_hours: int
    items: list[DriveAccountRead]


class PoolObjectOverviewSectionRead(BaseModel):
    stats: PoolObjectStatsRead
    attention_total: int
    items: list[PoolObjectRead]


class AdminOverviewRead(BaseModel):
    routes: dict[str, int]
    drives: DriveOverviewSectionRead
    pool_objects: PoolObjectOverviewSectionRead
