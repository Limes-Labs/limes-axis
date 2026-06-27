"""connector evidence snapshot export requests

Revision ID: 0038_connector_evidence_snapshot_export_requests
Revises: 0037_connector_sync_checkpoint_claim_lifecycle
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_connector_evidence_snapshot_export_requests"
down_revision: str | None = "0037_connector_sync_checkpoint_claim_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_evidence_snapshot_export_requests"
    op.create_table(
        table_name,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("export_request_id", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("export_status", sa.String(length=80), nullable=False),
        sa.Column("storage_status", sa.String(length=80), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("owner_role", sa.String(length=160), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("approval_id", sa.String(length=160), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=True),
        sa.Column("snapshot_id", sa.String(length=180), nullable=True),
        sa.Column("snapshot_idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("export_reason", sa.String(length=160), nullable=False),
        sa.Column("format", sa.String(length=40), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("requested_snapshot_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("redaction_policy", sa.String(length=120), nullable=False),
        sa.Column("controls", sa.JSON(), nullable=False),
        sa.Column("permission_decision", sa.JSON(), nullable=False),
        sa.Column("workflow_signal_status", sa.String(length=80), nullable=False),
        sa.Column("audit_event_id", sa.Uuid(), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "export_request_id",
            name="uq_connector_evidence_snapshot_export_requests_tenant_request",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_conn_evidence_export_req_tenant_idem",
        ),
    )
    for column_name in (
        "tenant_id",
        "export_request_id",
        "idempotency_key",
        "status",
        "export_status",
        "storage_status",
        "requested_by",
        "owner_role",
        "risk_level",
        "approval_id",
        "workflow_id",
        "connector_id",
        "snapshot_id",
        "snapshot_idempotency_key",
        "snapshot_checksum_sha256",
        "workflow_signal_status",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_conn_evidence_export_req_{column_name}",
            table_name,
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_evidence_snapshot_export_requests"
    for column_name in (
        "audit_event_type",
        "workflow_signal_status",
        "snapshot_checksum_sha256",
        "snapshot_idempotency_key",
        "snapshot_id",
        "connector_id",
        "workflow_id",
        "approval_id",
        "risk_level",
        "owner_role",
        "requested_by",
        "storage_status",
        "export_status",
        "status",
        "idempotency_key",
        "export_request_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_conn_evidence_export_req_{column_name}",
            table_name=table_name,
        )
    op.drop_table(table_name)
