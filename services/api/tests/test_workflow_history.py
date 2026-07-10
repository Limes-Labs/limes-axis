from copy import deepcopy
from pathlib import Path
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.action_runs import (
    ActionRunOutcomeRequest,
    ActionRunRequest,
    record_demo_action_run,
    record_demo_action_run_outcome,
)
from axis_api.approval_decisions import ApprovalDecisionRequest, record_demo_approval_decision
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.demo import ApprovalDecision
from axis_api.main import create_app
from axis_api.models import Base, WorkflowRunRecord, WorkflowTimelineRecord
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorPromotionPolicyCreate,
    ConnectorPromotionPolicySetCreate,
    DemoReferenceRecordCreate,
)
from axis_api.workflow_history import ensure_workflow_run
from axis_api.workflow_runtime import (
    WorkflowActionSignalRequest,
    WorkflowSignalRequest,
    WorkflowSignalResult,
)

MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations" / "versions"

TENANT_ID = "tenant_demo_manufacturing"
SUPPLIER_WORKFLOW_ID = "wf_supplier_delay_review"
SUPPLIER_APPROVAL_ID = "appr_expedite_supplier_batch"


class RecordingWorkflowRuntime:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def signal_approval_decision(
        self,
        request: WorkflowSignalRequest,
    ) -> WorkflowSignalResult:
        self.requests.append(request)
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="approval_signaled",
            adapter="axis-test-workflow-adapter",
            signal_name=request.signal_name,
            payload={
                "approval_id": request.approval_id,
                "approved": request.approved,
                "decision": request.decision.value,
            },
        )

    async def signal_action_run(
        self,
        request: WorkflowActionSignalRequest,
    ) -> WorkflowSignalResult:
        self.requests.append(request)
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="action_signal_requested",
            adapter="axis-test-workflow-adapter",
            signal_name=request.signal_name,
            payload={
                "action_id": request.action_id,
                "action_run_id": str(request.action_run_id),
                "idempotency_key": request.idempotency_key,
                "approval_id": request.approval_id,
            },
        )


def _migration_payload(migration_file: str, payload_name: str) -> dict:
    migration = run_path(str(MIGRATIONS_DIR / migration_file))
    return deepcopy(migration[payload_name])


def _seed_reference(
    factory: sessionmaker[Session],
    *,
    surface: str,
    reference_id: str,
    payload: dict,
) -> None:
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id=TENANT_ID,
                surface=surface,
                reference_id=reference_id,
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )


