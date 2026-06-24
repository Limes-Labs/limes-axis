"""manufacturing risk scenarios

Revision ID: 0033_manufacturing_risk_scenarios
Revises: 0032_manufacturing_daily_briefs
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_manufacturing_risk_scenarios"
down_revision: str | None = "0032_manufacturing_daily_briefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "manufacturing_risk_scenarios"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("scenario_id", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("owner_role", sa.String(length=160), nullable=False),
        sa.Column("workflow_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_record_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scenario_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "scenario_id",
            name="uq_manufacturing_risk_scenarios_tenant_scenario",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_manufacturing_risk_scenarios_tenant_idempotency",
        ),
    )
    for column_name in (
        "tenant_id",
        "scenario_id",
        "idempotency_key",
        "domain",
        "status",
        "risk_level",
        "requested_by",
        "owner_role",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_manufacturing_risk_scenarios_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    op.drop_table("manufacturing_risk_scenarios")
