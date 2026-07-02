"""oidc browser sessions

Revision ID: 0043_oidc_browser_sessions
Revises: 0042_ontology_relationship_metadata
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043_oidc_browser_sessions"
down_revision: str | None = "0042_ontology_relationship_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oidc_browser_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id_hash", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=160), nullable=True),
        sa.Column("revocation_reason", sa.String(length=240), nullable=True),
        sa.Column("revoke_audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id_hash",
            name="uq_oidc_browser_sessions_session_id_hash",
        ),
    )
    for column_name in (
        "tenant_id",
        "actor_id",
        "status",
        "revoked_by",
    ):
        op.create_index(
            f"ix_oidc_browser_sessions_{column_name}",
            "oidc_browser_sessions",
            [column_name],
        )


def downgrade() -> None:
    for column_name in (
        "revoked_by",
        "status",
        "actor_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_oidc_browser_sessions_{column_name}",
            table_name="oidc_browser_sessions",
        )
    op.drop_table("oidc_browser_sessions")
