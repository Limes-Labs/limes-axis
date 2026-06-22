from pathlib import Path
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.demo import (
    ApprovalDecision,
    ManufacturingActionRegistry,
    ManufacturingAgentRegistry,
    ManufacturingApprovalInbox,
    ManufacturingOverview,
    ManufacturingWorkflowConsole,
    OntologyNodeType,
    OverviewStatus,
    get_manufacturing_action_registry,
    get_manufacturing_agent_registry,
    get_manufacturing_approval_inbox,
    get_manufacturing_audit_explorer,
    get_manufacturing_model_routing,
    get_manufacturing_ontology,
    get_manufacturing_ontology_entity_detail,
    get_manufacturing_workflow_console,
)
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, DemoReferenceRecordCreate


def persisted_overview_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "plant_name": "Persisted Ravenna Works",
        "scenario": "Persisted Plant Operations Cockpit",
        "as_of": "2026-06-22T10:00:00+02:00",
        "metrics": [
            {
                "label": "Persisted Workflow Load",
                "value": "2 active",
                "detail": "Loaded from demo_reference_records.",
                "status": "ready",
            }
        ],
        "risk_signals": [
            {
                "title": "Persisted supply risk",
                "domain": "Supply",
                "severity": "watch",
                "owner_role": "supply-owner",
                "evidence": "Persisted supply evidence.",
                "related_asset": "asset_persisted_batch",
            }
        ],
        "workflows": [
            {
                "workflow_id": "wf_persisted_overview",
                "name": "Persisted Overview Workflow",
                "state": "ready",
                "owner_role": "operations-owner",
                "blocker": None,
                "eta": "Today",
            }
        ],
        "approvals": [
            {
                "approval_id": "appr_persisted_overview",
                "action": "Review persisted overview",
                "risk_level": "low",
                "requested_by": "axis-bootstrap",
                "owner_role": "operations-owner",
                "due": "Today",
            }
        ],
        "agents": [
            {
                "agent_id": "agent_persisted_overview",
                "name": "Persisted Overview Agent",
                "autonomy_level": "L1",
                "status": "ready",
                "proposals_pending": 0,
                "model_policy": "local-only",
            }
        ],
        "audit_events": [
            {
                "event": "overview.loaded",
                "actor": "axis-bootstrap",
                "scope": "overview",
                "result": "persisted",
            }
        ],
    }


def persisted_workflow_console_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "plant_name": "Persisted Ravenna Works",
        "scenario": "Persisted Workflow Console",
        "as_of": "2026-06-22T11:00:00+02:00",
        "runtime_status": "ready",
        "metrics": [
            {
                "label": "Persisted Reference Runs",
                "value": "1",
                "detail": "Loaded from demo_reference_records.",
                "status": "ready",
            }
        ],
        "workflow_runs": [
            {
                "workflow_id": "wf_persisted_reference",
                "name": "Persisted Reference Workflow",
                "domain": "Operations",
                "state": "waiting_for_approval",
                "status": "action_required",
                "owner_role": "plant-operations-owner",
                "runtime": "Temporal OSS",
                "adapter": "axis-temporal-adapter",
                "autonomy_level": "L2",
                "started_at": "2026-06-22T10:45:00+02:00",
                "eta": "Today 13:00",
                "blocker": "Owner approval required",
                "objective": "Validate persisted workflow reference path.",
                "current_step": "Approval gate",
                "related_risk": "risk_persisted_workflow",
                "related_assets": ["asset_persisted_line"],
                "inputs": ["Persisted workflow input"],
                "proposed_outputs": ["Persisted workflow output"],
                "pending_signals": [
                    {
                        "signal": "approval.decision",
                        "required_role": "plant-operations-owner",
                        "status": "waiting",
                        "approval_id": "appr_persisted_workflow",
                    }
                ],
                "controls": ["approvals:operations:decide"],
                "timeline": [
                    {
                        "event": "workflow.reference.loaded",
                        "at": "2026-06-22T10:45:00+02:00",
                        "actor": "axis-bootstrap",
                        "result": "loaded",
                        "summary": "Workflow reference loaded from persistence.",
                    }
                ],
                "audit_scope": "wf_persisted_reference",
                "replay_ready": False,
            }
        ],
        "runtime_notes": ["Persisted workflow console reference."],
    }


