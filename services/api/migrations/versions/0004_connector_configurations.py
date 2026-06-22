"""connector configurations

Revision ID: 0004_connector_configurations
Revises: 0003_workflow_persistence
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_connector_configurations"
down_revision: str | None = "0003_workflow_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("sync_mode", sa.String(length=80), nullable=False),
        sa.Column("runtime_boundary", sa.String(length=160), nullable=False),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("configuration_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("credential_ref_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "connector_id",
            name="uq_connector_configurations_tenant_connector",
        ),
    )
    op.create_index(
        "ix_connector_configurations_connector_id",
        "connector_configurations",
        ["connector_id"],
    )
    op.create_index(
        "ix_connector_configurations_created_by",
        "connector_configurations",
        ["created_by"],
    )
    op.create_index("ix_connector_configurations_status", "connector_configurations", ["status"])
    op.create_index(
        "ix_connector_configurations_sync_mode",
        "connector_configurations",
        ["sync_mode"],
    )
    op.create_index(
        "ix_connector_configurations_tenant_id",
        "connector_configurations",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_connector_configurations_tenant_id", table_name="connector_configurations")
    op.drop_index("ix_connector_configurations_sync_mode", table_name="connector_configurations")
    op.drop_index("ix_connector_configurations_status", table_name="connector_configurations")
    op.drop_index("ix_connector_configurations_created_by", table_name="connector_configurations")
    op.drop_index("ix_connector_configurations_connector_id", table_name="connector_configurations")
    op.drop_table("connector_configurations")
