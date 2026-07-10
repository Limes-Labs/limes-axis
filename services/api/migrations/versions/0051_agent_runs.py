"""agent runs and agent run steps

Revision ID: 0051_agent_runs
Revises: 0050_model_endpoints_and_invocations
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0051_agent_runs"
down_revision: str | None = "0050_model_endpoints_and_invocations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("autonomy_level", sa.String(length=8), nullable=False),
        sa.Column(
            "request_fingerprint",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("context_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "model_invocation_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("proposed_action_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "permission_decision",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "platform_policy_decision",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_reason", sa.String(length=240), nullable=True),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "agent_id",
            "idempotency_key",
            name="uq_agent_runs_tenant_agent_idempotency",
        ),
    )
    for column_name in (
        "tenant_id",
        "agent_id",
        "idempotency_key",
        "status",
        "mode",
        "requested_by",
        "autonomy_level",
        "proposed_action_run_id",
        "error_reason",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_agent_runs_{column_name}",
            "agent_runs",
            [column_name],
        )
    # Composite index backing the newest-first per-agent listing keyset.
    op.create_index(
        "ix_agent_runs_tenant_agent_created_at",
        "agent_runs",
        ["tenant_id", "agent_id", "created_at"],
    )

    op.create_table(
        "agent_run_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "run_id",
            "seq",
            name="uq_agent_run_steps_tenant_run_seq",
        ),
    )
    for column_name in (
        "tenant_id",
        "run_id",
        "step_type",
        "status",
    ):
        op.create_index(
            f"ix_agent_run_steps_{column_name}",
            "agent_run_steps",
            [column_name],
        )


def downgrade() -> None:
    for column_name in (
        "status",
        "step_type",
        "run_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_agent_run_steps_{column_name}",
            table_name="agent_run_steps",
        )
    op.drop_table("agent_run_steps")
    op.drop_index(
        "ix_agent_runs_tenant_agent_created_at",
        table_name="agent_runs",
    )
    for column_name in (
        "audit_event_type",
        "error_reason",
        "proposed_action_run_id",
        "autonomy_level",
        "requested_by",
        "mode",
        "status",
        "idempotency_key",
        "agent_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_agent_runs_{column_name}",
            table_name="agent_runs",
        )
    op.drop_table("agent_runs")
