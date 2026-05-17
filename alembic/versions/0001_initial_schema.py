import sqlalchemy as sa
from alembic import op


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("template_id", sa.String(length=120), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "media_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("source_file_id", sa.String(length=255), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("openlist_path", sa.String(length=1024), nullable=False),
        sa.UniqueConstraint("source_path"),
    )
    op.create_index("ix_media_items_fingerprint", "media_items", ["fingerprint"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"], unique=False)

    op.create_table(
        "user_drive_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("drive_type", sa.String(length=32), nullable=False),
        sa.Column("cookie_encrypted", sa.Text(), nullable=False),
        sa.Column("root_dir", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("share_pool_enabled", sa.Boolean(), nullable=False),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_drive_accounts_user_id", "user_drive_accounts", ["user_id"], unique=False
    )

    op.create_table(
        "pool_objects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("media_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("drive_type", sa.String(length=32), nullable=False),
        sa.Column("target_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ready",
                "suspect",
                "cooldown",
                "disabled",
                "stale",
                name="pool_object_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pool_objects_media_id", "pool_objects", ["media_id"], unique=False)
    op.create_index("ix_pool_objects_owner_user_id", "pool_objects", ["owner_user_id"], unique=False)

    op.create_table(
        "transfer_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("media_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=False),
        sa.Column("donor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("route_stage", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
    )
    op.create_index("ix_transfer_jobs_media_id", "transfer_jobs", ["media_id"], unique=False)
    op.create_index(
        "ix_transfer_jobs_target_user_id", "transfer_jobs", ["target_user_id"], unique=False
    )
    op.create_index(
        "ix_transfer_jobs_idempotency_key", "transfer_jobs", ["idempotency_key"], unique=True
    )

    op.create_table(
        "playback_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("media_id", sa.Integer(), sa.ForeignKey("media_items.id"), nullable=False),
        sa.Column(
            "route",
            sa.Enum(
                "self",
                "pool",
                "source_copy",
                "source_stream",
                name="transfer_route",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
    )
    op.create_index("ix_playback_records_user_id", "playback_records", ["user_id"], unique=False)
    op.create_index("ix_playback_records_media_id", "playback_records", ["media_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_playback_records_media_id", table_name="playback_records")
    op.drop_index("ix_playback_records_user_id", table_name="playback_records")
    op.drop_table("playback_records")

    op.drop_index("ix_transfer_jobs_idempotency_key", table_name="transfer_jobs")
    op.drop_index("ix_transfer_jobs_target_user_id", table_name="transfer_jobs")
    op.drop_index("ix_transfer_jobs_media_id", table_name="transfer_jobs")
    op.drop_table("transfer_jobs")

    op.drop_index("ix_pool_objects_owner_user_id", table_name="pool_objects")
    op.drop_index("ix_pool_objects_media_id", table_name="pool_objects")
    op.drop_table("pool_objects")

    op.drop_index("ix_user_drive_accounts_user_id", table_name="user_drive_accounts")
    op.drop_table("user_drive_accounts")

    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_media_items_fingerprint", table_name="media_items")
    op.drop_table("media_items")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
