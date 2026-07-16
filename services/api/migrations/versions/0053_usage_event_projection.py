"""asynchronous tenant usage event projection

Revision ID: 0053_usage_event_projection
Revises: 0052_tenant_usage_event_journal
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0053_usage_event_projection"
down_revision: str | None = "0052_tenant_usage_event_journal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    rolling_default = sa.func.now() if op.get_bind().dialect.name == "postgresql" else None
    op.add_column(
        "tenant_usage_events",
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=rolling_default,
        ),
    )
    # Every pre-0053 event was synchronously folded into the rollup. Marking
    # these rows projected prevents the new projector from counting history
    # twice during rollout.
    op.execute(
        "UPDATE tenant_usage_events "
        "SET projected_at = recorded_at "
        "WHERE projected_at IS NULL"
    )
    # Keep the default through the rolling-deploy compatibility window. Old
    # 0052 replicas omit this column and must therefore create already-projected
    # rows; 0053 code explicitly writes NULL for deferred request events.
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_tenant_usage_events_unprojected",
            "tenant_usage_events",
            ["recorded_at", "id"],
            unique=False,
            postgresql_where=sa.text("projected_at IS NULL"),
            sqlite_where=sa.text("projected_at IS NULL"),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM tenant_usage_events WHERE projected_at IS NULL) "
            "THEN RAISE EXCEPTION "
            "'cannot downgrade with unprojected tenant usage events'; "
            "END IF; END $$"
        )
    else:
        pending = op.get_bind().execute(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM tenant_usage_events WHERE projected_at IS NULL"
                ")"
            )
        ).scalar_one()
        if pending:
            raise RuntimeError(
                "Cannot downgrade while tenant usage events are awaiting projection."
            )
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_tenant_usage_events_unprojected",
            table_name="tenant_usage_events",
            postgresql_concurrently=True,
        )
    op.drop_column("tenant_usage_events", "projected_at")
