"""connector evidence snapshot export materializations

Revision ID: 0040_connector_evidence_snapshot_export_materializations
Revises: 0039_connector_evidence_snapshot_export_request_decisions
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_connector_evidence_snapshot_export_materializations"
down_revision: str | None = "0039_connector_evidence_snapshot_export_request_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_evidence_snapshot_export_requests"
    op.add_column(table_name, sa.Column("materialization_id", sa.String(180), nullable=True))
    op.add_column(
        table_name,
        sa.Column("materialization_idempotency_key", sa.String(200), nullable=True),
    )
    op.add_column(table_name, sa.Column("materialized_by", sa.String(160), nullable=True))
    op.add_column(
        table_name,
        sa.Column("materialized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(table_name, sa.Column("materialization_reason", sa.String(240), nullable=True))
    op.add_column(table_name, sa.Column("storage_adapter", sa.String(80), nullable=True))
    op.add_column(table_name, sa.Column("storage_key", sa.String(500), nullable=True))
    op.add_column(table_name, sa.Column("storage_uri", sa.String(700), nullable=True))
    op.add_column(table_name, sa.Column("artifact_checksum_sha256", sa.String(64), nullable=True))
    op.add_column(table_name, sa.Column("artifact_size_bytes", sa.Integer(), nullable=True))
    op.add_column(table_name, sa.Column("artifact_content_type", sa.String(120), nullable=True))
    for column_name in (
        "materialization_id",
        "materialization_idempotency_key",
        "materialized_by",
        "storage_adapter",
        "artifact_checksum_sha256",
    ):
        op.create_index(
            f"ix_connector_evidence_snapshot_export_requests_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_evidence_snapshot_export_requests"
    for column_name in (
        "artifact_checksum_sha256",
        "storage_adapter",
        "materialized_by",
        "materialization_idempotency_key",
        "materialization_id",
    ):
        op.drop_index(
            f"ix_connector_evidence_snapshot_export_requests_{column_name}",
            table_name=table_name,
        )
    op.drop_column(table_name, "artifact_content_type")
    op.drop_column(table_name, "artifact_size_bytes")
    op.drop_column(table_name, "artifact_checksum_sha256")
    op.drop_column(table_name, "storage_uri")
    op.drop_column(table_name, "storage_key")
    op.drop_column(table_name, "storage_adapter")
    op.drop_column(table_name, "materialization_reason")
    op.drop_column(table_name, "materialized_at")
    op.drop_column(table_name, "materialized_by")
    op.drop_column(table_name, "materialization_idempotency_key")
    op.drop_column(table_name, "materialization_id")
