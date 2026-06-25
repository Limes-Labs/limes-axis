"""connector sync checkpoint claims

Revision ID: 0036_connector_sync_checkpoint_claims
Revises: 0035_connector_sync_checkpoints
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036_connector_sync_checkpoint_claims"
down_revision: str | None = "0035_connector_sync_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_sync_checkpoint_claims"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("run_id", sa.String(length=180), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=220), nullable=False),
        sa.Column("claim_id", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("claimed_by", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("lease_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "claim_id",
            name="uq_connector_sync_checkpoint_claims_tenant_claim",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "checkpoint_id",
            "idempotency_key",
            name="uq_connector_sync_checkpoint_claims_tenant_checkpoint_idempotency",
        ),
    )
    for column_name in (
        "tenant_id",
        "connector_id",
        "run_id",
        "checkpoint_id",
        "claim_id",
        "status",
        "claimed_by",
        "idempotency_key",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_connector_sync_checkpoint_claims_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    op.drop_table("connector_sync_checkpoint_claims")
