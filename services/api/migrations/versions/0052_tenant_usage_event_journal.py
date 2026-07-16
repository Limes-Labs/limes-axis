"""durable tenant usage event journal

Revision ID: 0052_tenant_usage_event_journal
Revises: 0051_agent_runs
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052_tenant_usage_event_journal"
down_revision: str | None = "0051_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant_usage_records",
        sa.Column(
            "period_window_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("86400"),
        ),
    )
    op.create_check_constraint(
        "ck_tenant_usage_records_period_window_range",
        "tenant_usage_records",
        "period_window_seconds BETWEEN 60 AND 86400",
    )
    op.drop_index(
        "ix_tenant_usage_records_tenant_metric_period",
        table_name="tenant_usage_records",
    )
    op.drop_constraint(
        "uq_tenant_usage_records_tenant_metric_period",
        "tenant_usage_records",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_tenant_usage_records_tenant_metric_window_period",
        "tenant_usage_records",
        ["tenant_id", "metric_key", "period_window_seconds", "period_start"],
    )
    op.create_index(
        "ix_tenant_usage_records_tenant_metric_window_period",
        "tenant_usage_records",
        ["tenant_id", "metric_key", "period_window_seconds", "period_start"],
    )
    # The legacy rollup kept the dimensions from whichever event inserted the
    # bucket first, which was not a truthful dimensional aggregate.
    op.execute("UPDATE tenant_usage_records SET dimensions = '{}'::jsonb")

    op.create_table(
        "tenant_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("metric_key", sa.String(length=60), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("source_id", sa.String(length=220), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_window_seconds", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_tenant_usage_events_quantity_positive",
        ),
        sa.CheckConstraint(
            "period_window_seconds BETWEEN 60 AND 86400",
            name="ck_tenant_usage_events_period_window_range",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "metric_key",
            "source_type",
            "source_id",
            name="uq_tenant_usage_events_source",
        ),
    )
    for column_name in (
        "tenant_id",
        "metric_key",
        "source_type",
        "period_start",
        "occurred_at",
    ):
        op.create_index(
            f"ix_tenant_usage_events_{column_name}",
            "tenant_usage_events",
            [column_name],
        )
    op.create_index(
        "ix_tenant_usage_events_tenant_occurred",
        "tenant_usage_events",
        ["tenant_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_tenant_usage_events_tenant_metric_window_period",
        "tenant_usage_events",
        ["tenant_id", "metric_key", "period_window_seconds", "period_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_usage_events_tenant_metric_window_period",
        table_name="tenant_usage_events",
    )
    op.drop_index(
        "ix_tenant_usage_events_tenant_occurred",
        table_name="tenant_usage_events",
    )
    for column_name in (
        "occurred_at",
        "period_start",
        "source_type",
        "metric_key",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_tenant_usage_events_{column_name}",
            table_name="tenant_usage_events",
        )
    op.drop_table("tenant_usage_events")

    op.drop_index(
        "ix_tenant_usage_records_tenant_metric_window_period",
        table_name="tenant_usage_records",
    )
    op.drop_constraint(
        "uq_tenant_usage_records_tenant_metric_window_period",
        "tenant_usage_records",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_tenant_usage_records_tenant_metric_period",
        "tenant_usage_records",
        ["tenant_id", "metric_key", "period_start"],
    )
    op.create_index(
        "ix_tenant_usage_records_tenant_metric_period",
        "tenant_usage_records",
        ["tenant_id", "metric_key", "period_start"],
    )
    op.drop_constraint(
        "ck_tenant_usage_records_period_window_range",
        "tenant_usage_records",
        type_="check",
    )
    op.drop_column("tenant_usage_records", "period_window_seconds")
