// All types mirror gateway.schemas — keep field names and optionality in sync.

// mirrors gateway.schemas.UserRead
export interface UserRead {
  id: number;
  username: string;
  status: string;
}

// mirrors gateway.schemas.UserCreate
export interface UserCreate {
  username: string;
  status?: string;
}

// mirrors gateway.schemas.DriveAccountRead
export interface DriveAccountRead {
  id: number;
  user_id: number;
  drive_type: string;
  root_dir: string;
  enabled: boolean;
  share_pool_enabled: boolean;
  health_status: string;
  last_checked_at: string | null;
  cookie_preview: string | null;
  openlist_mount_path: string | null;
  openlist_storage_managed: boolean;
}

// mirrors gateway.schemas.CaiyunDriveCredentials
// `refresh_token` and `account_type` have Python defaults; treat as optional on the client.
export interface CaiyunDriveCredentials {
  access_token: string;
  refresh_token?: string;
  account_type?: string;
}

// mirrors gateway.schemas.DriveAccountCreate
export interface DriveAccountCreate {
  user_id: number;
  drive_type: string;
  cookie?: string | null;
  root_dir: string;
  share_pool_enabled?: boolean;
  caiyun?: CaiyunDriveCredentials | null;
  mount_path?: string | null;
  adopt_existing?: boolean;
}

// mirrors gateway.schemas.PoolObjectRead
// `status` is the PoolObjectStatus enum on the server, serialized as a string.
export interface PoolObjectRead {
  id: number;
  media_id: number;
  owner_user_id: number;
  drive_type: string;
  target_path: string;
  status: string;
  last_verified_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  failure_count: number;
  cooldown_until: string | null;
}

// mirrors gateway.schemas.MediaItemRead
export interface MediaItemRead {
  id: number;
  source_path: string;
  source_file_id: string | null;
  size: number;
  mtime: string | null;
  fingerprint: string;
  openlist_path: string;
}

// mirrors gateway.schemas.TransferJobRead
export interface TransferJobRead {
  id: number;
  media_id: number;
  donor_user_id: number | null;
  target_user_id: number;
  route_stage: string;
  idempotency_key: string;
  status: string;
  error_code: string | null;
  attempt_no: number;
}

// mirrors gateway.schemas.PlaybackRecordRead
export interface PlaybackRecordRead {
  id: number;
  user_id: number;
  media_id: number;
  route: string;
  success: boolean;
  latency_ms: number;
}

// mirrors gateway.schemas.CredentialFieldRead
export interface CredentialFieldRead {
  name: string;
  label: string;
  secret: boolean;
  required: boolean;
  help_text: string | null;
}

// mirrors gateway.schemas.DriveTypeCapabilitiesRead
export interface DriveTypeCapabilitiesRead {
  can_stream: boolean;
  can_source_copy: boolean;
  can_pool_copy: boolean;
  managed_by_openlist: boolean;
  supports_health_probe: boolean;
  supports_user_bind: boolean;
}

// mirrors gateway.schemas.DriveTypeRead
export interface DriveTypeRead {
  drive_type: string;
  label: string;
  description: string;
  credential_type: string;
  default_root_dir: string;
  capabilities: DriveTypeCapabilitiesRead;
  credential_fields: CredentialFieldRead[];
}

// mirrors gateway.schemas.DriveStatsRead
export interface DriveStatsRead {
  total: number;
  users: number;
  enabled: number;
  disabled: number;
  share_pool_enabled: number;
  by_drive_type: Record<string, number>;
  by_health_status: Record<string, number>;
}

// mirrors gateway.schemas.PoolObjectStatsRead
export interface PoolObjectStatsRead {
  total: number;
  owners: number;
  media_items: number;
  by_status: Record<string, number>;
  by_drive_type: Record<string, number>;
  cooldown_active: number;
  cooldown_expired: number;
}

// mirrors gateway.schemas.DriveOverviewSectionRead
export interface DriveOverviewSectionRead {
  stats: DriveStatsRead;
  attention_total: number;
  probe_error_distribution: Record<string, number>;
  stale_probe_count: number;
  stale_probe_threshold_hours: number;
  items: DriveAccountRead[];
}

// mirrors gateway.schemas.PoolObjectOverviewSectionRead
export interface PoolObjectOverviewSectionRead {
  stats: PoolObjectStatsRead;
  attention_total: number;
  items: PoolObjectRead[];
}

// mirrors response of GET /api/admin/session (gateway.api.admin_auth.admin_session)
export interface AdminSessionRead {
  auth_enabled: boolean;
  authenticated: boolean;
}

// mirrors gateway.schemas.AdminOverviewRead
export interface AdminOverviewRead {
  routes: Record<string, number>;
  drives: DriveOverviewSectionRead;
  pool_objects: PoolObjectOverviewSectionRead;
}
