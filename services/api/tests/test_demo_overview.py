from fastapi.testclient import TestClient

from axis_api.demo import (
    ApprovalDecision,
    OntologyNodeType,
    OverviewStatus,
    get_manufacturing_agent_registry,
    get_manufacturing_approval_inbox,
    get_manufacturing_audit_explorer,
    get_manufacturing_ontology,
    get_manufacturing_overview,
    get_manufacturing_workflow_console,
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


def test_manufacturing_workflow_console_seed_is_inspectable() -> None:
    console = get_manufacturing_workflow_console()

    assert console.scenario == "Plant Operations Cockpit"
    assert console.runtime_status == OverviewStatus.WATCH
    assert len(console.workflow_runs) == 3
    assert any(run.state == "waiting_for_approval" for run in console.workflow_runs)
    assert any(run.status == OverviewStatus.ACTION_REQUIRED for run in console.workflow_runs)
    assert all(run.runtime == "Temporal OSS" for run in console.workflow_runs)
    assert all(run.adapter == "axis-temporal-adapter" for run in console.workflow_runs)
    assert all(run.pending_signals for run in console.workflow_runs)
    assert all(run.timeline for run in console.workflow_runs)
    assert all(not run.replay_ready for run in console.workflow_runs)
    assert "password" not in console.model_dump_json().lower()
    assert "@" not in console.model_dump_json()


def test_manufacturing_workflow_console_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/workflows")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["workflow_runs"][0]["workflow_id"] == "wf_supplier_delay_review"
    assert body["workflow_runs"][0]["pending_signals"][0]["approval_id"] == (
        "appr_expedite_supplier_batch"
    )
    assert body["workflow_runs"][0]["controls"][0] == "approvals:supply:decide"
    assert "workflow signal execution remain Platform work" in body["runtime_notes"][3]
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_workflow_console_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/workflows" in response.json()["paths"]


def test_manufacturing_agent_registry_seed_is_governed() -> None:
    registry = get_manufacturing_agent_registry()

    assert registry.scenario == "Plant Operations Cockpit"
    assert registry.registry_status == OverviewStatus.WATCH
    assert len(registry.agents) == 4
    assert registry.filter_options.autonomy_levels == ["L1", "L2"]
    assert "Supply" in registry.filter_options.domains
    assert any(agent.agent_id == "agent_maintenance_planner" for agent in registry.agents)
    assert any(agent.proposals for agent in registry.agents)
    assert all(not agent.policy_boundary.external_egress_allowed for agent in registry.agents)
    assert all(agent.policy_boundary.max_action_level in {"L1", "L2"} for agent in registry.agents)
    assert all(agent.policy_boundary.guardrails for agent in registry.agents)
    assert "password" not in registry.model_dump_json().lower()
    assert "secret" not in registry.model_dump_json().lower()
    assert "@" not in registry.model_dump_json()


def test_manufacturing_agent_registry_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/agents")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["agents"][1]["agent_id"] == "agent_supply_risk"
    assert body["agents"][1]["pending_approvals"][0] == "appr_expedite_supplier_batch"
    assert body["agents"][1]["policy_boundary"]["external_egress_allowed"] is False
    assert "production action registry" in body["registry_notes"][3]
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_agent_registry_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/agents" in response.json()["paths"]


def test_manufacturing_approval_inbox_seed_is_governed() -> None:
    inbox = get_manufacturing_approval_inbox()

    assert inbox.scenario == "Plant Operations Cockpit"
    assert inbox.queue_status == OverviewStatus.ACTION_REQUIRED
    assert len(inbox.approvals) == 3
    assert any(item.risk_level == "high" for item in inbox.approvals)
    assert all(item.status == "pending" for item in inbox.approvals)
    assert all(item.evidence for item in inbox.approvals)
    assert all(item.data_accessed for item in inbox.approvals)
    assert all(
        item.audit_event_preview.event == "approval.decision.recorded" for item in inbox.approvals
    )
    assert all(
        {option.decision for option in item.decision_options}
        == {
            ApprovalDecision.APPROVE,
            ApprovalDecision.REJECT,
            ApprovalDecision.REQUEST_CHANGES,
        }
        for item in inbox.approvals
    )
    assert "password" not in inbox.model_dump_json().lower()
    assert "@" not in inbox.model_dump_json()


def test_manufacturing_approval_inbox_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/approvals")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["approvals"][0]["approval_id"] == "appr_expedite_supplier_batch"
    assert body["approvals"][0]["required_permission"] == "approvals:supply:decide"
    assert body["approvals"][0]["decision_options"][0]["decision"] == "approve"
    assert "production persistence remains Platform work" in body["policy_notes"][3]
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_approval_inbox_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/approvals" in response.json()["paths"]


def test_manufacturing_audit_explorer_seed_is_filterable() -> None:
    explorer = get_manufacturing_audit_explorer()

    assert explorer.scenario == "Plant Operations Cockpit"
    assert explorer.ledger_status == OverviewStatus.WATCH
    assert len(explorer.events) == 9
    assert explorer.filter_options.tenants == ["tenant_demo_manufacturing"]
    assert "agent.proposal.created" in explorer.filter_options.event_types
    assert "wf_supplier_delay_review" in explorer.filter_options.scopes
    assert "supply-risk-agent" in explorer.filter_options.actors
    assert any(event.severity == OverviewStatus.ACTION_REQUIRED for event in explorer.events)
    assert any(event.event_type == "policy.egress.blocked" for event in explorer.events)
    assert all(event.payload_preview for event in explorer.events)
    assert all(event.data_classification == "public-demo" for event in explorer.events)
    assert "password" not in explorer.model_dump_json().lower()
    assert "secret" not in explorer.model_dump_json().lower()
    assert "@" not in explorer.model_dump_json()


def test_manufacturing_audit_explorer_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/audit")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["events"][0]["event_type"] == "workflow.started"
    assert body["events"][1]["related_approval_id"] == "appr_expedite_supplier_batch"
    assert "agent.proposal.created" in body["filter_options"]["event_types"]
    assert "retention policy enforcement" in body["retention_notes"][3]
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_audit_explorer_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/audit" in response.json()["paths"]


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
