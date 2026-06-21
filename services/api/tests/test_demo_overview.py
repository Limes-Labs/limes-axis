from fastapi.testclient import TestClient

from axis_api.demo import (
    OntologyNodeType,
    OverviewStatus,
    get_manufacturing_ontology,
    get_manufacturing_overview,
)
from axis_api.main import create_app


def test_manufacturing_overview_seed_is_valid_and_actionable() -> None:
    overview = get_manufacturing_overview()

    assert overview.scenario == "Plant Operations Cockpit"
    assert overview.plant_name == "Ravenna Works"
    assert any(metric.label == "Approvals" for metric in overview.metrics)
    assert any(
        signal.severity == OverviewStatus.ACTION_REQUIRED for signal in overview.risk_signals
    )
    assert any(approval.risk_level == "high" for approval in overview.approvals)
    assert all("@" not in item.owner_role for item in overview.approvals)


def test_manufacturing_overview_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Plant Operations Cockpit"
    assert body["metrics"][0]["label"] == "Workflow Load"
    assert body["approvals"][0]["approval_id"] == "appr_expedite_supplier_batch"
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_overview_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/overview" in response.json()["paths"]


def test_manufacturing_ontology_seed_has_valid_relationships() -> None:
    ontology = get_manufacturing_ontology()
    node_ids = {node.node_id for node in ontology.nodes}

    assert ontology.scenario == "Plant Operations Cockpit"
    assert OntologyNodeType.RISK in {node.node_type for node in ontology.nodes}
    assert OntologyNodeType.APPROVAL in {node.node_type for node in ontology.nodes}
    assert all(edge.source_id in node_ids for edge in ontology.relationships)
    assert all(edge.target_id in node_ids for edge in ontology.relationships)
    assert all("@" not in note for note in ontology.permission_notes)


def test_manufacturing_ontology_endpoint_returns_read_only_graph() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/ontology")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["nodes"][0]["node_id"] == "org_ravenna_operations"
    assert any(edge["relation_type"] == "requires_approval" for edge in body["relationships"])
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_ontology_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/ontology" in response.json()["paths"]
