"""connector credential handles

Revision ID: 0005_connector_credential_handles
Revises: 0004_connector_configurations
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_connector_credential_handles"
down_revision: str | None = "0004_connector_configurations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_credential_handles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("handle_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("secret_provider", sa.String(length=120), nullable=False),
        sa.Column("secret_ref", sa.String(length=500), nullable=False),
        sa.Column("purpose", sa.String(length=160), nullable=False),
        sa.Column("rotation_interval_days", sa.Integer(), nullable=False),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_rotation_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("labels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "handle_id",
            name="uq_connector_credential_handles_tenant_handle",
        ),
    )
    op.create_index(
        "ix_connector_credential_handles_connector_id",
        "connector_credential_handles",
        ["connector_id"],
    )
    op.create_index(
        "ix_connector_credential_handles_created_by",
        "connector_credential_handles",
        ["created_by"],
    )
    op.create_index(
        "ix_connector_credential_handles_handle_id",
        "connector_credential_handles",
        ["handle_id"],
    )
    op.create_index(
        "ix_connector_credential_handles_next_rotation_due_at",
        "connector_credential_handles",
        ["next_rotation_due_at"],
    )
    op.create_index(
        "ix_connector_credential_handles_status",
        "connector_credential_handles",
        ["status"],
    )
    op.create_index(
        "ix_connector_credential_handles_tenant_id",
        "connector_credential_handles",
        ["tenant_id"],
    )

    op.create_table(
        "connector_credential_rotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("handle_id", sa.String(length=160), nullable=False),
        sa.Column("rotated_by", sa.String(length=160), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_ref", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_connector_credential_rotations_handle_id",
        "connector_credential_rotations",
        ["handle_id"],
    )
    op.create_index(
        "ix_connector_credential_rotations_rotated_by",
        "connector_credential_rotations",
        ["rotated_by"],
    )
    op.create_index(
        "ix_connector_credential_rotations_status",
        "connector_credential_rotations",
        ["status"],
    )
    op.create_index(
        "ix_connector_credential_rotations_tenant_id",
        "connector_credential_rotations",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_connector_credential_rotations_tenant_id",
        table_name="connector_credential_rotations",
    )
    op.drop_index(
        "ix_connector_credential_rotations_status",
        table_name="connector_credential_rotations",
    )
    op.drop_index(
        "ix_connector_credential_rotations_rotated_by",
        table_name="connector_credential_rotations",
    )
    op.drop_index(
        "ix_connector_credential_rotations_handle_id",
        table_name="connector_credential_rotations",
    )
    op.drop_table("connector_credential_rotations")

    op.drop_index(
        "ix_connector_credential_handles_tenant_id",
        table_name="connector_credential_handles",
    )
    op.drop_index(
        "ix_connector_credential_handles_status",
        table_name="connector_credential_handles",
    )
    op.drop_index(
        "ix_connector_credential_handles_next_rotation_due_at",
        table_name="connector_credential_handles",
    )
    op.drop_index(
        "ix_connector_credential_handles_handle_id",
        table_name="connector_credential_handles",
    )
    op.drop_index(
        "ix_connector_credential_handles_created_by",
        table_name="connector_credential_handles",
    )
    op.drop_index(
        "ix_connector_credential_handles_connector_id",
        table_name="connector_credential_handles",
    )
    op.drop_table("connector_credential_handles")
