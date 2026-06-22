"""connector promotion policy enforcement

Revision ID: 0012_connector_promotion_policy_enforcement
Revises: 0011_connector_promotion_policies
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_connector_promotion_policy_enforcement"
down_revision: str | None = "0011_connector_promotion_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    proposal_table = "connector_ontology_proposals"
    op.add_column(
        proposal_table,
        sa.Column("policy_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        proposal_table,
        sa.Column("policy_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_connector_ontology_proposals_policy_id", proposal_table, ["policy_id"])

    promotion_table = "connector_ontology_promotions"
    op.add_column(
        promotion_table,
        sa.Column("policy_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        promotion_table,
        sa.Column("policy_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_connector_ontology_promotions_policy_id", promotion_table, ["policy_id"])


def downgrade() -> None:
    promotion_table = "connector_ontology_promotions"
    op.drop_index("ix_connector_ontology_promotions_policy_id", table_name=promotion_table)
    op.drop_column(promotion_table, "policy_decision")
    op.drop_column(promotion_table, "policy_id")

    proposal_table = "connector_ontology_proposals"
    op.drop_index("ix_connector_ontology_proposals_policy_id", table_name=proposal_table)
    op.drop_column(proposal_table, "policy_decision")
    op.drop_column(proposal_table, "policy_id")
