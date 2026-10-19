"""Request-path TypeDB bounds (issue #942).

The request-path runtimes used the driver's default request timeout (two
hours), connected lazily without a lock, and asked the server whether the
database exists before every read.
"""

from __future__ import annotations

import sys
import threading
import time
import types

import pytest
from pydantic import ValidationError

from axis_api.config import Settings
from axis_api.main import create_app
from axis_api.ontology.client import OntologyClient, OntologyClientConfig
from axis_api.ontology.mutations import (
    TypeDBOntologyMutationConfig,
    TypeDBOntologyMutationRuntime,
)
from axis_api.ontology.queries import TypeDBOntologyQueryConfig, TypeDBOntologyQueryRuntime


class _FakeTransaction:
    def __init__(self) -> None:
        self.open = True

    def query(self, _text: str) -> _FakeTransaction:
        return self

    def resolve(self) -> list:
        return []

    def commit(self) -> None:
        self.open = False

    def is_open(self) -> bool:
        return self.open

    def close(self) -> None:
        self.open = False

    def rollback(self) -> None:
        self.open = False


class _FakeDatabases:
    def __init__(self) -> None:
        self.contains_calls = 0
        self.exists = True

    def contains(self, _name: str) -> bool:
        self.contains_calls += 1
        return self.exists

    def create(self, _name: str) -> None:
        self.exists = True


class _FakeDriver:
    def __init__(self) -> None:
        self.databases = _FakeDatabases()

    def transaction(self, _database: str, _kind: object) -> _FakeTransaction:
        return _FakeTransaction()

    def close(self) -> None:
        pass


@pytest.fixture
def fake_typedb(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace the driver dial with a slow fake and record every connect."""
    fake_package = types.ModuleType("typedb")
    fake_driver_module = types.ModuleType("typedb.driver")
    fake_driver_module.TransactionType = type(  # type: ignore[attr-defined]
        "TransactionType", (), {"READ": 0, "WRITE": 1, "SCHEMA": 2}
    )
    fake_package.driver = fake_driver_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "typedb", fake_package)
    monkeypatch.setitem(sys.modules, "typedb.driver", fake_driver_module)

    state: dict = {"connects": 0, "drivers": []}

    def connect(self: OntologyClient) -> None:
        state["connects"] += 1
        time.sleep(0.05)  # widen the race window between threads
        driver = _FakeDriver()
        state["drivers"].append(driver)
        self._driver = driver

    monkeypatch.setattr(OntologyClient, "connect", connect)
    return state


def test_request_path_runtimes_bound_the_typedb_request_timeout() -> None:
    query = TypeDBOntologyQueryRuntime(TypeDBOntologyQueryConfig())
    mutation = TypeDBOntologyMutationRuntime(TypeDBOntologyMutationConfig())

    assert query.client.config.request_timeout_millis == 10_000
    assert mutation.client.config.request_timeout_millis == 10_000


def test_typedb_request_timeout_setting_reaches_both_request_path_clients() -> None:
    settings = Settings(
        _env_file=None,
        postgres_dsn="sqlite+pysqlite://",
        ontology_queries_enabled=True,
        ontology_mutations_enabled=True,
        AXIS_TYPEDB_REQUEST_TIMEOUT_SECONDS=2.5,
    )

    app = create_app(settings)

    assert app.state.ontology_query_runtime.client.config.request_timeout_millis == 2_500
    assert app.state.ontology_mutation_runtime.client.config.request_timeout_millis == 2_500


@pytest.mark.parametrize("value", [0, -1, 301])
def test_typedb_request_timeout_is_bounded(value: float) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, AXIS_TYPEDB_REQUEST_TIMEOUT_SECONDS=value)


def test_concurrent_first_reads_share_one_driver_connect(fake_typedb: dict) -> None:
    client = OntologyClient(OntologyClientConfig(address="typedb:1729", username="u", password="p"))
    errors: list[BaseException] = []

    def read() -> None:
        try:
            client.execute_read("match $x isa thing;")
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=read) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert errors == []
    assert fake_typedb["connects"] == 1


def test_database_existence_is_checked_once_across_reads(fake_typedb: dict) -> None:
    client = OntologyClient(OntologyClientConfig(address="typedb:1729", username="u", password="p"))

    for _ in range(5):
        client.execute_read("match $x isa thing;")

    assert fake_typedb["drivers"][0].databases.contains_calls == 1


def test_database_existence_is_rechecked_after_a_failed_read(fake_typedb: dict) -> None:
    client = OntologyClient(OntologyClientConfig(address="typedb:1729", username="u", password="p"))
    client.execute_read("match $x isa thing;")
    driver = fake_typedb["drivers"][0]

    def failing_transaction(_database: str, _kind: object) -> _FakeTransaction:
        raise RuntimeError("database dropped")

    driver.transaction = failing_transaction  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        client.execute_read("match $x isa thing;")
    del driver.transaction
    client.execute_read("match $x isa thing;")

    assert driver.databases.contains_calls == 2
