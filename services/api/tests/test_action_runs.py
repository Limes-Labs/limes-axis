import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.action_runs import (
    ActionPayloadValidationError,
    ActionPermissionDenied,
    ActionRunIdempotencyConflict,
    ActionRunRequest,
    record_demo_action_run,
)
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import ActionRun, AuditEvent, Base
from axis_api.persistence import AxisPersistenceRepository
from axis_api.workflow_runtime import WorkflowSignalError, WorkflowSignalResult


class RecordingActionWorkflowRuntime:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def signal_action_run(self, request: object) -> WorkflowSignalResult:
        self.requests.append(request)
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="action_signal_requested",
            adapter="axis-test-action-workflow-adapter",
            signal_name=request.signal_name,
            payload={
                "action_id": request.action_id,
                "action_run_id": str(request.action_run_id),
                "idempotency_key": request.idempotency_key,
                "approval_id": request.approval_id,
                "payload_field_names": sorted(request.payload.keys()),
            },
        )


class FailingActionWorkflowRuntime:
    async def signal_action_run(self, request: object) -> WorkflowSignalResult:
        raise WorkflowSignalError("synthetic_action_runtime_down")


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


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


def supplier_action_request(
    *,
    idempotency_key: str = "tenant_demo_manufacturing:request_supplier_expedite:test",
    reason: str = "Line 2 packaging risk",
) -> ActionRunRequest:
    return ActionRunRequest(
        actor_id="agent_supply_risk",
        actor_scopes=["supply:read", "approvals:supply:request"],
        idempotency_key=idempotency_key,
        payload={
            "supplier_batch_id": "asset_motors_batch",
            "target_arrival": "2026-06-22T08:00:00+02:00",
            "reason": reason,
            "cost_ceiling_eur": "1200",
        },
    )


async def test_record_demo_action_run_persists_run_and_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
        )

    with session_factory() as session:
        action_run = session.scalars(select(ActionRun)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert result.persisted is True
    assert result.idempotent_replay is False
    assert result.action_run_id == action_run.id
    assert result.action_id == "request_supplier_expedite"
    assert result.status == "approval_required"
    assert result.execution_mode == "approval_gated_dry_run"
    assert result.requested_by == "agent_supply_risk"
    assert result.approval_required is True
    assert result.approval_id == "appr_expedite_supplier_batch"
    assert result.workflow_id == "wf_supplier_delay_review"
    assert result.permission_decision.allowed is True
    assert result.audit_event_id == audit_event.id
    assert result.audit_event_type == "action.proposal.created"
    assert action_run.payload["input"]["supplier_batch_id"] == "asset_motors_batch"
    assert audit_event.event_type == "action.proposal.created"
    assert audit_event.payload["action_run_id"] == str(action_run.id)
    assert audit_event.payload["permission_decision"] == {"allowed": True, "reason": "allowed"}
    assert audit_event.payload["payload_field_names"] == [
        "cost_ceiling_eur",
        "reason",
        "supplier_batch_id",
        "target_arrival",
    ]


async def test_record_demo_action_run_signals_bound_workflow_after_persistence(
    session_factory: sessionmaker[Session],
) -> None:
    workflow_runtime = RecordingActionWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            workflow_runtime,
        )

    with session_factory() as session:
        action_run = session.scalars(select(ActionRun)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert result.workflow_signal_status == "action_signal_requested"
    assert result.workflow_signal is not None
    assert result.workflow_signal.payload == {
        "action_id": "request_supplier_expedite",
        "action_run_id": str(action_run.id),
        "idempotency_key": "tenant_demo_manufacturing:request_supplier_expedite:test",
        "approval_id": "appr_expedite_supplier_batch",
        "payload_field_names": [
            "cost_ceiling_eur",
            "reason",
            "supplier_batch_id",
            "target_arrival",
        ],
    }
    assert workflow_runtime.requests[0].workflow_id == "wf_supplier_delay_review"
    assert workflow_runtime.requests[0].action_id == "request_supplier_expedite"
    assert workflow_runtime.requests[0].action_run_id == action_run.id
    assert workflow_runtime.requests[0].approval_id == "appr_expedite_supplier_batch"
    assert workflow_runtime.requests[0].payload["supplier_batch_id"] == "asset_motors_batch"
    assert audit_event.payload["workflow_signal"]["status"] == "action_signal_requested"
    assert audit_event.payload["workflow_signal"]["payload"]["payload_field_names"] == [
        "cost_ceiling_eur",
        "reason",
        "supplier_batch_id",
        "target_arrival",
    ]
    assert "payload" not in audit_event.payload["workflow_signal"]["payload"]


async def test_record_demo_action_run_records_signal_failure_without_blocking_persistence(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(),
            FailingActionWorkflowRuntime(),
        )

    with session_factory() as session:
        action_run = session.scalars(select(ActionRun)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert action_run.status == "approval_required"
    assert result.workflow_signal_status == "runtime_signal_unavailable"
    assert result.workflow_signal is not None
    assert result.workflow_signal.payload["reason"] == "synthetic_action_runtime_down"
    assert audit_event.payload["workflow_signal"]["status"] == "runtime_signal_unavailable"


async def test_record_demo_action_run_replays_same_idempotency_key_without_duplicate_audit(
    session_factory: sessionmaker[Session],
) -> None:
    request = supplier_action_request()
    workflow_runtime = RecordingActionWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        first = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            request,
            workflow_runtime,
        )
        second = await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            request,
            workflow_runtime,
        )

    with session_factory() as session:
        action_runs = list(session.scalars(select(ActionRun)))
        audit_events = list(session.scalars(select(AuditEvent)))

    assert first.action_run_id == second.action_run_id
    assert second.idempotent_replay is True
    assert second.workflow_signal_status == "idempotent_replay"
    assert second.audit_event_id is None
    assert len(workflow_runtime.requests) == 1
    assert len(action_runs) == 1
    assert len(audit_events) == 1