def persisted_approval_inbox_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "plant_name": "Persisted Ravenna Works",
        "scenario": "Persisted Approval Inbox",
        "as_of": "2026-06-22T11:15:00+02:00",
        "queue_status": "action_required",
        "policy_notes": ["Persisted approval inbox reference."],
        "approvals": [
            {
                "approval_id": "appr_persisted_operations_review",
                "action": "Review persisted operations proposal",
                "risk_level": "medium",
                "status": "pending",
                "requested_by": "agent_persisted_daily_brief",
                "owner_role": "plant-operations-owner",
                "due": "Today 14:00",
                "workflow_id": "wf_persisted_reference",
                "domain": "Operations",
                "summary": "Persisted approval reference used by the API.",
                "evidence": ["Persisted approval evidence"],
                "data_accessed": ["Axis Audit: persisted approval reference"],
                "risks": ["Approving without persisted evidence would violate policy."],
                "alternatives": ["Request changes before approval."],
                "estimated_cost": "No direct spend",
                "model_policy": "local-only",
                "required_permission": "approvals:operations:decide",
                "audit_event_preview": {
                    "event": "approval.decision.recorded",
                    "actor_role": "plant-operations-owner",
                    "scope": "wf_persisted_reference",
                    "result": "workflow_signal_ready",
                },
                "decision_options": [
                    {
                        "decision": "approve",
                        "label": "Approve",
                        "consequence": "Signal persisted workflow approval.",
                    },
                    {
                        "decision": "reject",
                        "label": "Reject",
                        "consequence": "Record denial in persisted approval flow.",
                    },
                    {
                        "decision": "request_changes",
                        "label": "Request changes",
                        "consequence": "Return persisted proposal for revision.",
                    },
                ],
            }
        ],
    }


def persisted_agent_registry_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "plant_name": "Persisted Ravenna Works",
        "scenario": "Persisted Agent Registry",
        "as_of": "2026-06-22T10:15:00+02:00",
        "registry_status": "ready",
        "metrics": [
            {
                "label": "Persisted Agents",
                "value": "1 governed",
                "detail": "Loaded from demo_reference_records.",
                "status": "ready",
            }
        ],
        "filter_options": {
            "domains": ["Operations"],
            "autonomy_levels": ["L1"],
            "statuses": ["ready"],
            "model_policies": ["local-only"],
        },
        "agents": [
            {
                "agent_id": "agent_persisted_daily_brief",
                "name": "Persisted Daily Brief Agent",
                "domain": "Operations",
                "status": "ready",
                "owner_role": "plant-operations-owner",
                "purpose": "Prepare owner-facing summaries from persisted evidence.",
                "policy_boundary": {
                    "autonomy_level": "L1",
                    "model_policy": "local-only",
                    "external_egress_allowed": False,
                    "max_action_level": "L1",
                    "required_permissions": ["agents:read"],
                    "guardrails": ["No mutation or external egress."],
                },
                "connected_systems": ["Axis Audit"],
                "data_access": ["audit summaries"],
                "allowed_actions": ["Prepare daily brief"],
                "blocked_actions": ["Mutate workflow state"],
                "proposals": [],
                "active_workflows": [],
                "pending_approvals": [],
                "last_audit_event": "audit_persisted_agent_registry",
                "evidence_refs": ["agent_persisted_daily_brief"],
            }
        ],
        "registry_notes": ["Persisted agent registry reference."],
    }


