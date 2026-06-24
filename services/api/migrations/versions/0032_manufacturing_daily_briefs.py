"""manufacturing daily briefs

Revision ID: 0032_manufacturing_daily_briefs
Revises: 0031_manufacturing_operation_records
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_manufacturing_daily_briefs"
down_revision: str | None = "0031_manufacturing_operation_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "manufacturing_daily_briefs"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("brief_id", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("brief_date", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("required_scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_record_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "brief_id",
            name="uq_manufacturing_daily_briefs_tenant_brief",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_manufacturing_daily_briefs_tenant_idempotency",
        ),
    )
    for column_name in (
        "tenant_id",
        "brief_id",
        "idempotency_key",
        "brief_date",
        "status",
        "requested_by",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_manufacturing_daily_briefs_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    op.drop_table("manufacturing_daily_briefs")
