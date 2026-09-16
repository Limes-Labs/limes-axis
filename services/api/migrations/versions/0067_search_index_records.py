"""Bounded full-text search index projection table.

Revision ID: 0067_search_index_records
Revises: 0066_s3_source_checkpoint
"""

import sqlalchemy as sa
from alembic import op

revision = "0067_search_index_records"
down_revision = "0066_s3_source_checkpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_index_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("source_object_id", sa.String(length=220), nullable=False, index=True),
        sa.Column("content_revision", sa.String(length=220), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, index=True),
        sa.Column("searchable_text", sa.Text(), nullable=True),
        sa.Column("text_digest", sa.String(length=64), nullable=True),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("analyzer_revision", sa.String(length=200), nullable=False),
        sa.Column("policy_revision_ref", sa.String(length=200), nullable=False),
        sa.Column("index_generation", sa.Integer(), nullable=False),
        sa.Column("indexed_event_type", sa.String(length=120), nullable=False),
        sa.Column("indexed_audit_event_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "source_object_id",
            name="uq_search_index_records_tenant_object",
        ),
        sa.CheckConstraint(
            "kind IN ('ontology_asset', 'document')",
            name="ck_search_index_records_kind",
        ),
        sa.CheckConstraint(
            "state IN ('live', 'tombstoned')",
            name="ck_search_index_records_state",
        ),
        sa.CheckConstraint(
            "(state = 'live' AND searchable_text IS NOT NULL AND text_digest IS NOT NULL) "
            "OR (state = 'tombstoned' AND searchable_text IS NULL AND text_digest IS NULL)",
            name="ck_search_index_records_text_state",
        ),
        sa.CheckConstraint(
            "index_generation >= 1",
            name="ck_search_index_records_generation",
        ),
    )
    op.create_index(
        "ix_search_index_records_tenant_state",
        "search_index_records",
        ["tenant_id", "state", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_search_index_records_tenant_state",
        table_name="search_index_records",
    )
    op.drop_table("search_index_records")