def persisted_action_registry_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "plant_name": "Persisted Ravenna Works",
        "scenario": "Persisted Action Registry",
        "as_of": "2026-06-22T10:30:00+02:00",
        "registry_status": "ready",
        "schema_version": "2026-06-22",
        "metrics": [
            {
                "label": "Persisted Actions",
                "value": "1 typed",
                "detail": "Loaded from demo_reference_records.",
                "status": "ready",
            }
        ],
        "filter_options": {
            "domains": ["Operations"],
            "risk_levels": ["low"],
            "approval_modes": ["not_required"],
            "statuses": ["ready"],
        },
        "actions": [
            {
                "definition": {
                    "action_id": "action_persisted_daily_brief",
                    "display_name": "Persisted daily brief",
                    "domain": "Operations",
                    "risk_level": "low",
                    "approval_mode": "not_required",
                    "input_schema": {
                        "type": "object",
                        "required": ["brief_date"],
                        "properties": {"brief_date": {"type": "string"}},
                    },
                    "output_schema": {
                        "type": "object",
                        "required": ["brief_id"],
                        "properties": {"brief_id": {"type": "string"}},
                    },
                    "required_permissions": ["actions:read"],
                },
                "description": "Persisted read-only action registry fixture.",
                "owner_role": "plant-operations-owner",
                "status": "ready",
                "side_effects": "No production mutation.",
                "policy": {
                    "approval_role": "plant-operations-owner",
                    "autonomy_ceiling": "L1",
                    "execution_mode": "dry_run_only",
                    "runtime_adapter": "axis-deferred-action-runtime",
                    "audit_event_type": "action.preview.generated",
                    "model_egress_policy": "local-only",
                    "idempotency_required": True,
                    "dry_run_supported": True,
                },
                "connected_agents": ["agent_persisted_daily_brief"],
                "workflow_bindings": [],
                "approval_refs": [],
                "guardrails": ["No live execution."],
                "validation_checks": ["brief_date is present"],
                "blocked_conditions": ["live execution requested"],
                "sample_input": {"brief_date": "2026-06-22"},
                "sample_output": {"brief_id": "brief_persisted_20260622"},
            }
        ],
        "registry_notes": ["Persisted action registry reference."],
    }


@pytest.fixture
def overview_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


def test_manufacturing_overview_reference_contract_is_valid_and_actionable() -> None:
    overview = ManufacturingOverview.model_validate(persisted_overview_payload())

    assert overview.scenario == "Persisted Plant Operations Cockpit"
    assert overview.plant_name == "Persisted Ravenna Works"
    assert any(metric.label == "Persisted Workflow Load" for metric in overview.metrics)
    assert any(signal.severity == OverviewStatus.WATCH for signal in overview.risk_signals)
    assert any(approval.risk_level == "low" for approval in overview.approvals)
    assert all("@" not in item.owner_role for item in overview.approvals)


def test_manufacturing_overview_bootstrap_payload_matches_contract() -> None:
    migration = run_path("migrations/versions/0022_demo_reference_records.py")

    overview = ManufacturingOverview.model_validate(migration["MANUFACTURING_OVERVIEW_PAYLOAD"])

    assert overview.tenant_id == "tenant_demo_manufacturing"
    assert overview.scenario == "Plant Operations Cockpit"
    assert any(agent.autonomy_level == "L2" for agent in overview.agents)


def test_manufacturing_overview_is_not_defined_as_runtime_seed() -> None:
    source = Path("src/axis_api/demo.py").read_text()

    assert "def get_manufacturing_overview" not in source


def test_manufacturing_overview_endpoint_returns_persisted_reference_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="overview",
                reference_id="manufacturing-overview",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=persisted_overview_payload(),
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Persisted Plant Operations Cockpit"
    assert body["plant_name"] == "Persisted Ravenna Works"
    assert body["metrics"][0]["label"] == "Persisted Workflow Load"
    assert body["approvals"][0]["approval_id"] == "appr_persisted_overview"
    assert "password" not in str(body).lower()


