"""connector sync checkpoint claim lifecycle

Revision ID: 0037_connector_sync_checkpoint_claim_lifecycle
Revises: 0036_connector_sync_checkpoint_claims
Create Date: 2026-06-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_connector_sync_checkpoint_claim_lifecycle"
down_revision: str | None = "0036_connector_sync_checkpoint_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_sync_checkpoint_claims"
    op.add_column(table_name, sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table_name, sa.Column("renewed_by", sa.String(length=160), nullable=True))
    op.add_column(
        table_name,
        sa.Column("renewal_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(table_name, sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table_name, sa.Column("released_by", sa.String(length=160), nullable=True))
    op.add_column(table_name, sa.Column("release_reason", sa.String(length=600), nullable=True))
    op.create_index(
        "ix_connector_sync_checkpoint_claims_renewed_by",
        table_name,
        ["renewed_by"],
    )
    op.create_index(
        "ix_connector_sync_checkpoint_claims_released_by",
        table_name,
        ["released_by"],
    )


def downgrade() -> None:
    table_name = "connector_sync_checkpoint_claims"
    op.drop_index("ix_connector_sync_checkpoint_claims_released_by", table_name=table_name)
    op.drop_index("ix_connector_sync_checkpoint_claims_renewed_by", table_name=table_name)
    op.drop_column(table_name, "release_reason")
    op.drop_column(table_name, "released_by")
    op.drop_column(table_name, "released_at")
    op.drop_column(table_name, "renewal_count")
    op.drop_column(table_name, "renewed_by")
    op.drop_column(table_name, "renewed_at")
