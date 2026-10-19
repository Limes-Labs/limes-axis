"""composite tenant/created_at indexes for tenant-scoped list reads

Revision ID: 0069_tenant_created_at_list_indexes
Revises: 0068_search_index_records
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0069_tenant_created_at_list_indexes"
down_revision: str | None = "0068_search_index_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index name, table, columns). Every list read below filters on tenant_id and
# orders by created_at descending (with id as the tie-breaker where the query
# has one). With only single-column indexes the planner either walks the
# tenant's whole history and sorts it, or walks created_at across every tenant,
# so a read with a small LIMIT costs in proportion to the tenant's history or
# the deployment's. A composite index lets it read the first LIMIT entries.
INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_audit_events_tenant_created", "audit_events", ("tenant_id", "created_at", "id")),
    (
        "ix_audit_events_tenant_event_type_created",
        "audit_events",
        ("tenant_id", "event_type", "created_at", "id"),
    ),
    ("ix_action_runs_tenant_created", "action_runs", ("tenant_id", "created_at", "id")),
    ("ix_connector_runs_tenant_created", "connector_runs", ("tenant_id", "created_at", "id")),
    ("ix_approval_records_tenant_created", "approval_records", ("tenant_id", "created_at")),
)


def upgrade() -> None:
    # audit_events is append-only and the largest table in a live deployment.
    # Follow migrations 0053 and 0065: PostgreSQL builds each index outside a
    # transaction with CONCURRENTLY so inserts are not blocked for the scan.
    # SQLite has no CONCURRENTLY and builds a plain index.
    with op.get_context().autocommit_block():
        for name, table, columns in INDEXES:
            op.create_index(name, table, list(columns), postgresql_concurrently=True)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, table, _columns in reversed(INDEXES):
            op.drop_index(name, table_name=table, postgresql_concurrently=True)
