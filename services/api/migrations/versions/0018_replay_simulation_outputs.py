"""replay simulation outputs

Revision ID: 0018_replay_simulation_outputs
Revises: 0017_connector_promotion_policy_set_revision_adoption
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_replay_simulation_outputs"
down_revision: str | None = "0017_connector_promotion_policy_set_revision_adoption"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "replay_simulation_outputs"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("simulation_output_id", sa.String(length=180), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("artifact_id", sa.String(length=240), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("required_scope", sa.String(length=160), nullable=False),
        sa.Column("replay_mode", sa.String(length=80), nullable=False),
        sa.Column("determinism_status", sa.String(length=80), nullable=False),
        sa.Column("output_hash", sa.String(length=128), nullable=False),
        sa.Column("retention_window_days", sa.Integer(), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=600), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "simulation_output_id",
            name="uq_replay_simulation_outputs_tenant_output",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_replay_simulation_outputs_tenant_idempotency",
        ),
    )
    for column_name in (
        "artifact_id",
        "audit_event_type",
        "determinism_status",
        "idempotency_key",
        "output_hash",
        "replay_mode",
        "requested_by",
        "simulation_output_id",
        "status",
        "tenant_id",
        "workflow_id",
    ):
        op.create_index(
            f"ix_replay_simulation_outputs_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "replay_simulation_outputs"
    for column_name in (
        "workflow_id",
        "tenant_id",
        "status",
        "simulation_output_id",
        "requested_by",
        "replay_mode",
        "output_hash",
        "idempotency_key",
        "determinism_status",
        "audit_event_type",
        "artifact_id",
    ):
        op.drop_index(f"ix_replay_simulation_outputs_{column_name}", table_name=table_name)
    op.drop_table(table_name)
