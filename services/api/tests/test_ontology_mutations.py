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
    _verification_confirms_node,
)

_DEMO_KEY = "tenant_demo_manufacturing::asset_line_2_packaging"


def _request(
    node_id: str = "asset_line_2_packaging",
    tenant_id: str = "tenant_demo_manufacturing",
    field_summary: dict[str, str] | None = None,
) -> OntologyMutationRequest:
    return OntologyMutationRequest(
        tenant_id=tenant_id,
        connector_id="file_csv_manufacturing_assets",
        promotion_id="promote_asset_line_2_packaging_20260622",
        proposal_id="proposal_asset_line_2_packaging",
        manual_import_id="import_assets_manual_20260622",
        actor_id="plant-operations-owner-role",
        node_id=node_id,
        node_type="asset",
        ontology_type="manufacturing_asset",
        field_summary=field_summary
        or {
            "asset_name": "Line 2 Packaging",
            "domain": "Operations",
            "station": "Line 2",
            "risk_level": "high",
        },
        evidence_refs=["manufacturing-assets-demo.csv"],
    )


class FakeOntologyClient:
    """In-memory stand-in for OntologyClient keyed on the graph key (axis_id).

    Models the idempotency contract of the put-pipeline: a given graph key is
    only stored once regardless of how many times the same write is applied. By
    default the read-back returns the scalar shape produced by a TypeDB 3.x
    ``fetch { "axis_id": $asset.axis_id }`` projection; ``nested_read_shape``
    switches it to the nested ``{"value": ...}`` attribute-concept rendering.
    """

    def __init__(self) -> None:
        self.config = TypeDBOntologyMutationConfig()
        self.writes: list[str] = []
        self.reads: list[str] = []
        self._keys: set[str] = set()
        self.fail_write: Exception | None = None
        self.fail_read: Exception | None = None
        self.drop_on_read = False
        self.nested_read_shape = False

    def execute_write(self, query_text: str) -> None:
        if self.fail_write is not None:
            raise self.fail_write
        self.writes.append(query_text)
        # The identity anchor is the first put stage; extract the graph key.
        for line in query_text.splitlines():
            if line.startswith('put $asset isa axis_asset, has axis_id "'):
                graph_key = line.split('has axis_id "', 1)[1].rstrip('";')
                self._keys.add(graph_key)

    def execute_read(self, query_text: str) -> list[dict[str, object]]:
        self.reads.append(query_text)
        if self.fail_read is not None:
            raise self.fail_read
        graph_key = query_text.split('has axis_id "', 1)[1].split('"', 1)[0]
        if self.drop_on_read or graph_key not in self._keys:
            return []
        if self.nested_read_shape:
            return [
                {"axis_id": [{"value": graph_key, "value_type": "string"}]}
            ]
        return [{"axis_id": graph_key}]


def _runtime_with(client: FakeOntologyClient) -> TypeDBOntologyMutationRuntime:
    runtime = TypeDBOntologyMutationRuntime(TypeDBOntologyMutationConfig())
    runtime.client = client
    return runtime


def test_typeql_is_deterministic_and_idempotent_put_pipeline() -> None:
    request = _request()
    first = request.typeql
    assert first == request.typeql  # deterministic for a given proposal
    # Keyed on the tenant-namespaced graph key, not the bare node_id.
    assert first.startswith(f'put $asset isa axis_asset, has axis_id "{_DEMO_KEY}";')
    # One object per put stage (the documented safe, idempotent form).
    assert "insert" not in first
    assert first.count("put ") == 6  # identity + asset_type + 4 field attributes
    assert 'put $asset has display_name "Line 2 Packaging";' in first
    assert 'put $asset has source_system_ref "Line 2";' in first


