"""connector live sync single-active checkpoint claim index

Revision ID: 0045_connector_live_sync_claim
Revises: 0044_platform_policies
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0045_connector_live_sync_claim"
down_revision: str | None = "0044_platform_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_conn_sync_claims_single_active"
TABLE_NAME = "connector_sync_checkpoint_claims"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        TABLE_NAME,
        ["tenant_id", "checkpoint_id"],
        unique=True,
        postgresql_where=text("status = 'claimed'"),
        sqlite_where=text("status = 'claimed'"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
