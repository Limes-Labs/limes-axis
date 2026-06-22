import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from axis_api.config import Settings
from axis_api.ontology.client import OntologyClient, OntologyClientConfig

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


def test_postgres_migration_creates_foundation_tables() -> None:
    upgrade(Config("alembic.ini"), "head")

    engine = create_engine(Settings().postgres_dsn)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {
        "tenants",
        "actors",
        "audit_events",
        "approval_records",
        "action_runs",
        "connector_configurations",
        "connector_credential_handles",
        "connector_credential_rotations",
        "connector_runs",
    }.issubset(tables)


def test_typedb_schema_loads_into_fresh_database() -> None:
    database = f"axis_integration_{uuid4().hex}"
    client = OntologyClient(
        OntologyClientConfig(
            address=Settings().typedb_address,
            username=Settings().typedb_username,
            password=Settings().typedb_password,
            database=database,
        )
    )
    try:
        schema_text = Path("src/axis_api/ontology/schema.tql").read_text(encoding="utf-8")
        client.load_schema(schema_text)
        loaded_schema = client.schema()
        assert "entity axis_actor" in loaded_schema
        assert "relation axis_requires_approval" in loaded_schema
    finally:
        client.drop_database()
        client.close()