def test_graph_key_is_tenant_namespaced_to_prevent_cross_tenant_convergence() -> None:
    # Same node_id, different tenants -> DIFFERENT graph keys / distinct nodes.
    tenant_a = _request(node_id="asset_1", tenant_id="tenant_a")
    tenant_b = _request(node_id="asset_1", tenant_id="tenant_b")
    assert tenant_a.graph_key == "tenant_a::asset_1"
    assert tenant_b.graph_key == "tenant_b::asset_1"
    assert tenant_a.graph_key != tenant_b.graph_key
    assert 'has axis_id "tenant_a::asset_1"' in tenant_a.typeql
    assert 'has axis_id "tenant_b::asset_1"' in tenant_b.typeql
    # The written @key identity differs, so a shared graph cannot merge them.
    assert tenant_a.typeql != tenant_b.typeql

    # Same tenant + same node_id -> identical key (within-tenant convergence).
    tenant_a_again = _request(node_id="asset_1", tenant_id="tenant_a")
    assert tenant_a.graph_key == tenant_a_again.graph_key
    assert tenant_a.typeql == tenant_a_again.typeql


def test_typeql_escapes_adversarial_connector_values() -> None:
    # node_id and field values are connector-controlled; verify they cannot break
    # out of the string literal / inject additional TypeQL statements.
    hostile = 'x" isa axis_actor; insert $e isa axis_actor, has axis_id "pwned'
    request = _request(
        node_id=hostile,
        field_summary={
            "asset_name": 'name"; delete $x; match $y\nhas axis_id "z',
            "risk_level": "back\\slash",
        },
    )
    typeql = request.typeql

    # Every user-controlled value stays inside an escaped double-quoted literal:
    # quotes are backslash-escaped and backslashes doubled, so no bare `"` closes
    # a literal early and no injected `insert`/`delete`/`match` becomes a clause.
    assert 'has axis_id "tenant_demo_manufacturing::x\\" isa axis_actor;' in typeql
    assert 'has display_name "name\\"; delete $x;' in typeql
    assert 'has risk_level "back\\\\slash";' in typeql
    # The statement count is exactly the intended pipeline (identity + asset_type
    # + asset_name + risk_level); injected keywords did not create new stages.
    assert typeql.count("put $asset") == 4
    # Injection invariant: after removing escaped backslashes and escaped quotes,
    # the only double-quotes left are the structural literal delimiters — two per
    # `has <attr> "<value>"` statement, i.e. 8 across the four put statements. If
    # any payload quote had escaped the literal, this count would be higher.
    structural_quotes = typeql.replace("\\\\", "").replace('\\"', "")
    assert structural_quotes.count('"') == 8


def test_promote_applies_and_reads_back() -> None:
    client = FakeOntologyClient()
    result = _runtime_with(client).promote_connector_proposal(_request())

    assert result.status == "type_db_mutation_applied"
    assert result.payload["verified"] is True
    assert result.payload["graph_key"] == _DEMO_KEY
    assert result.mutation_ref == f"typedb://axis/{_DEMO_KEY}"
    assert len(client.writes) == 1
    assert len(client.reads) == 1


def test_read_back_accepts_nested_attribute_concept_shape() -> None:
    # Robustness (F2): a driver rendering axis_id as {"value": ...} must still
    # verify a real committed write instead of a spurious type_db_mutation_failed.
    client = FakeOntologyClient()
    client.nested_read_shape = True
    result = _runtime_with(client).promote_connector_proposal(_request())
    assert result.status == "type_db_mutation_applied"


def test_verification_confirms_node_handles_scalar_list_and_nested_shapes() -> None:
    key = _DEMO_KEY
    assert _verification_confirms_node([{"axis_id": key}], key)
    assert _verification_confirms_node([{"axis_id": [key]}], key)
    assert _verification_confirms_node([{"axis_id": {"value": key}}], key)
    assert _verification_confirms_node(
        [{"axis_id": [{"value": key, "value_type": "string"}]}], key
    )
    assert not _verification_confirms_node([{"axis_id": "other"}], key)
    assert not _verification_confirms_node([], key)


def test_repromotion_is_idempotent_single_logical_node() -> None:
    client = FakeOntologyClient()
    runtime = _runtime_with(client)

    runtime.promote_connector_proposal(_request())
    runtime.promote_connector_proposal(_request())

    # The same graph key is only ever stored once (put match-or-insert).
    assert client._keys == {_DEMO_KEY}
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
