"""audit legal holds

Revision ID: 0034_audit_legal_holds
Revises: 0033_manufacturing_risk_scenarios
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_audit_legal_holds"
down_revision: str | None = "0033_manufacturing_risk_scenarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "audit_legal_holds"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("hold_id", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=600), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=True),
        sa.Column("actor_id", sa.String(length=160), nullable=True),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("approved_by", sa.String(length=160), nullable=False),
        sa.Column("released_by", sa.String(length=160), nullable=True),
        sa.Column("release_reason", sa.String(length=600), nullable=True),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("release_audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "hold_id",
            name="uq_audit_legal_holds_tenant_hold",
        ),
    )
    for column_name in (
        "tenant_id",
        "hold_id",
        "status",
        "event_type",
        "actor_id",
        "requested_by",
        "approved_by",
        "released_by",
    ):
        op.create_index(f"ix_audit_legal_holds_{column_name}", table_name, [column_name])


def downgrade() -> None:
    op.drop_table("audit_legal_holds")
