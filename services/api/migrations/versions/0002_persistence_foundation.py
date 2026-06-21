"""persistence foundation

Revision ID: 0002_persistence_foundation
Revises: 0001_foundation
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_persistence_foundation"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("approval_id", sa.String(length=160), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=True),
        sa.Column("action_id", sa.String(length=160), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("owner_role", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=True),
        sa.Column("decision_actor_id", sa.String(length=160), nullable=True),
        sa.Column("decision_note", sa.String(length=600), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "approval_id",
            name="uq_approval_records_tenant_approval",
        ),
    )
    op.create_index("ix_approval_records_action_id", "approval_records", ["action_id"])
    op.create_index("ix_approval_records_approval_id", "approval_records", ["approval_id"])
    op.create_index("ix_approval_records_owner_role", "approval_records", ["owner_role"])
    op.create_index("ix_approval_records_requested_by", "approval_records", ["requested_by"])
    op.create_index("ix_approval_records_status", "approval_records", ["status"])
    op.create_index("ix_approval_records_tenant_id", "approval_records", ["tenant_id"])
    op.create_index("ix_approval_records_workflow_id", "approval_records", ["workflow_id"])

    op.create_table(
        "action_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("action_id", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("execution_mode", sa.String(length=80), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("approval_id", sa.String(length=160), nullable=True),
        sa.Column("workflow_id", sa.String(length=160), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "action_id",
            "idempotency_key",
            name="uq_action_runs_tenant_action_idempotency",
        ),
    )
    op.create_index("ix_action_runs_action_id", "action_runs", ["action_id"])
    op.create_index("ix_action_runs_approval_id", "action_runs", ["approval_id"])
    op.create_index("ix_action_runs_idempotency_key", "action_runs", ["idempotency_key"])
    op.create_index("ix_action_runs_requested_by", "action_runs", ["requested_by"])
    op.create_index("ix_action_runs_status", "action_runs", ["status"])
    op.create_index("ix_action_runs_tenant_id", "action_runs", ["tenant_id"])
    op.create_index("ix_action_runs_workflow_id", "action_runs", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_action_runs_workflow_id", table_name="action_runs")
    op.drop_index("ix_action_runs_tenant_id", table_name="action_runs")
    op.drop_index("ix_action_runs_status", table_name="action_runs")
    op.drop_index("ix_action_runs_requested_by", table_name="action_runs")
    op.drop_index("ix_action_runs_idempotency_key", table_name="action_runs")
    op.drop_index("ix_action_runs_approval_id", table_name="action_runs")
    op.drop_index("ix_action_runs_action_id", table_name="action_runs")
    op.drop_table("action_runs")

    op.drop_index("ix_approval_records_workflow_id", table_name="approval_records")
    op.drop_index("ix_approval_records_tenant_id", table_name="approval_records")
    op.drop_index("ix_approval_records_status", table_name="approval_records")
    op.drop_index("ix_approval_records_requested_by", table_name="approval_records")
    op.drop_index("ix_approval_records_owner_role", table_name="approval_records")
    op.drop_index("ix_approval_records_approval_id", table_name="approval_records")
    op.drop_index("ix_approval_records_action_id", table_name="approval_records")
    op.drop_table("approval_records")
