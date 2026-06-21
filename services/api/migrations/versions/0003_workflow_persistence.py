"""workflow persistence

Revision ID: 0003_workflow_persistence
Revises: 0002_persistence_foundation
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_workflow_persistence"
down_revision: str | None = "0002_persistence_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("owner_role", sa.String(length=160), nullable=False),
        sa.Column("runtime", sa.String(length=120), nullable=False),
        sa.Column("adapter", sa.String(length=120), nullable=False),
        sa.Column("autonomy_level", sa.String(length=8), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("eta", sa.String(length=120), nullable=False),
        sa.Column("blocker", sa.String(length=600), nullable=True),
        sa.Column("objective", sa.String(length=1000), nullable=False),
        sa.Column("current_step", sa.String(length=200), nullable=False),
        sa.Column("related_risk", sa.String(length=160), nullable=False),
        sa.Column("related_assets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposed_outputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pending_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("controls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_scope", sa.String(length=160), nullable=False),
        sa.Column("replay_ready", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workflow_id",
            name="uq_workflow_runs_tenant_workflow",
        ),
    )
    op.create_index("ix_workflow_runs_audit_scope", "workflow_runs", ["audit_scope"])
    op.create_index("ix_workflow_runs_domain", "workflow_runs", ["domain"])
    op.create_index("ix_workflow_runs_owner_role", "workflow_runs", ["owner_role"])
    op.create_index("ix_workflow_runs_state", "workflow_runs", ["state"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_index("ix_workflow_runs_tenant_id", "workflow_runs", ["tenant_id"])
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])

    op.create_table(
        "workflow_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("result", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "workflow_id",
            "sequence",
            name="uq_workflow_timeline_tenant_workflow_sequence",
        ),
    )
    op.create_index("ix_workflow_timeline_events_actor", "workflow_timeline_events", ["actor"])
    op.create_index("ix_workflow_timeline_events_event", "workflow_timeline_events", ["event"])
    op.create_index(
        "ix_workflow_timeline_events_tenant_id",
        "workflow_timeline_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_workflow_timeline_events_workflow_id",
        "workflow_timeline_events",
        ["workflow_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_timeline_events_workflow_id",
        table_name="workflow_timeline_events",
    )
    op.drop_index(
        "ix_workflow_timeline_events_tenant_id",
        table_name="workflow_timeline_events",
    )
    op.drop_index("ix_workflow_timeline_events_event", table_name="workflow_timeline_events")
    op.drop_index("ix_workflow_timeline_events_actor", table_name="workflow_timeline_events")
    op.drop_table("workflow_timeline_events")

    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_tenant_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_state", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_owner_role", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_domain", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_audit_scope", table_name="workflow_runs")
    op.drop_table("workflow_runs")
