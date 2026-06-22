"""connector manifests

Revision ID: 0019_connector_manifests
Revises: 0018_replay_simulation_outputs
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_connector_manifests"
down_revision: str | None = "0018_replay_simulation_outputs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table_name = "connector_manifests"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("connector_type", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("runtime_boundary", sa.String(length=160), nullable=False),
        sa.Column("registered_by", sa.String(length=160), nullable=False),
        sa.Column("manifest_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("runtime_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preview_sample", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "connector_id",
            name="uq_connector_manifests_tenant_connector",
        ),
    )
    for column_name in (
        "audit_event_type",
        "connector_id",
        "connector_type",
        "registered_by",
        "source_type",
        "status",
        "tenant_id",
    ):
        op.create_index(f"ix_connector_manifests_{column_name}", table_name, [column_name])


def downgrade() -> None:
    table_name = "connector_manifests"
    for column_name in (
        "tenant_id",
        "status",
        "source_type",
        "registered_by",
        "connector_type",
        "connector_id",
        "audit_event_type",
    ):
        op.drop_index(f"ix_connector_manifests_{column_name}", table_name=table_name)
    op.drop_table(table_name)
