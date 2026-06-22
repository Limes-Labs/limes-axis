"""connector promotion policy set replacement

Revision ID: 0014_connector_promotion_policy_set_replacement
Revises: 0013_connector_promotion_policy_sets
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_connector_promotion_policy_set_replacement"
down_revision: str | None = "0013_connector_promotion_policy_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_promotion_policy_sets"
    op.add_column(
        table_name,
        sa.Column("replaces_policy_set_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("replaced_by_policy_set_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("replacement_approval_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("replacement_decision", sa.String(length=40), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("replacement_workflow_signal_status", sa.String(length=120), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column_name in (
        "replaced_by_policy_set_id",
        "replacement_approval_id",
        "replaces_policy_set_id",
    ):
        op.create_index(
            f"ix_connector_promotion_policy_sets_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_promotion_policy_sets"
    for column_name in (
        "replaces_policy_set_id",
        "replacement_approval_id",
        "replaced_by_policy_set_id",
    ):
        op.drop_index(f"ix_connector_promotion_policy_sets_{column_name}", table_name=table_name)
    op.drop_column(table_name, "replaced_at")
    op.drop_column(table_name, "replacement_workflow_signal_status")
    op.drop_column(table_name, "replacement_decision")
    op.drop_column(table_name, "replacement_approval_id")
    op.drop_column(table_name, "replaced_by_policy_set_id")
    op.drop_column(table_name, "replaces_policy_set_id")