async def test_record_demo_action_run_rejects_same_idempotency_key_with_different_payload(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        await record_demo_action_run(
            repository,
            "request_supplier_expedite",
            supplier_action_request(reason="Line 2 packaging risk"),
        )
        with pytest.raises(ActionRunIdempotencyConflict):
            await record_demo_action_run(
                repository,
                "request_supplier_expedite",
                supplier_action_request(reason="Changed payload"),
            )

    with session_factory() as session:
        assert len(list(session.scalars(select(ActionRun)))) == 1
        assert len(list(session.scalars(select(AuditEvent)))) == 1


async def test_record_demo_action_run_denies_actor_without_required_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(ActionPermissionDenied, match="missing_scope:approvals:supply:request"):
            await record_demo_action_run(
                repository,
                "request_supplier_expedite",
                ActionRunRequest(
                    actor_id="agent_quality_risk",
                    actor_scopes=["supply:read"],
                    idempotency_key="denied-key",
                    payload=supplier_action_request().payload,
                ),
            )

    with session_factory() as session:
        assert list(session.scalars(select(ActionRun))) == []
        assert list(session.scalars(select(AuditEvent))) == []


async def test_record_demo_action_run_validates_typed_payload_before_persistence(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(ActionPayloadValidationError) as exc_info:
            await record_demo_action_run(
                repository,
                "request_supplier_expedite",
                ActionRunRequest(
                    actor_id="agent_supply_risk",
                    actor_scopes=["supply:read", "approvals:supply:request"],
                    idempotency_key="invalid-payload",
                    payload={"supplier_batch_id": "asset_motors_batch"},
                ),
            )

    assert "missing_required:target_arrival" in exc_info.value.issues
    with session_factory() as session:
        assert list(session.scalars(select(ActionRun))) == []
        assert list(session.scalars(select(AuditEvent))) == []


async def test_record_demo_action_run_derives_optional_idempotency_for_preview_action(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_action_run(
            repository,
            "generate_daily_plant_brief",
            ActionRunRequest(
                actor_id="agent_daily_brief",
                actor_scopes=["briefs:generate", "audit:read", "workflows:read"],
                payload={
                    "tenant_id": "tenant_demo_manufacturing",
                    "scope": "daily_operations",
                    "evidence_refs": [
                        "wf_supplier_delay_review",
                        "audit_20260621_154000_ontology_read",
                    ],
                },
            ),
        )

    assert result.status == "preview_generated"
    assert result.approval_required is False
    assert result.idempotency_key == (
        "tenant_demo_manufacturing:generate_daily_plant_brief:agent_daily_brief:preview"
    )
    assert result.audit_event_type == "action.preview.generated"


def test_action_run_endpoint_returns_created_then_idempotent_replay(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RecordingActionWorkflowRuntime()
    client = TestClient(app)
    payload = supplier_action_request().model_dump()

    first = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        json=payload,
    )
    second = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["action_run_id"] == second_body["action_run_id"]
    assert first_body["idempotent_replay"] is False
    assert first_body["workflow_signal_status"] == "action_signal_requested"
    assert first_body["workflow_signal"]["signal_name"] == "action_requested"
    assert second_body["idempotent_replay"] is True
    assert second_body["workflow_signal_status"] == "idempotent_replay"
    assert second_body["workflow_signal"] is None
    assert second_body["audit_event_id"] is None
    assert len(app.state.workflow_runtime.requests) == 1


def test_action_run_endpoint_binds_actor_and_scopes_from_oidc_token(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RecordingActionWorkflowRuntime()
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="agent_supply_risk",
            tenant_id="tenant_demo_manufacturing",
            scopes=["supply:read", "approvals:supply:request"],
        )
    )
    client = TestClient(app)
    payload = supplier_action_request().model_dump()
    payload["actor_scopes"] = []

    response = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        headers={"Authorization": "Bearer valid-token"},
        json=payload,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["requested_by"] == "agent_supply_risk"
    assert body["permission_decision"] == {"allowed": True, "reason": "allowed"}
    with session_factory() as session:
        audit_event = session.scalars(select(AuditEvent)).one()
    assert audit_event.actor_id == "agent_supply_risk"


def test_action_run_endpoint_returns_validation_and_permission_errors(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    invalid_payload = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        json={
            "actor_id": "agent_supply_risk",
            "actor_scopes": ["supply:read", "approvals:supply:request"],
            "idempotency_key": "invalid-payload",
            "payload": {"supplier_batch_id": "asset_motors_batch"},
        },
    )
    denied = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        json={
            "actor_id": "agent_quality_risk",
            "actor_scopes": ["quality:read"],
            "idempotency_key": "denied-key",
            "payload": supplier_action_request().payload,
        },
    )
    missing = client.post(
        "/demo/manufacturing/actions/missing/runs",
        json=supplier_action_request(idempotency_key="missing-action").model_dump(),
    )

    assert invalid_payload.status_code == 422
    assert invalid_payload.json()["detail"]["code"] == "VALIDATION_FAILED"
    assert "missing_required:target_arrival" in invalid_payload.json()["detail"]["issues"]
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PERMISSION_DENIED"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Action not found"


def test_action_run_endpoint_returns_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    first = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        json=supplier_action_request(reason="Line 2 packaging risk").model_dump(),
    )
    conflict = client.post(
        "/demo/manufacturing/actions/request_supplier_expedite/runs",
        json=supplier_action_request(reason="Changed payload").model_dump(),
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "POLICY_VIOLATION"
    assert conflict.json()["detail"]["action_run_id"] == first.json()["action_run_id"]


def test_openapi_exposes_action_run_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/actions/{action_id}/runs" in response.json()["paths"]