def seed_reference_records(factory: sessionmaker[Session]) -> None:
    _seed_reference(
        factory,
        surface="actions",
        reference_id="manufacturing-action-registry",
        payload=_migration_payload(
            "0025_action_registry_reference.py",
            "ACTION_REGISTRY_PAYLOAD",
        ),
    )
    _seed_reference(
        factory,
        surface="ontology",
        reference_id="manufacturing-ontology",
        payload=_migration_payload("0030_ontology_reference.py", "ONTOLOGY_PAYLOAD"),
    )
    _seed_reference(
        factory,
        surface="approvals",
        reference_id="manufacturing-approval-inbox",
        payload=_migration_payload(
            "0027_approval_inbox_reference.py",
            "APPROVAL_INBOX_PAYLOAD",
        ),
    )
    _seed_reference(
        factory,
        surface="workflows",
        reference_id="manufacturing-workflow-console",
        payload=_migration_payload(
            "0026_workflow_console_reference.py",
            "WORKFLOW_CONSOLE_PAYLOAD",
        ),
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
    seed_reference_records(factory)
    yield factory
    engine.dispose()


def supplier_action_request(
    *,
    idempotency_key: str = "tenant_demo_manufacturing:request_supplier_expedite:history",
) -> ActionRunRequest:
    return ActionRunRequest(
        actor_id="agent_supply_risk",
        actor_scopes=["supply:read", "approvals:supply:request"],
        idempotency_key=idempotency_key,
        payload={
            "supplier_batch_id": "asset_motors_batch",
            "target_arrival": "2026-06-22T08:00:00+02:00",
            "reason": "Line 2 packaging risk",
            "cost_ceiling_eur": "1200",
        },
    )


def supplier_approval_request() -> ApprovalDecisionRequest:
    return ApprovalDecisionRequest(
        decision=ApprovalDecision.APPROVE,
        actor_id="plant-operations-owner-role",
        actor_scopes=["approvals:supply:decide"],
        note="Approved for workflow history persistence test.",
    )


def supplier_outcome_request() -> ActionRunOutcomeRequest:
    return ActionRunOutcomeRequest(
        actor_id="workflow-runtime",
        actor_scopes=["actions:result:record"],
        idempotency_key="supplier-expedite-history-outcome",
        status="dry_run_completed",
        result_summary="Supplier expedite dry-run package generated.",
        evidence_refs=["audit_supplier_expedite_preview"],
        metrics={"external_mutations": 0},
    )


def workflow_history_rows(
    factory: sessionmaker[Session],
) -> tuple[list[WorkflowRunRecord], list[WorkflowTimelineRecord]]:
    with factory() as session:
        runs = list(session.scalars(select(WorkflowRunRecord)))
        events = list(
            session.scalars(
                select(WorkflowTimelineRecord).order_by(WorkflowTimelineRecord.sequence)
            )
        )
    return runs, events


async def test_flag_off_records_no_workflow_history(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        action_result = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            runtime,
        )
        approval_result = await record_demo_approval_decision(
            repository,
            SUPPLIER_APPROVAL_ID,
            supplier_approval_request(),
            runtime,
        )

    runs, events = workflow_history_rows(session_factory)
    assert runs == []
    assert events == []
    assert action_result.persisted is True
    assert action_result.workflow_state_updated is False
    assert approval_result.persisted is True
    assert approval_result.workflow_state_updated is False


async def test_flag_on_action_run_bootstraps_run_and_appends_timeline_event(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )

    runs, events = workflow_history_rows(session_factory)
    assert result.workflow_state_updated is True
    assert result.workflow_state == "action_proposed"
    assert result.workflow_status == "action_required"
    assert len(runs) == 1
    run = runs[0]
    assert run.tenant_id == TENANT_ID
    assert run.workflow_id == SUPPLIER_WORKFLOW_ID
    assert run.name == "Supplier Delay Review"
    assert run.domain == "Supply"
    assert run.owner_role == "plant-operations-owner"
    assert run.adapter == "axis-temporal-adapter"
    assert run.audit_scope == SUPPLIER_WORKFLOW_ID
    assert run.state == "action_proposed"
    assert run.replay_ready is True
    assert run.pending_signals[-1]["signal"] == "action.requested"
    assert run.pending_signals[-1]["action_run_id"] == str(result.action_run_id)
    assert len(events) == 1
    event = events[0]
    assert event.tenant_id == TENANT_ID
    assert event.workflow_id == SUPPLIER_WORKFLOW_ID
    assert event.sequence == 1
    assert event.event == "workflow.action_run.recorded"
    assert event.actor == "agent_supply_risk"
    assert event.result == "action_signal_requested"
    assert str(result.action_run_id) in event.summary


async def test_flag_on_approval_decision_bootstraps_run_and_appends_timeline_event(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_approval_decision(
            repository,
            SUPPLIER_APPROVAL_ID,
            supplier_approval_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )

    runs, events = workflow_history_rows(session_factory)
    assert result.workflow_state_updated is True
    assert result.workflow_state == "approval_approved"
    assert result.workflow_status == "ready"
    assert len(runs) == 1
    run = runs[0]
    assert run.workflow_id == SUPPLIER_WORKFLOW_ID
    assert run.state == "approval_approved"
    assert run.replay_ready is True
    matched_signal = next(
        signal
        for signal in run.pending_signals
        if signal.get("approval_id") == SUPPLIER_APPROVAL_ID
    )
    assert matched_signal["status"] == "approved"
    assert matched_signal["decided_by"] == "plant-operations-owner-role"
    assert len(events) == 1
    assert events[0].event == "workflow.approval_decision.recorded"
    assert events[0].actor == "plant-operations-owner-role"
    assert events[0].result == "approved"
    assert SUPPLIER_APPROVAL_ID in events[0].summary


async def test_flag_on_multiple_signals_correlate_to_one_run(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        action_result = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )
        await record_demo_approval_decision(
            repository,
            SUPPLIER_APPROVAL_ID,
            supplier_approval_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )
        outcome_result = await record_demo_action_run_outcome(
            repository,
            action_result.action_run_id,
            supplier_outcome_request(),
            workflow_history_persistence_enabled=True,
        )

    runs, events = workflow_history_rows(session_factory)
    assert len(runs) == 1
    assert runs[0].workflow_id == SUPPLIER_WORKFLOW_ID
    assert runs[0].state == "action_completed"
    assert outcome_result.workflow_state_updated is True
    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.event for event in events] == [
        "workflow.action_run.recorded",
        "workflow.approval_decision.recorded",
        "workflow.action_run.completed",
    ]
    assert events[2].result == "dry_run_completed"


async def test_flag_on_idempotent_action_run_replay_does_not_duplicate_history(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        first = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )
        replay = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )

    runs, events = workflow_history_rows(session_factory)
    assert first.idempotent_replay is False
    assert replay.idempotent_replay is True
    assert replay.action_run_id == first.action_run_id
    assert len(runs) == 1
    assert len(events) == 1


