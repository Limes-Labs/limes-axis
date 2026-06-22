"""connector credential leases

Revision ID: 0020_connector_credential_leases
Revises: 0019_connector_manifests
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_connector_credential_leases"
down_revision: str | None = "0019_connector_manifests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_credential_leases"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("handle_id", sa.String(length=160), nullable=False),
        sa.Column("lease_id", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("lease_mode", sa.String(length=120), nullable=False),
        sa.Column("runtime_boundary", sa.String(length=160), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("lease_purpose", sa.String(length=160), nullable=False),
        sa.Column("secret_provider", sa.String(length=120), nullable=False),
        sa.Column("secret_ref", sa.String(length=500), nullable=False),
        sa.Column("vault_kms_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lease_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("renewal_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("renewed_by", sa.String(length=160), nullable=True),
        sa.Column("renewal_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=160), nullable=True),
        sa.Column("revocation_reason", sa.String(length=600), nullable=True),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "lease_id",
            name="uq_connector_credential_leases_tenant_lease",
        ),
    )
    for column_name in (
        "audit_event_type",
        "connector_id",
        "expires_at",
        "handle_id",
        "lease_id",
        "lease_mode",
        "lease_purpose",
        "renewal_due_at",
        "renewed_by",
        "requested_by",
        "revoked_by",
        "status",
        "tenant_id",
    ):
        op.create_index(f"ix_connector_credential_leases_{column_name}", table_name, [column_name])


def downgrade() -> None:
    table_name = "connector_credential_leases"
    for column_name in (
        "tenant_id",
        "status",
        "revoked_by",
        "requested_by",
        "renewed_by",
        "renewal_due_at",
        "lease_purpose",
        "lease_mode",
        "lease_id",
        "handle_id",
        "expires_at",
        "connector_id",
        "audit_event_type",
    ):
        op.drop_index(f"ix_connector_credential_leases_{column_name}", table_name=table_name)
    op.drop_table(table_name)
