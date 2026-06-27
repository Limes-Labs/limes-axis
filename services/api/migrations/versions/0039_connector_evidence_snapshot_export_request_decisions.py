"""connector evidence snapshot export request decisions

Revision ID: 0039_connector_evidence_snapshot_export_request_decisions
Revises: 0038_connector_evidence_snapshot_export_requests
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_connector_evidence_snapshot_export_request_decisions"
down_revision: str | None = "0038_connector_evidence_snapshot_export_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_evidence_snapshot_export_requests"
    op.add_column(table_name, sa.Column("decision", sa.String(length=40), nullable=True))
    op.add_column(
        table_name,
        sa.Column("decision_actor_id", sa.String(length=160), nullable=True),
    )
    op.add_column(table_name, sa.Column("decision_note", sa.String(length=600), nullable=True))
    op.add_column(table_name, sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table_name, sa.Column("workflow_signal", sa.JSON(), nullable=True))
    op.create_index(
        "ix_connector_evidence_snapshot_export_requests_decision",
        table_name,
        ["decision"],
    )
    op.create_index(
        "ix_connector_evidence_snapshot_export_requests_decision_actor_id",
        table_name,
        ["decision_actor_id"],
    )


def downgrade() -> None:
    table_name = "connector_evidence_snapshot_export_requests"
    op.drop_index(
        "ix_connector_evidence_snapshot_export_requests_decision_actor_id",
        table_name=table_name,
    )
    op.drop_index(
        "ix_connector_evidence_snapshot_export_requests_decision",
        table_name=table_name,
    )
    op.drop_column(table_name, "workflow_signal")
    op.drop_column(table_name, "decided_at")
    op.drop_column(table_name, "decision_note")
    op.drop_column(table_name, "decision_actor_id")
    op.drop_column(table_name, "decision")