async def test_flag_on_unknown_workflow_id_skips_history_without_failing(
    session_factory: sessionmaker[Session],
) -> None:
    inbox_payload = _migration_payload(
        "0027_approval_inbox_reference.py",
        "APPROVAL_INBOX_PAYLOAD",
    )
    approval = next(
        item
        for item in inbox_payload["approvals"]
        if item["approval_id"] == SUPPLIER_APPROVAL_ID
    )
    approval["workflow_id"] = "wf_not_in_console_reference"
    _seed_reference(
        session_factory,
        surface="approvals",
        reference_id="manufacturing-approval-inbox",
        payload=inbox_payload,
    )
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_approval_decision(
            repository,
            SUPPLIER_APPROVAL_ID,
            supplier_approval_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )

    runs, events = workflow_history_rows(session_factory)
    assert result.persisted is True
    assert result.workflow_state_updated is False
    assert runs == []
    assert events == []


async def test_flag_on_history_is_tenant_scoped(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            runtime,
            workflow_history_persistence_enabled=True,
        )
        assert repository.list_workflow_runs(TENANT_ID) != []
        assert repository.list_workflow_runs("tenant_other") == []
        assert repository.list_workflow_timeline_events(
            "tenant_other",
            SUPPLIER_WORKFLOW_ID,
        ) == []
        assert ensure_workflow_run(repository, "tenant_other", SUPPLIER_WORKFLOW_ID) is None

    runs, events = workflow_history_rows(session_factory)
    assert all(run.tenant_id == TENANT_ID for run in runs)
    assert all(event.tenant_id == TENANT_ID for event in events)


