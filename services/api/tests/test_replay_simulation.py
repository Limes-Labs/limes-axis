from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    WorkflowRunCreate,
    WorkflowTimelineEventCreate,
)
from axis_api.replay_simulation import (
    ReplaySimulationQuery,
    build_replay_simulation,
)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def seed_replay_history(repository: AxisPersistenceRepository) -> None:
    started_at = datetime(2026, 6, 21, 14, 5, tzinfo=UTC)
    repository.create_workflow_run(
        WorkflowRunCreate(
            tenant_id="tenant_demo_manufacturing",
            workflow_id="wf_supplier_delay_review",
            name="Supplier Delay Review",
            domain="Supply",
            state="waiting_for_approval",
            status="action_required",
            owner_role="plant-operations-owner",
            runtime="Temporal OSS",
            adapter="axis-temporal-adapter",
            autonomy_level="L2",
            started_at=started_at,
            eta="Today 18:00",
            blocker="Approve expedite action or adjust production schedule",
            objective="Resolve a delayed supplier batch before it blocks Line 2.",
            current_step="Approval gate",
            related_risk="risk_supplier_delay",
            related_assets=["asset_motors_batch", "asset_line_2_packaging"],
            inputs=["Supplier portal delay signal", "Line 2 packaging schedule"],
            proposed_outputs=["Expedite supplier batch action payload"],
            pending_signals=[
                {
                    "signal": "approval.decision",
                    "required_role": "plant-operations-owner",
                    "status": "waiting",
                    "approval_id": "appr_expedite_supplier_batch",
                }
            ],
            controls=["approvals:supply:decide", "append-only-audit-required"],
            audit_scope="wf_supplier_delay_review",
            replay_ready=False,
        )
    )
    repository.append_workflow_timeline_event(
        WorkflowTimelineEventCreate(
            tenant_id="tenant_demo_manufacturing",
            workflow_id="wf_supplier_delay_review",
            sequence=1,
            event="workflow.started",
            occurred_at=started_at,
            actor="workflow-runtime",
            result="started",
            summary="Supplier delay workflow created from the supply risk signal.",
        )
    )
    repository.append_workflow_timeline_event(
        WorkflowTimelineEventCreate(
            tenant_id="tenant_demo_manufacturing",
            workflow_id="wf_supplier_delay_review",
            sequence=2,
            event="workflow.signal.awaiting",
            occurred_at=datetime(2026, 6, 21, 14, 18, tzinfo=UTC),
            actor="axis-temporal-adapter",
            result="waiting_for_approval",
            summary="Workflow paused at the human approval gate.",
        )
    )
    repository.create_workflow_run(
        WorkflowRunCreate(
            tenant_id="tenant_other",
            workflow_id="wf_other",
            name="Other Tenant Workflow",
            domain="Other",
            state="waiting_for_approval",
            status="action_required",
            owner_role="other-owner",
            runtime="Temporal OSS",
            adapter="axis-temporal-adapter",
            autonomy_level="L1",
            started_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            eta="Today 17:00",
            blocker=None,
            objective="Other tenant objective",
            current_step="Other step",
            related_risk="risk_other",
            related_assets=["asset_other"],
            inputs=["Other input"],
            proposed_outputs=["Other output"],
            pending_signals=[],
            controls=["other:decide"],
            audit_scope="wf_other",
            replay_ready=False,
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="agent_supply_risk",
            event_type="action.proposal.created",
            payload={
                "action_id": "request_supplier_expedite",
                "workflow_id": "wf_supplier_delay_review",
                "approval_id": "appr_expedite_supplier_batch",
                "status": "approval_required",
                "approval_required": True,
                "payload_field_names": ["supplier_batch_id", "target_arrival"],
                "credential_secret": "never-export-this-value",
            },
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="plant-operations-owner-role",
            event_type="approval.decision.recorded",
            payload={
                "workflow_id": "wf_supplier_delay_review",
                "approval_id": "appr_expedite_supplier_batch",
                "decision": "approve",
                "required_permission": "approvals:supply:decide",
            },
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_other",
            actor_id="other-actor",
            event_type="approval.decision.recorded",
            payload={"workflow_id": "wf_other", "decision": "approve"},
        )
    )


