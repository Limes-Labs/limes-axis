"""Unit tests for the TypeDB ontology mutation runtime.

These exercise the live mutation runtime through an injected fake client (the
same lazy-driver seam used by the read-path tests), so no running TypeDB is
required. The real round-trip is covered by the AXIS_RUN_INTEGRATION test.
"""

import pytest

from axis_api.ontology.mutations import (
    DeferredOntologyMutationRuntime,
    OntologyMutationError,
    OntologyMutationRequest,
    TypeDBOntologyMutationConfig,
    TypeDBOntologyMutationRuntime,
)


def _request(node_id: str = "asset_line_2_packaging") -> OntologyMutationRequest:
    return OntologyMutationRequest(
        tenant_id="tenant_demo_manufacturing",
        connector_id="file_csv_manufacturing_assets",
        promotion_id="promote_asset_line_2_packaging_20260622",
        proposal_id="proposal_asset_line_2_packaging",
        manual_import_id="import_assets_manual_20260622",
        actor_id="plant-operations-owner-role",
        node_id=node_id,
        node_type="asset",
        ontology_type="manufacturing_asset",
        field_summary={
            "asset_name": "Line 2 Packaging",
            "domain": "Operations",
            "station": "Line 2",
            "risk_level": "high",
        },
        evidence_refs=["manufacturing-assets-demo.csv"],
    )


class FakeOntologyClient:
    """In-memory stand-in for OntologyClient keyed on axis_id.

    Models the idempotency contract of the put-pipeline: a given node_id is only
    stored once regardless of how many times the same write is applied.
    """

    def __init__(self) -> None:
        self.config = TypeDBOntologyMutationConfig()
        self.writes: list[str] = []
        self.reads: list[str] = []
        self._nodes: set[str] = set()
        self.fail_write: Exception | None = None
        self.fail_read: Exception | None = None
        self.drop_on_read = False

    def execute_write(self, query_text: str) -> None:
        if self.fail_write is not None:
            raise self.fail_write
        self.writes.append(query_text)
        # The identity anchor is the first put stage; extract the axis_id.
        for line in query_text.splitlines():
            if line.startswith('put $asset isa axis_asset, has axis_id "'):
                node_id = line.split('has axis_id "', 1)[1].rstrip('";')
                self._nodes.add(node_id)

    def execute_read(self, query_text: str) -> list[dict[str, object]]:
        self.reads.append(query_text)
        if self.fail_read is not None:
            raise self.fail_read
        node_id = query_text.split('has axis_id "', 1)[1].split('"', 1)[0]
        if self.drop_on_read or node_id not in self._nodes:
            return []
        return [{"axis_id": node_id}]


def _runtime_with(client: FakeOntologyClient) -> TypeDBOntologyMutationRuntime:
    runtime = TypeDBOntologyMutationRuntime(TypeDBOntologyMutationConfig())
    runtime.client = client
    return runtime


def test_typeql_is_deterministic_and_idempotent_put_pipeline() -> None:
    request = _request()
    first = request.typeql
    assert first == request.typeql  # deterministic for a given proposal
    assert first.startswith('put $asset isa axis_asset, has axis_id "asset_line_2_packaging";')
    # One object per put stage (the documented safe, idempotent form).
    assert "insert" not in first
    assert first.count("put ") == 6  # identity + asset_type + 4 field attributes
    assert 'put $asset has display_name "Line 2 Packaging";' in first
    assert 'put $asset has source_system_ref "Line 2";' in first


def test_promote_applies_and_reads_back() -> None:
    client = FakeOntologyClient()
    result = _runtime_with(client).promote_connector_proposal(_request())

    assert result.status == "type_db_mutation_applied"
    assert result.payload["verified"] is True
    assert result.mutation_ref == "typedb://axis/asset_line_2_packaging"
    assert len(client.writes) == 1
    assert len(client.reads) == 1


def test_repromotion_is_idempotent_single_logical_node() -> None:
    client = FakeOntologyClient()
    runtime = _runtime_with(client)

    runtime.promote_connector_proposal(_request())
    runtime.promote_connector_proposal(_request())

    # The same node_id is only ever stored once (put match-or-insert).
    assert client._nodes == {"asset_line_2_packaging"}
    assert client.writes[0] == client.writes[1]


def test_write_failure_is_unavailable_and_skips_read_back() -> None:
    client = FakeOntologyClient()
    client.fail_write = TimeoutError("connection refused")
    with pytest.raises(OntologyMutationError) as exc_info:
        _runtime_with(client).promote_connector_proposal(_request())

    assert exc_info.value.status == "type_db_mutation_unavailable"
    assert client.reads == []  # fail-closed: never claim success


def test_read_back_error_is_unavailable() -> None:
    client = FakeOntologyClient()
    client.fail_read = RuntimeError("driver reset")
    with pytest.raises(OntologyMutationError) as exc_info:
        _runtime_with(client).promote_connector_proposal(_request())

    assert exc_info.value.status == "type_db_mutation_unavailable"


def test_missing_node_on_read_back_is_failed() -> None:
    client = FakeOntologyClient()
    client.drop_on_read = True  # write "succeeds" but node cannot be observed
    with pytest.raises(OntologyMutationError) as exc_info:
        _runtime_with(client).promote_connector_proposal(_request())

    assert exc_info.value.status == "type_db_mutation_failed"
    assert "verification_missing_node" in str(exc_info.value)


def test_deferred_runtime_writes_nothing() -> None:
    result = DeferredOntologyMutationRuntime().promote_connector_proposal(_request())

    assert result.status == "type_db_mutation_deferred"
    assert result.mutation_ref is None
    # Deferred still surfaces the TypeQL it would have run for auditability.
    assert result.typeql.startswith("put $asset isa axis_asset")