def test_ensure_workflow_run_is_idempotent(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        first = ensure_workflow_run(repository, TENANT_ID, SUPPLIER_WORKFLOW_ID)
        second = ensure_workflow_run(repository, TENANT_ID, SUPPLIER_WORKFLOW_ID)
        assert first is not None
        assert second is not None
        assert first.id == second.id

    runs, events = workflow_history_rows(session_factory)
    assert len(runs) == 1
    assert events == []


def seed_workflow_signal_policy_sets(factory: sessionmaker[Session]) -> None:
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        for policy_id, required_signal_status in (
            ("policy_gate_signal_approved", "approved"),
            ("policy_gate_signal_waiting", "waiting_for_approval"),
        ):
            repository.create_connector_promotion_policy(
                ConnectorPromotionPolicyCreate(
                    tenant_id=TENANT_ID,
                    connector_id="file_csv_manufacturing_assets",
                    policy_id=policy_id,
                    policy_version="2026-07-10.1",
                    status="enabled",
                    enforcement_mode="required",
                    created_by="connector-governance-owner-role",
                    required_scopes=["connectors:ontology:promote"],
                    required_manual_import_status="approval_required",
                    required_workflow_signal_status=required_signal_status,
                    allowed_risk_levels=["high", "medium"],
                    allowed_ontology_types=["manufacturing_asset"],
                    review_window_hours=24,
                )
            )
        for policy_set_id, version, policy_ids in (
            ("policy_set_history_baseline", "2026-07-10.1", ["policy_gate_signal_approved"]),
            ("policy_set_history_candidate", "2026-07-10.2", ["policy_gate_signal_waiting"]),
        ):
            repository.create_connector_promotion_policy_set(
                ConnectorPromotionPolicySetCreate(
                    tenant_id=TENANT_ID,
                    connector_id="file_csv_manufacturing_assets",
                    policy_set_id=policy_set_id,
                    policy_set_version=version,
                    status="active",
                    activated_by="connector-governance-owner-role",
                    policy_ids=policy_ids,
                    activation_reason="Seed policy sets for workflow history replay test.",
                )
            )


def test_fresh_stack_api_actions_produce_replayable_history_and_policy_set_diff(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            workflow_history_persistence_enabled=True,
            replay_arbitrary_policy_set_diff_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RecordingWorkflowRuntime()
    seed_workflow_signal_policy_sets(session_factory)
    client = TestClient(app)

    empty_replay = client.get(
        "/demo/manufacturing/simulation/replay",
        params={"tenant_id": TENANT_ID},
    )
    assert empty_replay.status_code == 200
    assert empty_replay.json()["artifacts"] == []

    decision_response = client.post(
        f"/demo/manufacturing/approvals/{SUPPLIER_APPROVAL_ID}/decision",
        json={
            "decision": "approve",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": ["approvals:supply:decide"],
            "note": "Approved on a fresh stack to prove replay reachability.",
        },
    )
    assert decision_response.status_code == 201
    assert decision_response.json()["workflow_state_updated"] is True
    assert decision_response.json()["workflow_state"] == "approval_approved"

    replay_response = client.get(
        "/demo/manufacturing/simulation/replay",
        params={"tenant_id": TENANT_ID},
    )
    assert replay_response.status_code == 200
    replay_body = replay_response.json()
    assert len(replay_body["artifacts"]) == 1
    artifact = replay_body["artifacts"][0]
    assert artifact["workflow_id"] == SUPPLIER_WORKFLOW_ID
    assert artifact["replay_ready"] is True
    assert artifact["determinism_status"] == "replay_ready"
    assert artifact["timeline_event_count"] >= 1
    assert artifact["timeline"][0]["event"] == "workflow.approval_decision.recorded"
    assert artifact["timeline"][0]["result"] == "approved"
    assert artifact["audit_event_count"] >= 1

    diff_response = client.get(
        "/demo/manufacturing/simulation/replay",
        params={
            "tenant_id": TENANT_ID,
            "baseline_policy_set_id": "policy_set_history_baseline",
            "candidate_policy_set_id": "policy_set_history_candidate",
            "connector_id": "file_csv_manufacturing_assets",
        },
    )
    assert diff_response.status_code == 200
    diff = diff_response.json()["artifacts"][0]["policy_set_diffs"][0]
    assert diff["baseline_policy_set_id"] == "policy_set_history_baseline"
    assert diff["candidate_policy_set_id"] == "policy_set_history_candidate"
    assert diff["events_evaluated"] >= 2
    assert diff["changed_outcome"] is True
    assert diff["diff_status"] == "changed_outcome_detected"
    timeline_decisions = [
        decision
        for decision in diff["event_decisions"]
        if decision["event_kind"] == "timeline"
    ]
    assert len(timeline_decisions) == 1
    assert timeline_decisions[0]["baseline_decision"] == "allow_historical_event"
    assert timeline_decisions[0]["candidate_decision"] == "block_until_required_policy_gate"
    assert timeline_decisions[0]["changed_outcome"] is True

    console_response = client.get(
        "/demo/manufacturing/workflows/runs",
        params={"tenant_id": TENANT_ID},
    )
    client.close()
    assert console_response.status_code == 200
    console_runs = console_response.json()["workflow_runs"]
    assert len(console_runs) == 1
    assert console_runs[0]["workflow_id"] == SUPPLIER_WORKFLOW_ID
    assert console_runs[0]["state"] == "approval_approved"
    assert console_runs[0]["timeline"][-1]["event"] == "workflow.approval_decision.recorded"
