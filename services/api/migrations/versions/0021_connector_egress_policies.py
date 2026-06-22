"""connector egress policies

Revision ID: 0021_connector_egress_policies
Revises: 0020_connector_credential_leases
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_connector_egress_policies"
down_revision: str | None = "0020_connector_credential_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_egress_policies"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("policy_id", sa.String(length=180), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("connection_profile_id", sa.String(length=180), nullable=False),
        sa.Column("egress_boundary", sa.String(length=120), nullable=False),
        sa.Column("policy_mode", sa.String(length=120), nullable=False),
        sa.Column("runtime_boundary", sa.String(length=160), nullable=False),
        sa.Column("private_endpoint_ref", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("policy_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "policy_id",
            name="uq_connector_egress_policies_tenant_policy",
        ),
    )
    for column_name in (
        "audit_event_type",
        "connection_profile_id",
        "connector_id",
        "created_by",
        "egress_boundary",
        "policy_id",
        "policy_mode",
        "status",
        "tenant_id",
    ):
        op.create_index(f"ix_connector_egress_policies_{column_name}", table_name, [column_name])


def downgrade() -> None:
    table_name = "connector_egress_policies"
    for column_name in (
        "tenant_id",
        "status",
        "policy_mode",
        "policy_id",
        "egress_boundary",
        "created_by",
        "connector_id",
        "connection_profile_id",
        "audit_event_type",
    ):
        op.drop_index(f"ix_connector_egress_policies_{column_name}", table_name=table_name)
    op.drop_table(table_name)
