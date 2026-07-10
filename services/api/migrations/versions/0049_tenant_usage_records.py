"""tenant usage records

Revision ID: 0049_tenant_usage_records
Revises: 0048_session_device_metadata
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0049_tenant_usage_records"
down_revision: str | None = "0048_session_device_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("metric_key", sa.String(length=60), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("first_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "metric_key",
            "period_start",
            name="uq_tenant_usage_records_tenant_metric_period",
        ),
    )
    for column_name in ("tenant_id", "metric_key", "period_start"):
        op.create_index(
            f"ix_tenant_usage_records_{column_name}",
            "tenant_usage_records",
            [column_name],
        )
    # Composite index backing the per-metric, per-period aggregation reads.
    op.create_index(
        "ix_tenant_usage_records_tenant_metric_period",
        "tenant_usage_records",
        ["tenant_id", "metric_key", "period_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_usage_records_tenant_metric_period",
        table_name="tenant_usage_records",
    )
    for column_name in ("period_start", "metric_key", "tenant_id"):
        op.drop_index(
            f"ix_tenant_usage_records_{column_name}",
            table_name="tenant_usage_records",
        )
    op.drop_table("tenant_usage_records")
