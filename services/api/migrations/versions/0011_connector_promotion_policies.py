"""connector promotion policies

Revision ID: 0011_connector_promotion_policies
Revises: 0010_connector_ontology_promotions
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_connector_promotion_policies"
down_revision: str | None = "0010_connector_ontology_promotions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_promotion_policies"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("policy_id", sa.String(length=180), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("enforcement_mode", sa.String(length=80), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("required_authoring_scope", sa.String(length=160), nullable=False),
        sa.Column("required_scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("required_manual_import_status", sa.String(length=80), nullable=False),
        sa.Column("required_workflow_signal_status", sa.String(length=80), nullable=False),
        sa.Column("allowed_risk_levels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "allowed_ontology_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("review_window_hours", sa.Integer(), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "policy_id",
            name="uq_connector_promotion_policies_tenant_policy",
        ),
    )
    for column_name in (
        "audit_event_type",
        "connector_id",
        "created_by",
        "enforcement_mode",
        "policy_id",
        "policy_version",
        "status",
        "tenant_id",
    ):
        op.create_index(
            f"ix_connector_promotion_policies_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_promotion_policies"
    for column_name in (
        "tenant_id",
        "status",
        "policy_version",
        "policy_id",
        "enforcement_mode",
        "created_by",
        "connector_id",
        "audit_event_type",
    ):
        op.drop_index(f"ix_connector_promotion_policies_{column_name}", table_name=table_name)
    op.drop_table(table_name)
