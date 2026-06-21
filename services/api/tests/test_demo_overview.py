from fastapi.testclient import TestClient

from axis_api.demo import OverviewStatus, get_manufacturing_overview
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
