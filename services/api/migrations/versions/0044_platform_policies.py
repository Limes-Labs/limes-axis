"""platform policies

Revision ID: 0044_platform_policies
Revises: 0043_oidc_browser_sessions
Create Date: 2026-07-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0044_platform_policies"
down_revision: str | None = "0043_oidc_browser_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("policy_id", sa.String(length=180), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=600), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("effect", sa.String(length=80), nullable=False),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("required_authoring_scope", sa.String(length=160), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("revises_revision_number", sa.Integer(), nullable=True),
        sa.Column("replaced_by_revision_number", sa.Integer(), nullable=True),
        sa.Column("revision_idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "policy_id",
            "revision_number",
            name="uq_platform_policies_tenant_policy_revision",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "revision_idempotency_key",
            name="uq_platform_policies_tenant_revision_idempotency",
        ),
    )
    for column_name in (
        "tenant_id",
        "policy_id",
        "policy_version",
        "scope",
        "effect",
        "status",
        "created_by",
        "audit_event_type",
        "revision_idempotency_key",
    ):
        op.create_index(
            f"ix_platform_policies_{column_name}",
            "platform_policies",
            [column_name],
        )
    op.create_index(
        "uq_platform_policies_tenant_policy_active",
        "platform_policies",
        ["tenant_id", "policy_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_platform_policies_tenant_policy_active",
        table_name="platform_policies",
    )
    for column_name in (
        "revision_idempotency_key",
        "audit_event_type",
        "created_by",
        "status",
        "effect",
        "scope",
        "policy_version",
        "policy_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_platform_policies_{column_name}",
            table_name="platform_policies",
        )
    op.drop_table("platform_policies")
