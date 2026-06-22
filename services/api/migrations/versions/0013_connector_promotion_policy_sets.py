"""connector promotion policy sets

Revision ID: 0013_connector_promotion_policy_sets
Revises: 0012_connector_promotion_policy_enforcement
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_connector_promotion_policy_sets"
down_revision: str | None = "0012_connector_promotion_policy_enforcement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_promotion_policy_sets"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("policy_set_id", sa.String(length=180), nullable=False),
        sa.Column("policy_set_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("activated_by", sa.String(length=160), nullable=False),
        sa.Column("activation_scope", sa.String(length=160), nullable=False),
        sa.Column("policy_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("activation_reason", sa.String(length=600), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "policy_set_id",
            name="uq_connector_promotion_policy_sets_tenant_set",
        ),
    )
    for column_name in (
        "activated_by",
        "audit_event_type",
        "connector_id",
        "policy_set_id",
        "policy_set_version",
        "status",
        "tenant_id",
    ):
        op.create_index(
            f"ix_connector_promotion_policy_sets_{column_name}",
            table_name,
            [column_name],
        )

    proposal_table = "connector_ontology_proposals"
    op.add_column(
        proposal_table,
        sa.Column("policy_set_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        proposal_table,
        sa.Column("policy_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_connector_ontology_proposals_policy_set_id",
        proposal_table,
        ["policy_set_id"],
    )

    promotion_table = "connector_ontology_promotions"
    op.add_column(
        promotion_table,
        sa.Column("policy_set_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        promotion_table,
        sa.Column("policy_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_connector_ontology_promotions_policy_set_id",
        promotion_table,
        ["policy_set_id"],
    )


def downgrade() -> None:
    promotion_table = "connector_ontology_promotions"
    op.drop_index("ix_connector_ontology_promotions_policy_set_id", table_name=promotion_table)
    op.drop_column(promotion_table, "policy_ids")
    op.drop_column(promotion_table, "policy_set_id")

    proposal_table = "connector_ontology_proposals"
    op.drop_index("ix_connector_ontology_proposals_policy_set_id", table_name=proposal_table)
    op.drop_column(proposal_table, "policy_ids")
    op.drop_column(proposal_table, "policy_set_id")

    table_name = "connector_promotion_policy_sets"
    for column_name in (
        "tenant_id",
        "status",
        "policy_set_version",
        "policy_set_id",
        "connector_id",
        "audit_event_type",
        "activated_by",
    ):
        op.drop_index(f"ix_connector_promotion_policy_sets_{column_name}", table_name=table_name)
    op.drop_table(table_name)
