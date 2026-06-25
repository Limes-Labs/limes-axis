"""connector sync checkpoints

Revision ID: 0035_connector_sync_checkpoints
Revises: 0034_audit_legal_holds
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035_connector_sync_checkpoints"
down_revision: str | None = "0034_audit_legal_holds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_sync_checkpoints"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("run_id", sa.String(length=180), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=220), nullable=False),
        sa.Column("checkpoint_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("runtime_boundary", sa.String(length=160), nullable=False),
        sa.Column("adapter", sa.String(length=160), nullable=False),
        sa.Column("cursor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "checkpoint_id",
            name="uq_connector_sync_checkpoints_tenant_checkpoint",
        ),
    )
    for column_name in (
        "tenant_id",
        "connector_id",
        "run_id",
        "checkpoint_id",
        "checkpoint_type",
        "status",
        "adapter",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_connector_sync_checkpoints_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    op.drop_table("connector_sync_checkpoints")
