"""connector promotion policy set revision adoption

Revision ID: 0017_connector_promotion_policy_set_revision_adoption
Revises: 0016_connector_promotion_policy_revision
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_connector_promotion_policy_set_revision_adoption"
down_revision: str | None = "0016_connector_promotion_policy_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_promotion_policy_sets"
    op.add_column(
        table_name,
        sa.Column(
            "policy_revision_adoptions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column(table_name, "policy_revision_adoptions", server_default=None)


def downgrade() -> None:
    op.drop_column("connector_promotion_policy_sets", "policy_revision_adoptions")
