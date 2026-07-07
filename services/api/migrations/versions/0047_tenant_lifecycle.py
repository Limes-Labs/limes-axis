"""tenant lifecycle

Revision ID: 0047_tenant_lifecycle
Revises: 0046_oidc_session_lifecycle
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0047_tenant_lifecycle"
down_revision: str | None = "0046_oidc_session_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "description",
            sa.String(length=600),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "created_by",
            sa.String(length=160),
            nullable=False,
            server_default="axis-bootstrap",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("bootstrap_admin_actor_id", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("provision_idempotency_key", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("suspended_by", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("suspension_reason", sa.String(length=600), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("reactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("reactivated_by", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "audit_event_type",
            sa.String(length=120),
            nullable=False,
            server_default="platform.tenant.bootstrapped",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "notes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    for column_name in (
        "status",
        "created_by",
        "bootstrap_admin_actor_id",
        "provision_idempotency_key",
        "suspended_by",
        "reactivated_by",
        "audit_event_type",
    ):
        op.create_index(f"ix_tenants_{column_name}", "tenants", [column_name])
    op.create_unique_constraint(
        "uq_tenants_provision_idempotency",
        "tenants",
        ["provision_idempotency_key"],
    )

    op.create_table(
        "tenant_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("quota_key", sa.String(length=80), nullable=False),
        sa.Column("quota_value", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(length=160), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "quota_key",
            name="uq_tenant_quotas_tenant_quota_key",
        ),
    )
    for column_name in (
        "tenant_id",
        "quota_key",
        "updated_by",
        "audit_event_type",
    ):
        op.create_index(f"ix_tenant_quotas_{column_name}", "tenant_quotas", [column_name])


def downgrade() -> None:
    for column_name in (
        "audit_event_type",
        "updated_by",
        "quota_key",
        "tenant_id",
    ):
        op.drop_index(f"ix_tenant_quotas_{column_name}", table_name="tenant_quotas")
    op.drop_table("tenant_quotas")

    op.drop_constraint("uq_tenants_provision_idempotency", "tenants", type_="unique")
    for column_name in (
        "audit_event_type",
        "reactivated_by",
        "suspended_by",
        "provision_idempotency_key",
        "bootstrap_admin_actor_id",
        "created_by",
        "status",
    ):
        op.drop_index(f"ix_tenants_{column_name}", table_name="tenants")
    for column_name in (
        "updated_at",
        "notes",
        "audit_event_type",
        "audit_event_id",
        "reactivated_by",
        "reactivated_at",
        "suspension_reason",
        "suspended_by",
        "suspended_at",
        "provision_idempotency_key",
        "bootstrap_admin_actor_id",
        "created_by",
        "status",
        "description",
    ):
        op.drop_column("tenants", column_name)
