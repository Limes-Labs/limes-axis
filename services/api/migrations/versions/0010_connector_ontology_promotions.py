"""connector ontology promotions

Revision ID: 0010_connector_ontology_promotions
Revises: 0009_connector_manual_import_decisions
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_connector_ontology_promotions"
down_revision: str | None = "0009_connector_manual_import_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    proposal_table = "connector_ontology_proposals"
    op.add_column(
        proposal_table,
        sa.Column("promotion_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        proposal_table,
        sa.Column("promoted_by", sa.String(length=160), nullable=True),
    )
    op.add_column(proposal_table, sa.Column("promoted_at", sa.DateTime(timezone=True)))
    op.add_column(
        proposal_table,
        sa.Column("ontology_mutation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    for column_name in ("promotion_id", "promoted_by"):
        op.create_index(
            f"ix_connector_ontology_proposals_{column_name}",
            proposal_table,
            [column_name],
        )

    op.create_table(
        "connector_ontology_promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("promotion_id", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("proposal_id", sa.String(length=180), nullable=False),
        sa.Column("manual_import_id", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("promotion_mode", sa.String(length=80), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("graph_mutation_status", sa.String(length=80), nullable=False),
        sa.Column("ontology_mutation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permission_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "promotion_id",
            name="uq_connector_ontology_promotions_tenant_promotion",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_connector_ontology_promotions_tenant_idempotency",
        ),
    )
    for column_name in (
        "audit_event_type",
        "connector_id",
        "graph_mutation_status",
        "idempotency_key",
        "manual_import_id",
        "promotion_id",
        "promotion_mode",
        "proposal_id",
        "requested_by",
        "status",
        "tenant_id",
    ):
        op.create_index(
            f"ix_connector_ontology_promotions_{column_name}",
            "connector_ontology_promotions",
            [column_name],
        )


def downgrade() -> None:
    promotion_table = "connector_ontology_promotions"
    for column_name in (
        "tenant_id",
        "status",
        "requested_by",
        "proposal_id",
        "promotion_mode",
        "promotion_id",
        "manual_import_id",
        "idempotency_key",
        "graph_mutation_status",
        "connector_id",
        "audit_event_type",
    ):
        op.drop_index(f"ix_connector_ontology_promotions_{column_name}", table_name=promotion_table)
    op.drop_table(promotion_table)

    proposal_table = "connector_ontology_proposals"
    for column_name in ("promoted_by", "promotion_id"):
        op.drop_index(f"ix_connector_ontology_proposals_{column_name}", table_name=proposal_table)
    for column_name in ("ontology_mutation", "promoted_at", "promoted_by", "promotion_id"):
        op.drop_column(proposal_table, column_name)
