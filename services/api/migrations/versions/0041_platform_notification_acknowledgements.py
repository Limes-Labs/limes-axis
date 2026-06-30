"""platform notification acknowledgements

Revision ID: 0041_platform_notification_acknowledgements
Revises: 0040_connector_evidence_snapshot_export_materializations
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041_platform_notification_acknowledgements"
down_revision: str | None = "0040_connector_evidence_snapshot_export_materializations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_notification_acknowledgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("notification_id", sa.String(length=120), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=600), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("notification_title", sa.String(length=300), nullable=False),
        sa.Column("notification_category", sa.String(length=80), nullable=False),
        sa.Column("notification_severity", sa.String(length=40), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "notification_id",
            "actor_id",
            name="uq_platform_notification_ack_tenant_notification_actor",
        ),
    )
    for column_name in (
        "tenant_id",
        "notification_id",
        "actor_id",
        "state",
        "source",
        "notification_category",
        "notification_severity",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_platform_notification_acknowledgements_{column_name}",
            "platform_notification_acknowledgements",
            [column_name],
        )


def downgrade() -> None:
    for column_name in (
        "audit_event_type",
        "notification_severity",
        "notification_category",
        "source",
        "state",
        "actor_id",
        "notification_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_platform_notification_acknowledgements_{column_name}",
            table_name="platform_notification_acknowledgements",
        )
    op.drop_table("platform_notification_acknowledgements")
