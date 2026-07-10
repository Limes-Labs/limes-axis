"""Live TypeDB round-trip for connector ontology graph promotion.

Requires the local Docker runtime (TypeDB at localhost:1729) and
AXIS_RUN_INTEGRATION=1, exactly like the other external-datastore integration
tests. Not part of the default CI suite.
"""

import os
import uuid

import pytest

from axis_api.ontology.bootstrap import read_meta_ontology_schema
from axis_api.ontology.client import OntologyClient, OntologyClientConfig
from axis_api.ontology.mutations import (
    OntologyMutationRequest,
    TypeDBOntologyMutationConfig,
    TypeDBOntologyMutationRuntime,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]

_ADDRESS = os.getenv("AXIS_TYPEDB_ADDRESS", "localhost:1729")
_USERNAME = os.getenv("AXIS_TYPEDB_USERNAME", "admin")
_PASSWORD = os.getenv("AXIS_TYPEDB_PASSWORD", "password")


def _client(database: str) -> OntologyClient:
    return OntologyClient(
        OntologyClientConfig(
            address=_ADDRESS,
            username=_USERNAME,
            password=_PASSWORD,
            database=database,
        )
    )


def _request(node_id: str) -> OntologyMutationRequest:
    return OntologyMutationRequest(
        tenant_id="tenant_demo_manufacturing",
        connector_id="file_csv_manufacturing_assets",
        promotion_id="promote_integration",
        proposal_id="proposal_integration",
        manual_import_id="import_integration",
        actor_id="integration-actor",
        node_id=node_id,
        node_type="asset",
        ontology_type="manufacturing_asset",
        field_summary={
            "asset_name": "Integration Asset",
            "domain": "Operations",
            "station": "Line 9",
            "risk_level": "high",
        },
        evidence_refs=["integration.csv"],
    )


def test_promotion_writes_reads_back_and_is_idempotent() -> None:
    database = f"axis_it_{uuid.uuid4().hex[:10]}"
    node_id = f"asset_integration_{uuid.uuid4().hex[:8]}"

    schema_client = _client(database)
    try:
        schema_client.ensure_database()
        schema_client.load_schema(read_meta_ontology_schema())
    finally:
        schema_client.close()

    runtime = TypeDBOntologyMutationRuntime(
        TypeDBOntologyMutationConfig(
            address=_ADDRESS,
            username=_USERNAME,
            password=_PASSWORD,
            database=database,
        )
    )
    read_client = _client(database)
    try:
        first = runtime.promote_connector_proposal(_request(node_id))
        assert first.status == "type_db_mutation_applied"

        rows = read_client.execute_read(
            f'match $a isa axis_asset, has axis_id "{node_id}";'
            ' fetch { "axis_id": $a.axis_id };'
        )
        assert any(str(row.get("axis_id")) == node_id for row in rows if isinstance(row, dict))

        # Re-promote: must remain a single logical node (idempotent put).
        second = runtime.promote_connector_proposal(_request(node_id))
        assert second.status == "type_db_mutation_applied"
        count_rows = read_client.execute_read(
            f'match $a isa axis_asset, has axis_id "{node_id}";'
            " reduce $n = count;"
        )
        assert count_rows, "count query returned no rows"
    finally:
        read_client.close()
        drop_client = _client(database)
        try:
            drop_client.drop_database()
        finally:
            drop_client.close()
        runtime.client.close()