def test_build_replay_simulation_creates_tenant_scoped_artifacts(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_replay_history(repository)
        simulation = build_replay_simulation(
            repository,
            ReplaySimulationQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert simulation.tenant_id == "tenant_demo_manufacturing"
    assert simulation.simulation_status == "ready"
    assert simulation.metrics[0].label == "Replay Artifacts"
    assert simulation.metrics[0].value == "1"
    assert len(simulation.artifacts) == 1
    artifact = simulation.artifacts[0]
    assert artifact.artifact_id.startswith("replay-wf_supplier_delay_review-")
    assert artifact.workflow_id == "wf_supplier_delay_review"
    assert artifact.audit_scope == "wf_supplier_delay_review"
    assert artifact.timeline_event_count == 2
    assert artifact.audit_event_count == 2
    assert artifact.replay_mode == "governance-preview"
    assert artifact.determinism_status == "preview_only"
    assert artifact.policy_results[0].policy_id == "human-approval-required"
    assert artifact.policy_results[0].simulated_decision == "blocked_until_human_approval"
    assert artifact.policy_set_diffs[0].candidate_policy_set_id == (
        "policy_set_connector_asset_required_20260622_rollback"
    )
    assert "tenant_other" not in simulation.model_dump_json()
    assert "credential_secret" not in simulation.model_dump_json()
    assert "never-export-this-value" not in simulation.model_dump_json()


def test_build_replay_simulation_includes_policy_set_version_diff_preview(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_replay_history(repository)
        simulation = build_replay_simulation(
            repository,
            ReplaySimulationQuery(tenant_id="tenant_demo_manufacturing"),
        )

    diff_metric = next(
        metric for metric in simulation.metrics if metric.label == "Policy Set Diffs"
    )
    assert diff_metric.value == "1"
    artifact = simulation.artifacts[0]
    diff = artifact.policy_set_diffs[0]
    assert diff.diff_id.startswith("policy-set-diff-wf_supplier_delay_review-")
    assert diff.connector_id == "file_csv_manufacturing_assets"
    assert diff.baseline_policy_set_id == "policy_set_connector_asset_required_20260622_v2"
    assert diff.baseline_policy_set_version == "2026-06-22.2"
    assert diff.candidate_policy_set_id == (
        "policy_set_connector_asset_required_20260622_rollback"
    )
    assert diff.candidate_policy_set_version == "2026-06-22.3"
    assert diff.historical_event_count == 4
    assert diff.changed_policy_ids == ["connector.asset.required"]
    assert diff.changed_outcome is True
    assert diff.diff_status == "changed_outcome_detected"
    assert diff.audit_event_type == "connector.promotion_policy_set.simulated_diff"
    assert "appr_expedite_supplier_batch" in diff.evidence_refs
    assert "credential_secret" not in diff.model_dump_json()


def test_build_replay_simulation_filters_by_workflow_id(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_replay_history(repository)
        simulation = build_replay_simulation(
            repository,
            ReplaySimulationQuery(
                tenant_id="tenant_demo_manufacturing",
                workflow_id="missing_workflow",
            ),
        )

    assert simulation.artifacts == []
    assert simulation.simulation_status == "watch"
    assert simulation.metrics[0].value == "0"


def test_replay_simulation_endpoint_returns_artifact(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_replay_history(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/simulation/replay",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "workflow_id": "wf_supplier_delay_review",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["artifacts"][0]["workflow_id"] == "wf_supplier_delay_review"
    assert body["artifacts"][0]["policy_results"][0]["policy_id"] == "human-approval-required"
    assert body["artifacts"][0]["policy_set_diffs"][0]["audit_event_type"] == (
        "connector.promotion_policy_set.simulated_diff"
    )
    assert "tenant_other" not in str(body)


def test_openapi_exposes_replay_simulation_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/simulation/replay" in response.json()["paths"]
