from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.demo import ManufacturingOntology, get_manufacturing_ontology
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.ontology.queries import (
    DeferredOntologyQueryRuntime,
    OntologyGraphQueryMetadata,
    OntologyGraphQueryRequest,
    query_manufacturing_ontology_graph,
)
from axis_api.permissions import PermissionDecision


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


class RecordingOntologyQueryRuntime:
    adapter_name = "axis-recording-ontology-query-adapter"

    def __init__(self) -> None:
        self.requests: list[OntologyGraphQueryRequest] = []

    def query_manufacturing_graph(
        self,
        request: OntologyGraphQueryRequest,
    ) -> ManufacturingOntology:
        self.requests.append(request)
        ontology = get_manufacturing_ontology()
        return ontology.model_copy(
            update={
                "graph_query": OntologyGraphQueryMetadata(
                    adapter=self.adapter_name,
                    source="recording-test-runtime",
                    query_mode="permission_filtered",
                    tenant_id=request.tenant_id,
                    actor_id=request.actor_id,
                    permission_decision=PermissionDecision(
                        allowed=True,
                        reason="recording_runtime_allowed",
                    ),
                    requested_scopes=request.actor_scopes,
                    applied_relationship_scopes=["operations:read"],
                    denied_relationship_count=0,
                    returned_node_count=len(ontology.nodes),
                    returned_relationship_count=len(ontology.relationships),
                    typeql=request.typeql,
                    notes=["Recording runtime used by API test."],
                )
            }
        )


def test_deferred_ontology_query_runtime_filters_relationships_by_scope() -> None:
    runtime = DeferredOntologyQueryRuntime()

    ontology = query_manufacturing_ontology_graph(
        runtime,
        OntologyGraphQueryRequest(
            tenant_id="tenant_demo_manufacturing",
            actor_id="operations-reader",
            actor_scopes=["operations:read"],
            enforce_relationship_scopes=True,
        ),
    )

    assert ontology.graph_query.adapter == "axis-deferred-ontology-query-adapter"
    assert ontology.graph_query.query_mode == "permission_filtered"
    assert ontology.graph_query.permission_decision.allowed is True
    assert ontology.graph_query.applied_relationship_scopes == ["operations:read"]
    assert ontology.graph_query.denied_relationship_count > 0
    assert {relationship.permission_scope for relationship in ontology.relationships} == {
        "operations:read"
    }
    assert "rel_supplier_batch_impacts_line" not in {
        relationship.relationship_id for relationship in ontology.relationships
    }
    assert "asset_line_2_packaging" in {node.node_id for node in ontology.nodes}
    assert "asset_motors_batch" not in {node.node_id for node in ontology.nodes}


def test_ontology_endpoint_uses_query_runtime_and_oidc_principal() -> None:
    app = create_app(Settings(oidc_auth_required=True))
    runtime = RecordingOntologyQueryRuntime()
    app.state.ontology_query_runtime = runtime
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="operations-reader",
            tenant_id="tenant_demo_manufacturing",
            scopes=["operations:read"],
        )
    )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/ontology",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["graph_query"]["adapter"] == "axis-recording-ontology-query-adapter"
    assert body["graph_query"]["actor_id"] == "operations-reader"
    assert body["graph_query"]["requested_scopes"] == ["operations:read"]
    assert runtime.requests[0].enforce_relationship_scopes is True
    assert runtime.requests[0].actor_scopes == ["operations:read"]


def test_ontology_endpoint_filters_graph_when_oidc_auth_required() -> None:
    app = create_app(Settings(oidc_auth_required=True))
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="operations-reader",
            tenant_id="tenant_demo_manufacturing",
            scopes=["operations:read"],
        )
    )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/ontology",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["graph_query"]["query_mode"] == "permission_filtered"
    assert body["graph_query"]["denied_relationship_count"] > 0
    assert {relationship["permission_scope"] for relationship in body["relationships"]} == {
        "operations:read"
    }
    assert "asset_motors_batch" not in str(body)


def test_ontology_endpoint_rejects_tenant_mismatch() -> None:
    app = create_app(Settings(oidc_auth_required=True))
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="operations-reader",
            tenant_id="tenant_demo_manufacturing",
            scopes=["operations:read"],
        )
    )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/ontology?tenant_id=tenant_other",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "tenant_mismatch"


def test_ontology_endpoint_allows_empty_filtered_graph() -> None:
    app = create_app(Settings(oidc_auth_required=True))
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="no-graph-scope-reader",
            tenant_id="tenant_demo_manufacturing",
            scopes=["profile:read"],
        )
    )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/ontology",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == []
    assert body["relationships"] == []
    assert body["graph_query"]["denied_relationship_count"] == 14


def test_ontology_openapi_allows_empty_filtered_graph_lists() -> None:
    app = create_app(Settings())
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()["components"]["schemas"]["ManufacturingOntology"]
    assert "minItems" not in schema["properties"]["nodes"]
    assert "minItems" not in schema["properties"]["relationships"]
