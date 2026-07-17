from __future__ import annotations

from pathlib import Path
from runpy import run_path

from sqlalchemy import Column, Constraint

from axis_api.models import ApprovalDecisionOutbox

MIGRATION_PATH = (
    Path(__file__).parents[1] / "migrations" / "versions" / "0054_approval_decision_outbox.py"
)


class RecordingOperations:
    def __init__(self) -> None:
        self.created_table: tuple[str, tuple[object, ...]] | None = None
        self.created_indexes: list[tuple[str, str, tuple[str, ...]]] = []

    def create_table(self, name: str, *items: object) -> None:
        self.created_table = (name, items)

    def create_index(self, name: str, table_name: str, columns: list[str]) -> None:
        self.created_indexes.append((name, table_name, tuple(columns)))


def test_migration_columns_constraints_and_indexes_match_the_orm_model() -> None:
    migration = run_path(str(MIGRATION_PATH))
    operations = RecordingOperations()
    migration["upgrade"].__globals__["op"] = operations

    migration["upgrade"]()

    assert migration["revision"] == "0054_approval_decision_outbox"
    assert migration["down_revision"] == "0053_usage_event_projection"
    assert operations.created_table is not None
    table_name, items = operations.created_table
    assert table_name == ApprovalDecisionOutbox.__tablename__

    migration_columns = {item.name for item in items if isinstance(item, Column)}
    model_columns = set(ApprovalDecisionOutbox.__table__.columns.keys())
    assert migration_columns == model_columns

    migration_constraints = {
        item.name for item in items if isinstance(item, Constraint) and item.name is not None
    }
    model_constraints = {
        item.name
        for item in ApprovalDecisionOutbox.__table__.constraints
        if item.name is not None
    }
    assert migration_constraints == model_constraints

    migration_indexes = {name for name, _, _ in operations.created_indexes}
    model_indexes = {index.name for index in ApprovalDecisionOutbox.__table__.indexes}
    assert migration_indexes == model_indexes
    assert all(
        indexed_table == ApprovalDecisionOutbox.__tablename__
        for _, indexed_table, _ in operations.created_indexes
    )
