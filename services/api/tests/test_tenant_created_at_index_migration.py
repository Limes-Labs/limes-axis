import importlib.util
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session

from axis_api.models import AuditEvent, Base
from axis_api.persistence import AxisPersistenceRepository

EXPECTED = {
    "ix_audit_events_tenant_created": ("audit_events", ["tenant_id", "created_at", "id"]),
    "ix_audit_events_tenant_event_type_created": (
        "audit_events",
        ["tenant_id", "event_type", "created_at", "id"],
    ),
    "ix_action_runs_tenant_created": ("action_runs", ["tenant_id", "created_at", "id"]),
    "ix_connector_runs_tenant_created": ("connector_runs", ["tenant_id", "created_at", "id"]),
    "ix_approval_records_tenant_created": ("approval_records", ["tenant_id", "created_at"]),
}


@pytest.fixture
def migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations/versions/0069_tenant_created_at_list_indexes.py"
    )
    spec = importlib.util.spec_from_file_location("tenant_created_at_index_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_declares_exactly_the_expected_indexes(migration) -> None:
    assert {
        name: (table, list(columns)) for name, table, columns in migration.INDEXES
    } == EXPECTED
    assert migration.down_revision == "0068_search_index_records"


@pytest.mark.parametrize("direction,statement", [
    ("upgrade", "CREATE INDEX CONCURRENTLY"),
    ("downgrade", "DROP INDEX CONCURRENTLY"),
])
def test_postgres_index_ddl_runs_outside_a_transaction(
    migration, monkeypatch, direction, statement,
) -> None:
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    with context.begin_transaction():
        getattr(migration, direction)()
    sql = output.getvalue()
    assert sql.count(statement) == len(EXPECTED)
    in_transaction = False
    seen = 0
    for line in sql.splitlines():
        if line.startswith("BEGIN;"):
            in_transaction = True
        elif line.startswith("COMMIT;"):
            in_transaction = False
        elif line.startswith(statement):
            assert not in_transaction, line
            seen += 1
    assert seen == len(EXPECTED)
    # The surrounding migration transaction resumes after the autocommit block.
    assert "BEGIN;" in sql.rsplit(statement, 1)[1]


def test_index_upgrade_and_downgrade_preserve_rows(migration, monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite://")
    tables = sorted({table for table, _columns in EXPECTED.values()})
    try:
        with engine.connect() as connection:
            for table in tables:
                connection.execute(text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, "
                    "event_type TEXT, created_at TIMESTAMP NOT NULL)"
                ))
                connection.execute(text(
                    f"INSERT INTO {table} VALUES (1, 'tenant-a', 'x', '2026-10-19 00:00:00')"
                ))
            connection.commit()
            context = MigrationContext.configure(connection)
            monkeypatch.setattr(migration, "op", Operations(context))
            with context.begin_transaction():
                migration.upgrade()
            inspector = inspect(connection)
            for name, (table, columns) in EXPECTED.items():
                assert any(
                    item["name"] == name and item["column_names"] == columns
                    for item in inspector.get_indexes(table)
                )
            connection.commit()
            with context.begin_transaction():
                migration.downgrade()
            inspector = inspect(connection)
            for table in tables:
                assert not inspector.get_indexes(table)
                assert connection.execute(text(f"SELECT id FROM {table}")).all() == [(1,)]
    finally:
        engine.dispose()


def test_models_declare_the_migrated_indexes() -> None:
    declared = {
        index.name: (table.name, [column.name for column in index.columns])
        for table in Base.metadata.sorted_tables
        for index in table.indexes
    }
    for name, expected in EXPECTED.items():
        assert declared.get(name) == expected


def _plans_for_audit_reads(event_type: str | None) -> list[str]:
    engine = create_engine("sqlite+pysqlite://")
    Base.metadata.create_all(engine)
    plans: list[str] = []
    try:
        with Session(engine) as session:
            base = datetime(2026, 10, 19, tzinfo=UTC)
            session.add_all(
                AuditEvent(
                    id=uuid4(),
                    tenant_id=f"tenant-{index % 4}",
                    actor_id="actor",
                    event_type=f"event.{index % 3}",
                    payload={},
                    created_at=base + timedelta(seconds=index),
                )
                for index in range(400)
            )
            session.commit()
            session.execute(text("ANALYZE"))

            @event.listens_for(engine, "before_cursor_execute")
            def explain(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT") and "audit_events" in statement:
                    rows = conn.exec_driver_sql(
                        f"EXPLAIN QUERY PLAN {statement}", parameters
                    ).all()
                    plans.append(" | ".join(str(row[-1]) for row in rows))

            rows = AxisPersistenceRepository(session).list_audit_events(
                "tenant-1", event_type=event_type, limit=10
            )
            assert len(rows) == 10
            assert [row.created_at for row in rows] == sorted(
                (row.created_at for row in rows), reverse=True
            )
    finally:
        engine.dispose()
    return plans


@pytest.mark.parametrize(
    "event_type,index_name",
    [
        (None, "ix_audit_events_tenant_created"),
        ("event.1", "ix_audit_events_tenant_event_type_created"),
    ],
)
def test_tenant_audit_list_reads_the_composite_index_without_a_sort(
    event_type: str | None, index_name: str
) -> None:
    plans = _plans_for_audit_reads(event_type)

    assert plans, "list_audit_events issued no SELECT"
    plan = plans[-1]
    assert index_name in plan
    assert "TEMP B-TREE" not in plan
