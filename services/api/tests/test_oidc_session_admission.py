from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from axis_api.persistence import AxisPersistenceRepository


def _repository_for_dialect(dialect_name: str) -> tuple[AxisPersistenceRepository, Mock]:
    session = Mock(spec=Session)
    session.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect_name)
    )
    return AxisPersistenceRepository(session), session


def test_postgres_oidc_session_admission_uses_transaction_advisory_lock() -> None:
    repository, session = _repository_for_dialect("postgresql")

    repository.acquire_oidc_session_admission_lock(
        tenant_id="tenant_acme",
        actor_id="operator@example.com",
    )

    statement = session.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "pg_advisory_xact_lock" in sql
    assert "hashtextextended" in sql
    assert any("tenant_acme" in str(value) for value in compiled.params.values())
    assert any("operator@example.com" in str(value) for value in compiled.params.values())


def test_sqlite_oidc_session_admission_relies_on_database_write_serialization() -> None:
    repository, session = _repository_for_dialect("sqlite")

    repository.acquire_oidc_session_admission_lock(
        tenant_id="tenant_demo_manufacturing",
        actor_id="plant-operations-owner-role",
    )

    session.execute.assert_not_called()


def test_unsupported_oidc_session_admission_dialect_fails_closed() -> None:
    repository, session = _repository_for_dialect("mysql")

    with pytest.raises(NotImplementedError, match="mysql"):
        repository.acquire_oidc_session_admission_lock(
            tenant_id="tenant_acme",
            actor_id="operator@example.com",
        )

    session.execute.assert_not_called()
