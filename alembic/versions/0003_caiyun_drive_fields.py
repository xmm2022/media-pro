import sqlalchemy as sa
from alembic import op


revision = "0003_caiyun_drive_fields"
down_revision = "0002_pool_object_health_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_drive_accounts",
        sa.Column("openlist_mount_path", sa.String(length=255), nullable=True),
    )
    with op.batch_alter_table("user_drive_accounts") as batch_op:
        batch_op.alter_column(
            "cookie_encrypted",
            existing_type=sa.Text(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("user_drive_accounts") as batch_op:
        batch_op.alter_column(
            "cookie_encrypted",
            existing_type=sa.Text(),
            nullable=False,
        )
    op.drop_column("user_drive_accounts", "openlist_mount_path")
