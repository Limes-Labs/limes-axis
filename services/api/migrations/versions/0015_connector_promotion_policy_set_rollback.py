"""connector promotion policy set rollback

Revision ID: 0015_connector_promotion_policy_set_rollback
Revises: 0014_connector_promotion_policy_set_replacement
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_connector_promotion_policy_set_rollback"
down_revision: str | None = "0014_connector_promotion_policy_set_replacement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_promotion_policy_sets"
    op.add_column(
        table_name,
        sa.Column("rollback_to_policy_set_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("rollback_approval_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("rollback_decision", sa.String(length=40), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("rollback_workflow_signal_status", sa.String(length=120), nullable=True),
    )
    for column_name in (
        "rollback_approval_id",
        "rollback_to_policy_set_id",
    ):
        op.create_index(
            f"ix_connector_promotion_policy_sets_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_promotion_policy_sets"
    for column_name in (
        "rollback_to_policy_set_id",
        "rollback_approval_id",
    ):
        op.drop_index(f"ix_connector_promotion_policy_sets_{column_name}", table_name=table_name)
    op.drop_column(table_name, "rollback_workflow_signal_status")
    op.drop_column(table_name, "rollback_decision")
    op.drop_column(table_name, "rollback_approval_id")
    op.drop_column(table_name, "rollback_to_policy_set_id")
