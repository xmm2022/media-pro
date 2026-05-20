import sqlalchemy as sa
from alembic import op


revision = "0002_pool_object_health_state"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pool_objects",
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pool_objects",
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pool_objects",
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pool_objects", "cooldown_until")
    op.drop_column("pool_objects", "failure_count")
    op.drop_column("pool_objects", "last_failure_at")
