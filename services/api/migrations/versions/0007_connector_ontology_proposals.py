"""connector ontology proposals

Revision ID: 0007_connector_ontology_proposals
Revises: 0006_connector_runs
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_connector_ontology_proposals"
down_revision: str | None = "0006_connector_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_ontology_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("connector_id", sa.String(length=160), nullable=False),
        sa.Column("proposal_id", sa.String(length=180), nullable=False),
        sa.Column("source_run_id", sa.String(length=180), nullable=True),
        sa.Column("source_file_name", sa.String(length=240), nullable=False),
        sa.Column("mapping_profile", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("write_mode", sa.String(length=80), nullable=False),
        sa.Column("graph_mutation_status", sa.String(length=80), nullable=False),
        sa.Column("proposed_by", sa.String(length=160), nullable=False),
        sa.Column("node_id", sa.String(length=180), nullable=False),
        sa.Column("node_type", sa.String(length=80), nullable=False),
        sa.Column("ontology_type", sa.String(length=160), nullable=False),
        sa.Column("field_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "proposal_id",
            name="uq_connector_ontology_proposals_tenant_proposal",
        ),
    )
    op.create_index(
        "ix_connector_ontology_proposals_audit_event_type",
        "connector_ontology_proposals",
        ["audit_event_type"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_connector_id",
        "connector_ontology_proposals",
        ["connector_id"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_graph_mutation_status",
        "connector_ontology_proposals",
        ["graph_mutation_status"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_mapping_profile",
        "connector_ontology_proposals",
        ["mapping_profile"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_node_id",
        "connector_ontology_proposals",
        ["node_id"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_node_type",
        "connector_ontology_proposals",
        ["node_type"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_ontology_type",
        "connector_ontology_proposals",
        ["ontology_type"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_proposal_id",
        "connector_ontology_proposals",
        ["proposal_id"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_proposed_by",
        "connector_ontology_proposals",
        ["proposed_by"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_source_run_id",
        "connector_ontology_proposals",
        ["source_run_id"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_status",
        "connector_ontology_proposals",
        ["status"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_tenant_id",
        "connector_ontology_proposals",
        ["tenant_id"],
    )
    op.create_index(
        "ix_connector_ontology_proposals_write_mode",
        "connector_ontology_proposals",
        ["write_mode"],
    )


def downgrade() -> None:
    table_name = "connector_ontology_proposals"
    index_names = (
        "ix_connector_ontology_proposals_write_mode",
        "ix_connector_ontology_proposals_tenant_id",
        "ix_connector_ontology_proposals_status",
        "ix_connector_ontology_proposals_source_run_id",
        "ix_connector_ontology_proposals_proposed_by",
        "ix_connector_ontology_proposals_proposal_id",
        "ix_connector_ontology_proposals_ontology_type",
        "ix_connector_ontology_proposals_node_type",
        "ix_connector_ontology_proposals_node_id",
        "ix_connector_ontology_proposals_mapping_profile",
        "ix_connector_ontology_proposals_graph_mutation_status",
        "ix_connector_ontology_proposals_connector_id",
        "ix_connector_ontology_proposals_audit_event_type",
    )
    for index_name in index_names:
        op.drop_index(index_name, table_name=table_name)
    op.drop_table(table_name)
