"""oidc session lifecycle

Revision ID: 0046_oidc_session_lifecycle
Revises: 0045_connector_live_sync_claim
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_oidc_session_lifecycle"
down_revision: str | None = "0045_connector_live_sync_claim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "oidc_browser_sessions",
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "oidc_browser_sessions",
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
    )
    op.add_column(
        "oidc_browser_sessions",
        sa.Column(
            "refresh_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "oidc_browser_sessions",
        sa.Column("rotated_to_session_id_hash", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oidc_browser_sessions", "rotated_to_session_id_hash")
    op.drop_column("oidc_browser_sessions", "refresh_count")
    op.drop_column("oidc_browser_sessions", "refresh_token_ciphertext")
    op.drop_column("oidc_browser_sessions", "absolute_expires_at")
