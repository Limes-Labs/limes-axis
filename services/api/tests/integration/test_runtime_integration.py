import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

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
        "audit_legal_holds",
        "approval_records",
        "action_runs",
        "connector_configurations",
        "connector_manifests",
        "connector_credential_handles",
        "connector_credential_rotations",
        "connector_runs",
        "demo_reference_records",
    }.issubset(tables)
    with engine.connect() as connection:
        overview_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'overview' "
                "AND reference_id = 'manufacturing-overview'"
            )
        ).scalar_one()
        connector_registry_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'connectors' "
                "AND reference_id = 'manufacturing-connector-registry'"
            )
        ).scalar_one()
        agent_registry_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'agents' "
                "AND reference_id = 'manufacturing-agent-registry'"
            )
        ).scalar_one()
        action_registry_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'actions' "
                "AND reference_id = 'manufacturing-action-registry'"
            )
        ).scalar_one()
        workflow_console_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'workflows' "
                "AND reference_id = 'manufacturing-workflow-console'"
            )
        ).scalar_one()
        approval_inbox_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'approvals' "
                "AND reference_id = 'manufacturing-approval-inbox'"
            )
        ).scalar_one()
        audit_explorer_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'audit' "
                "AND reference_id = 'manufacturing-audit-explorer'"
            )
        ).scalar_one()
        model_routing_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'model-routing' "
                "AND reference_id = 'manufacturing-model-routing'"
            )
        ).scalar_one()
        ontology_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM demo_reference_records "
                "WHERE tenant_id = 'tenant_demo_manufacturing' "
                "AND surface = 'ontology' "
                "AND reference_id = 'manufacturing-ontology'"
            )
        ).scalar_one()

    assert overview_count == 1
    assert connector_registry_count == 1
    assert agent_registry_count == 1
    assert action_registry_count == 1
    assert workflow_console_count == 1
    assert approval_inbox_count == 1
    assert audit_explorer_count == 1
    assert model_routing_count == 1
    assert ontology_count == 1


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
