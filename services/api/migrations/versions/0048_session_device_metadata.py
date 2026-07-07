"""session device metadata

Revision ID: 0048_session_device_metadata
Revises: 0047_tenant_lifecycle
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_session_device_metadata"
down_revision: str | None = "0047_tenant_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "oidc_browser_sessions",
        sa.Column("user_agent", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "oidc_browser_sessions",
        sa.Column("client_ip", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "oidc_browser_sessions",
        sa.Column("device_label", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("oidc_browser_sessions", "device_label")
    op.drop_column("oidc_browser_sessions", "client_ip")
    op.drop_column("oidc_browser_sessions", "user_agent")
