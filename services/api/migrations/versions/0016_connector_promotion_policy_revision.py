"""connector promotion policy revision

Revision ID: 0016_connector_promotion_policy_revision
Revises: 0015_connector_promotion_policy_set_rollback
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_connector_promotion_policy_revision"
down_revision: str | None = "0015_connector_promotion_policy_set_rollback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_promotion_policies"
    op.add_column(
        table_name,
        sa.Column("revises_policy_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("replaced_by_policy_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("revision_idempotency_key", sa.String(length=200), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("revision_approval_id", sa.String(length=180), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("revision_decision", sa.String(length=40), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("revision_workflow_signal_status", sa.String(length=120), nullable=True),
    )
    for column_name in (
        "replaced_by_policy_id",
        "revises_policy_id",
        "revision_approval_id",
        "revision_idempotency_key",
    ):
        op.create_index(
            f"ix_connector_promotion_policies_{column_name}",
            table_name,
            [column_name],
        )
    op.create_unique_constraint(
        "uq_connector_promotion_policies_tenant_revision_idempotency",
        table_name,
        ["tenant_id", "revision_idempotency_key"],
    )


def downgrade() -> None:
    table_name = "connector_promotion_policies"
    op.drop_constraint(
        "uq_connector_promotion_policies_tenant_revision_idempotency",
        table_name,
        type_="unique",
    )
    for column_name in (
        "revision_idempotency_key",
        "revision_approval_id",
        "revises_policy_id",
        "replaced_by_policy_id",
    ):
        op.drop_index(f"ix_connector_promotion_policies_{column_name}", table_name=table_name)
    op.drop_column(table_name, "revision_workflow_signal_status")
    op.drop_column(table_name, "revision_decision")
    op.drop_column(table_name, "revision_approval_id")
    op.drop_column(table_name, "revision_idempotency_key")
    op.drop_column(table_name, "replaced_by_policy_id")
    op.drop_column(table_name, "revises_policy_id")
