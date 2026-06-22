"""connector runs

Revision ID: 0006_connector_runs
Revises: 0005_connector_credential_handles
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_connector_runs"
down_revision: str | None = "0005_connector_credential_handles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("run_id", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("execution_mode", sa.String(length=80), nullable=False),
        sa.Column("runtime_boundary", sa.String(length=160), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("credential_handle_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_id", name="uq_connector_runs_tenant_run"),
    )
    op.create_index("ix_connector_runs_audit_event_type", "connector_runs", ["audit_event_type"])
    op.create_index("ix_connector_runs_connector_id", "connector_runs", ["connector_id"])
    op.create_index("ix_connector_runs_execution_mode", "connector_runs", ["execution_mode"])
    op.create_index("ix_connector_runs_requested_by", "connector_runs", ["requested_by"])
    op.create_index("ix_connector_runs_run_id", "connector_runs", ["run_id"])
    op.create_index("ix_connector_runs_status", "connector_runs", ["status"])
    op.create_index("ix_connector_runs_tenant_id", "connector_runs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_connector_runs_tenant_id", table_name="connector_runs")
    op.drop_index("ix_connector_runs_status", table_name="connector_runs")
    op.drop_index("ix_connector_runs_run_id", table_name="connector_runs")
    op.drop_index("ix_connector_runs_requested_by", table_name="connector_runs")
    op.drop_index("ix_connector_runs_execution_mode", table_name="connector_runs")
    op.drop_index("ix_connector_runs_connector_id", table_name="connector_runs")
    op.drop_index("ix_connector_runs_audit_event_type", table_name="connector_runs")
    op.drop_table("connector_runs")
