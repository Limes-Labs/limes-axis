"""transactional approval decision workflow outbox

Revision ID: 0054_approval_decision_outbox
Revises: 0053_usage_event_projection
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0054_approval_decision_outbox"
down_revision: str | None = "0053_usage_event_projection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_decision_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("approval_id", sa.String(length=160), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("signal_name", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("decision_actor_id", sa.String(length=160), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'dispatching', 'delivered', 'dead_letter')",
            name="ck_approval_decision_outbox_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_approval_decision_outbox_attempt_count",
        ),
        sa.CheckConstraint(
            "(status = 'dispatching' AND claim_token IS NOT NULL AND claimed_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR (status <> 'dispatching' "
            "AND claim_token IS NULL AND claimed_at IS NULL AND lease_expires_at IS NULL)",
            name="ck_approval_decision_outbox_claim_state",
        ),
        sa.CheckConstraint(
            "(status = 'delivered' AND delivered_at IS NOT NULL AND dead_lettered_at IS NULL) "
            "OR (status <> 'delivered' AND delivered_at IS NULL)",
            name="ck_approval_decision_outbox_delivered_state",
        ),
        sa.CheckConstraint(
            "(status = 'dead_letter' AND dead_lettered_at IS NOT NULL AND delivered_at IS NULL) "
            "OR (status <> 'dead_letter' AND dead_lettered_at IS NULL)",
            name="ck_approval_decision_outbox_dead_letter_state",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "approval_id",
            name="uq_approval_decision_outbox_tenant_approval",
        ),
    )
    op.create_index(
        "ix_approval_decision_outbox_dispatch",
        "approval_decision_outbox",
        ["status", "available_at", "id"],
    )
    op.create_index(
        "ix_approval_decision_outbox_stale_claim",
        "approval_decision_outbox",
        ["status", "lease_expires_at", "id"],
    )
    for column in ("tenant_id", "approval_id", "workflow_id", "status", "claim_token"):
        op.create_index(
            f"ix_approval_decision_outbox_{column}",
            "approval_decision_outbox",
            [column],
        )


def downgrade() -> None:
    for column in ("claim_token", "status", "workflow_id", "approval_id", "tenant_id"):
        op.drop_index(
            f"ix_approval_decision_outbox_{column}",
            table_name="approval_decision_outbox",
        )
    op.drop_index(
        "ix_approval_decision_outbox_stale_claim",
        table_name="approval_decision_outbox",
    )
    op.drop_index(
        "ix_approval_decision_outbox_dispatch",
        table_name="approval_decision_outbox",
    )
    op.drop_table("approval_decision_outbox")
