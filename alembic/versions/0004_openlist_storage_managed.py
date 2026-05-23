import sqlalchemy as sa
from alembic import op


revision = "0004_openlist_storage_managed"
down_revision = "0003_caiyun_drive_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_drive_accounts",
        sa.Column(
            "openlist_storage_managed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_drive_accounts", "openlist_storage_managed")
