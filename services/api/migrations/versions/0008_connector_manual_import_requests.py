"""connector manual import requests

Revision ID: 0008_connector_manual_import_requests
Revises: 0007_connector_ontology_proposals
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_connector_manual_import_requests"
down_revision: str | None = "0007_connector_ontology_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_manual_import_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("import_id", sa.String(length=180), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("import_mode", sa.String(length=80), nullable=False),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("owner_role", sa.String(length=160), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("approval_id", sa.String(length=160), nullable=False),
        sa.Column("workflow_id", sa.String(length=160), nullable=False),
        sa.Column("proposal_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("import_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("controls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_mutation_status", sa.String(length=80), nullable=False),
        sa.Column("workflow_signal_status", sa.String(length=80), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "import_id",
            name="uq_connector_manual_import_requests_tenant_import",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_connector_manual_import_requests_tenant_idempotency",
        ),
    )
    for column_name in (
        "audit_event_type",
        "connector_id",
        "graph_mutation_status",
        "idempotency_key",
        "import_id",
        "import_mode",
        "owner_role",
        "requested_by",
        "risk_level",
        "status",
        "tenant_id",
        "workflow_id",
        "workflow_signal_status",
        "approval_id",
    ):
        op.create_index(
            f"ix_connector_manual_import_requests_{column_name}",
            "connector_manual_import_requests",
            [column_name],
        )


def downgrade() -> None:
    table_name = "connector_manual_import_requests"
    for column_name in (
        "approval_id",
        "workflow_signal_status",
        "workflow_id",
        "tenant_id",
        "status",
        "risk_level",
        "requested_by",
        "owner_role",
        "import_mode",
        "import_id",
        "idempotency_key",
        "graph_mutation_status",
        "connector_id",
        "audit_event_type",
    ):
        op.drop_index(f"ix_connector_manual_import_requests_{column_name}", table_name=table_name)
    op.drop_table(table_name)