def test_manufacturing_overview_endpoint_reports_missing_reference_record(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    client = TestClient(app)
    response = client.get("/demo/manufacturing/overview")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_manufacturing_overview_endpoint_rejects_invalid_reference_payload(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        payload = persisted_overview_payload()
        payload["tenant_id"] = "tenant_wrong"
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="overview",
                reference_id="manufacturing-overview",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/overview")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


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


def test_manufacturing_workflow_console_reference_contract_is_valid() -> None:
    console = ManufacturingWorkflowConsole.model_validate(persisted_workflow_console_payload())

    assert console.tenant_id == "tenant_demo_manufacturing"
    assert console.scenario == "Persisted Workflow Console"
    assert console.workflow_runs[0].workflow_id == "wf_persisted_reference"
    assert console.workflow_runs[0].timeline[0].event == "workflow.reference.loaded"


def test_manufacturing_workflow_console_bootstrap_payload_matches_contract() -> None:
    migration = run_path("migrations/versions/0026_workflow_console_reference.py")

    console = ManufacturingWorkflowConsole.model_validate(migration["WORKFLOW_CONSOLE_PAYLOAD"])

    assert console.tenant_id == "tenant_demo_manufacturing"
    assert console.scenario == "Plant Operations Cockpit"
    assert len(console.workflow_runs) == 3
    assert any(run.workflow_id == "wf_supplier_delay_review" for run in console.workflow_runs)
    serialized = console.model_dump_json().lower()
    assert "password" not in serialized
    assert "api_key" not in serialized
    assert "credential_value" not in serialized


def test_manufacturing_workflow_console_endpoint_is_not_defined_as_runtime_seed() -> None:
    source = Path("src/axis_api/main.py").read_text()

    assert "return get_manufacturing_workflow_console()" not in source


def test_manufacturing_workflow_console_endpoint_returns_persisted_reference_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="workflows",
                reference_id="manufacturing-workflow-console",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=persisted_workflow_console_payload(),
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/workflows")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Persisted Workflow Console"
    assert body["workflow_runs"][0]["workflow_id"] == "wf_persisted_reference"
    assert body["workflow_runs"][0]["pending_signals"][0]["approval_id"] == (
        "appr_persisted_workflow"
    )
    assert body["workflow_runs"][0]["controls"][0] == "approvals:operations:decide"
    assert "Persisted workflow console reference." in body["runtime_notes"][0]
    assert "password" not in str(body).lower()


def test_manufacturing_workflow_console_endpoint_reports_missing_reference_record(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    client = TestClient(app)
    response = client.get("/demo/manufacturing/workflows")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_manufacturing_workflow_console_endpoint_rejects_invalid_reference_payload(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        payload = persisted_workflow_console_payload()
        payload["tenant_id"] = "tenant_wrong"
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="workflows",
                reference_id="manufacturing-workflow-console",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/workflows")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


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


def test_manufacturing_agent_registry_reference_contract_is_valid_and_actionable() -> None:
    registry = ManufacturingAgentRegistry.model_validate(persisted_agent_registry_payload())

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.scenario == "Persisted Agent Registry"
    assert registry.agents[0].agent_id == "agent_persisted_daily_brief"
    assert registry.agents[0].policy_boundary.external_egress_allowed is False


def test_manufacturing_agent_registry_bootstrap_payload_matches_contract() -> None:
    migration = run_path("migrations/versions/0024_agent_registry_reference.py")

    registry = ManufacturingAgentRegistry.model_validate(migration["AGENT_REGISTRY_PAYLOAD"])

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.scenario == "Plant Operations Cockpit"
    assert len(registry.agents) == 4
    assert any(agent.agent_id == "agent_supply_risk" for agent in registry.agents)
    serialized = registry.model_dump_json().lower()
    assert "password" not in serialized
    assert "api_key" not in serialized
    assert "credential_value" not in serialized


def test_manufacturing_agent_registry_endpoint_is_not_defined_as_runtime_seed() -> None:
    source = Path("src/axis_api/main.py").read_text()

    assert "return get_manufacturing_agent_registry()" not in source


def test_manufacturing_agent_registry_endpoint_returns_persisted_reference_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="agents",
                reference_id="manufacturing-agent-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=persisted_agent_registry_payload(),
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/agents")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Persisted Agent Registry"
    assert body["agents"][0]["agent_id"] == "agent_persisted_daily_brief"
    assert body["agents"][0]["policy_boundary"]["external_egress_allowed"] is False
    assert "password" not in str(body).lower()


def test_manufacturing_agent_registry_endpoint_reports_missing_reference_record(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    client = TestClient(app)
    response = client.get("/demo/manufacturing/agents")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_manufacturing_agent_registry_endpoint_rejects_invalid_reference_payload(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        payload = persisted_agent_registry_payload()
        payload["tenant_id"] = "tenant_wrong"
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="agents",
                reference_id="manufacturing-agent-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/agents")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


def test_manufacturing_agent_registry_endpoint_returns_bootstrap_public_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    migration = run_path("migrations/versions/0024_agent_registry_reference.py")
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="agents",
                reference_id="manufacturing-agent-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=migration["AGENT_REGISTRY_PAYLOAD"],
            )
        )
    client = TestClient(app)
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


def test_manufacturing_action_registry_seed_is_policy_gated() -> None:
    registry = get_manufacturing_action_registry()

    assert registry.scenario == "Plant Operations Cockpit"
    assert registry.registry_status == OverviewStatus.WATCH
    assert registry.schema_version == "2026-06-21"
    assert len(registry.actions) == 4
    assert "Supply" in registry.filter_options.domains
    assert "required" in registry.filter_options.approval_modes
    assert "high" in registry.filter_options.risk_levels
    assert any(
        action.definition.action_id == "request_supplier_expedite" for action in registry.actions
    )
    assert sum(action.definition.requires_approval for action in registry.actions) == 3
    assert all(action.policy.dry_run_supported for action in registry.actions)
    assert all(action.policy.execution_mode != "live_execution" for action in registry.actions)
    assert all(action.validation_checks for action in registry.actions)
    assert all(action.blocked_conditions for action in registry.actions)
    assert "password" not in registry.model_dump_json().lower()
    assert "secret" not in registry.model_dump_json().lower()
    assert "@" not in registry.model_dump_json()


def test_manufacturing_action_registry_reference_contract_is_valid_and_actionable() -> None:
    registry = ManufacturingActionRegistry.model_validate(persisted_action_registry_payload())

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.scenario == "Persisted Action Registry"
    assert registry.actions[0].definition.action_id == "action_persisted_daily_brief"
    assert registry.actions[0].policy.dry_run_supported is True


def test_manufacturing_action_registry_bootstrap_payload_matches_contract() -> None:
    migration = run_path("migrations/versions/0025_action_registry_reference.py")

    registry = ManufacturingActionRegistry.model_validate(migration["ACTION_REGISTRY_PAYLOAD"])

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.scenario == "Plant Operations Cockpit"
    assert len(registry.actions) == 4
    assert any(
        action.definition.action_id == "request_supplier_expedite" for action in registry.actions
    )
    serialized = registry.model_dump_json().lower()
    assert "password" not in serialized
    assert "api_key" not in serialized
    assert "credential_value" not in serialized


def test_manufacturing_action_registry_endpoint_is_not_defined_as_runtime_seed() -> None:
    source = Path("src/axis_api/main.py").read_text()

    assert "return get_manufacturing_action_registry()" not in source


def test_manufacturing_action_registry_endpoint_returns_persisted_reference_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="actions",
                reference_id="manufacturing-action-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=persisted_action_registry_payload(),
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/actions")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Persisted Action Registry"
    assert body["actions"][0]["definition"]["action_id"] == "action_persisted_daily_brief"
    assert body["actions"][0]["policy"]["dry_run_supported"] is True
    assert "password" not in str(body).lower()


def test_manufacturing_action_registry_endpoint_reports_missing_reference_record(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    client = TestClient(app)
    response = client.get("/demo/manufacturing/actions")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_manufacturing_action_registry_endpoint_rejects_invalid_reference_payload(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        payload = persisted_action_registry_payload()
        payload["tenant_id"] = "tenant_wrong"
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="actions",
                reference_id="manufacturing-action-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/actions")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


def test_manufacturing_action_registry_endpoint_returns_bootstrap_public_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    migration = run_path("migrations/versions/0025_action_registry_reference.py")
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="actions",
                reference_id="manufacturing-action-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=migration["ACTION_REGISTRY_PAYLOAD"],
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/actions")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["actions"][1]["definition"]["action_id"] == "request_supplier_expedite"
    assert body["actions"][1]["definition"]["risk_level"] == "high"
    assert body["actions"][1]["definition"]["approval_mode"] == "required"
    assert body["actions"][1]["approval_refs"][0] == "appr_expedite_supplier_batch"
    assert body["actions"][1]["policy"]["model_egress_policy"] == "no-external-egress"
    assert "runtime execution is not enabled" in body["registry_notes"][1]
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_action_registry_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/actions" in response.json()["paths"]


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


def test_manufacturing_approval_inbox_reference_contract_is_valid() -> None:
    inbox = ManufacturingApprovalInbox.model_validate(persisted_approval_inbox_payload())

    assert inbox.tenant_id == "tenant_demo_manufacturing"
    assert inbox.scenario == "Persisted Approval Inbox"
    assert inbox.approvals[0].approval_id == "appr_persisted_operations_review"
    assert inbox.approvals[0].required_permission == "approvals:operations:decide"


def test_manufacturing_approval_inbox_bootstrap_payload_matches_contract() -> None:
    migration = run_path("migrations/versions/0027_approval_inbox_reference.py")

    inbox = ManufacturingApprovalInbox.model_validate(migration["APPROVAL_INBOX_PAYLOAD"])

    assert inbox.tenant_id == "tenant_demo_manufacturing"
    assert inbox.scenario == "Plant Operations Cockpit"
    assert len(inbox.approvals) == 3
    assert any(
        approval.approval_id == "appr_expedite_supplier_batch" for approval in inbox.approvals
    )
    serialized = inbox.model_dump_json().lower()
    assert "password" not in serialized
    assert "api_key" not in serialized
    assert "credential_value" not in serialized


def test_manufacturing_approval_inbox_endpoint_is_not_defined_as_runtime_seed() -> None:
    source = Path("src/axis_api/main.py").read_text()

    assert "return get_manufacturing_approval_inbox()" not in source


def test_manufacturing_approval_inbox_endpoint_returns_persisted_reference_data(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="approvals",
                reference_id="manufacturing-approval-inbox",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=persisted_approval_inbox_payload(),
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/approvals")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Persisted Approval Inbox"
    assert body["approvals"][0]["approval_id"] == "appr_persisted_operations_review"
    assert body["approvals"][0]["required_permission"] == "approvals:operations:decide"
    assert body["approvals"][0]["decision_options"][0]["decision"] == "approve"
    assert "Persisted approval inbox reference." in body["policy_notes"][0]
    assert "password" not in str(body).lower()


def test_manufacturing_approval_inbox_endpoint_reports_missing_reference_record(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    client = TestClient(app)
    response = client.get("/demo/manufacturing/approvals")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_manufacturing_approval_inbox_endpoint_rejects_invalid_reference_payload(
    overview_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = overview_session_factory
    with session_scope(overview_session_factory) as session:
        payload = persisted_approval_inbox_payload()
        payload["tenant_id"] = "tenant_wrong"
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="approvals",
                reference_id="manufacturing-approval-inbox",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/approvals")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


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


def test_manufacturing_model_routing_seed_is_observable() -> None:
    routing = get_manufacturing_model_routing()

    assert routing.scenario == "Plant Operations Cockpit"
    assert routing.routing_status == OverviewStatus.WATCH
    assert len(routing.routes) == 4
    assert len(routing.provider_options) == 3
    assert "Quality" in routing.filter_options.domains
    assert "blocked_by_default" in routing.filter_options.egress_decisions
    assert any(route.egress_decision == "blocked_by_default" for route in routing.routes)
    assert any(route.estimated_cost_eur > 0 for route in routing.routes)
    assert all(
        route.estimated_cost_eur == 0
        for route in routing.routes
        if route.egress_decision == "blocked_by_default"
    )
    assert all(not route.external_egress_allowed for route in routing.routes)
    assert all(route.required_permissions for route in routing.routes)
    assert "password" not in routing.model_dump_json().lower()
    assert "secret" not in routing.model_dump_json().lower()
    assert "@" not in routing.model_dump_json()


def test_manufacturing_model_routing_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/model-routing")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["routes"][2]["route_id"] == "route_quality_external_blocked"
    assert body["routes"][2]["egress_decision"] == "blocked_by_default"
    assert body["routes"][2]["estimated_cost_eur"] == 0
    assert body["provider_options"][0]["provider_id"] == "local-vllm"
    assert "not product pricing" in body["budget_notes"][0]
    assert "password" not in str(body).lower()


def test_openapi_exposes_manufacturing_model_routing_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/model-routing" in response.json()["paths"]


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


def test_manufacturing_ontology_entity_detail_seed_is_connected() -> None:
    detail = get_manufacturing_ontology_entity_detail("asset_line_2_packaging")

    assert detail is not None
    assert detail.node.label == "Line 2 Packaging"
    assert detail.node.node_type == OntologyNodeType.ASSET
    assert detail.inbound_count == 2
    assert detail.outbound_count == 0
    assert "operations:read" in detail.required_permissions
    assert "supply:read" in detail.required_permissions
    assert "risk_supplier_delay" in detail.evidence_refs
    assert any(
        item.relationship.relation_type == "impacts" for item in detail.connected_relationships
    )
    assert "password" not in detail.model_dump_json().lower()
    assert "secret" not in detail.model_dump_json().lower()
    assert "@" not in detail.model_dump_json()


def test_manufacturing_ontology_entity_detail_endpoint_returns_public_demo_data() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/ontology/entities/risk_supplier_delay")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["node"]["node_id"] == "risk_supplier_delay"
    assert body["related_workflows"] == ["wf_supplier_delay_review"]
    assert "supply:read" in body["required_permissions"]
    assert "TypeDB-shaped relationships" in body["detail_notes"][0]
    assert "password" not in str(body).lower()


def test_manufacturing_ontology_entity_detail_endpoint_handles_missing_node() -> None:
    client = TestClient(create_app())
    response = client.get("/demo/manufacturing/ontology/entities/missing-node")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ontology entity not found"


def test_manufacturing_ontology_entity_detail_endpoint_enforces_relationship_scopes() -> None:
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
        "/demo/manufacturing/ontology/entities/asset_line_2_packaging",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "PERMISSION_DENIED",
        "message": "The actor cannot read this ontology entity relationship context.",
        "required_permissions": ["operations:read", "supply:read"],
        "reason": "missing_relationship_scope:supply:read",
    }


def test_manufacturing_ontology_entity_detail_endpoint_allows_relationship_scopes() -> None:
    app = create_app(Settings(oidc_auth_required=True))
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="operations-reader",
            tenant_id="tenant_demo_manufacturing",
            scopes=["operations:read", "supply:read"],
        )
    )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/ontology/entities/asset_line_2_packaging",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json()["node"]["node_id"] == "asset_line_2_packaging"


def test_openapi_exposes_manufacturing_ontology_entity_detail_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/ontology/entities/{node_id}" in response.json()["paths"]
