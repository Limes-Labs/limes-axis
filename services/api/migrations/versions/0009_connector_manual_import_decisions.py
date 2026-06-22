"""connector manual import decisions

Revision ID: 0009_connector_manual_import_decisions
Revises: 0008_connector_manual_import_requests
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_connector_manual_import_decisions"
down_revision: str | None = "0008_connector_manual_import_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_manual_import_requests"
    op.add_column(table_name, sa.Column("decision", sa.String(length=40), nullable=True))
    op.add_column(
        table_name,
        sa.Column("decision_actor_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column("decision_note", sa.String(length=600), nullable=True),
    )
    op.add_column(table_name, sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        table_name,
        sa.Column("workflow_signal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    for column_name in ("decision", "decision_actor_id"):
        op.create_index(
            f"ix_connector_manual_import_requests_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_manual_import_requests"
    for column_name in ("decision_actor_id", "decision"):
        op.drop_index(f"ix_connector_manual_import_requests_{column_name}", table_name=table_name)
    for column_name in (
        "workflow_signal",
        "decided_at",
        "decision_note",
        "decision_actor_id",
        "decision",
    ):
        op.drop_column(table_name, column_name)
