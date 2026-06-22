from copy import deepcopy
from pathlib import Path
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.approval_decisions import ApprovalDecisionRequest, record_demo_approval_decision
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.demo import ApprovalDecision
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import ApprovalRecord, AuditEvent, Base
from axis_api.persistence import AxisPersistenceRepository, DemoReferenceRecordCreate
from axis_api.workflow_runtime import (
    WorkflowSignalError,
    WorkflowSignalRequest,
    WorkflowSignalResult,
)

MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations" / "versions"


class RecordingWorkflowRuntime:
    def __init__(self) -> None:
        self.requests: list[WorkflowSignalRequest] = []

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


class FailingWorkflowRuntime:
    async def signal_approval_decision(
        self,
        request: WorkflowSignalRequest,
    ) -> WorkflowSignalResult:
        raise WorkflowSignalError("synthetic_runtime_down")


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
    seed_approval_inbox_reference(factory, approval_inbox_bootstrap_payload())
    yield factory
    engine.dispose()


@pytest.fixture
def empty_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def approval_inbox_bootstrap_payload() -> dict:
    migration = run_path(str(MIGRATIONS_DIR / "0027_approval_inbox_reference.py"))
    return deepcopy(migration["APPROVAL_INBOX_PAYLOAD"])


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


def seed_approval_inbox_reference(
    factory: sessionmaker[Session],
    payload: dict | None = None,
) -> None:
    inbox_payload = deepcopy(payload or approval_inbox_bootstrap_payload())
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="approvals",
                reference_id="manufacturing-approval-inbox",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=inbox_payload,
            )
        )


async def test_record_demo_approval_decision_reads_persisted_approval_inbox_reference(
    session_factory: sessionmaker[Session],
) -> None:
    seed_approval_inbox_reference(session_factory, persisted_approval_inbox_payload())
    workflow_runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_approval_decision(
            repository,
            "appr_persisted_operations_review",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.APPROVE,
                actor_id="plant-operations-owner-role",
                actor_scopes=["approvals:operations:decide"],
                note="Approved persisted reference.",
            ),
            workflow_runtime,
        )

    with session_factory() as session:
        approval = session.scalars(select(ApprovalRecord)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert result.approval_id == "appr_persisted_operations_review"
    assert result.workflow_id == "wf_persisted_reference"
    assert result.action_id == "appr_persisted_operations_review"
    assert approval.workflow_id == "wf_persisted_reference"
    assert audit_event.payload["required_permission"] == "approvals:operations:decide"
    assert workflow_runtime.requests[0].workflow_id == "wf_persisted_reference"


def test_approval_decision_endpoint_reports_missing_approval_reference_record(
    empty_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = empty_session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision",
        json={
            "decision": "approve",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": ["approvals:supply:decide"],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "NOT_FOUND",
        "message": "Manufacturing approval inbox reference record not found.",
        "surface": "approvals",
    }


async def test_record_demo_approval_decision_persists_approval_and_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    workflow_runtime = RecordingWorkflowRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_approval_decision(
            repository,
            "appr_expedite_supplier_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.APPROVE,
                actor_id="plant-operations-owner-role",
                actor_scopes=["approvals:supply:decide"],
                note="Approved in synthetic test scope.",
            ),
            workflow_runtime,
        )

    with session_factory() as session:
        approval = session.scalars(select(ApprovalRecord)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert result.persisted is True
    assert result.permission_decision.allowed is True
    assert result.permission_decision.reason == "allowed"
    assert result.workflow_signal_status == "approval_signaled"
    assert result.workflow_signal.payload == {
        "approval_id": "appr_expedite_supplier_batch",
        "approved": True,
        "decision": "approve",
    }
    assert result.action_id == "request_supplier_expedite"
    assert result.audit_event_id == audit_event.id
    assert approval.status == "approve"
    assert approval.decision_actor_id == "plant-operations-owner-role"
    assert approval.decided_at is not None
    assert audit_event.event_type == "approval.decision.recorded"
    assert audit_event.payload["approval_id"] == "appr_expedite_supplier_batch"
    assert audit_event.payload["decision"] == "approve"
    assert audit_event.payload["permission_decision"] == {
        "allowed": True,
        "reason": "allowed",
    }
    assert audit_event.payload["workflow_signal"]["status"] == "approval_signaled"
    assert audit_event.payload["decision_note_recorded"] == "true"
    assert workflow_runtime.requests[0].workflow_id == "wf_supplier_delay_review"
    assert workflow_runtime.requests[0].approved is True


async def test_record_demo_approval_decision_reuses_existing_approval_record(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        await record_demo_approval_decision(
            repository,
            "appr_quality_hold_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.REQUEST_CHANGES,
                actor_id="quality-owner-role",
                actor_scopes=["approvals:quality:decide"],
            ),
            RecordingWorkflowRuntime(),
        )
        await record_demo_approval_decision(
            repository,
            "appr_quality_hold_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.REJECT,
                actor_id="quality-owner-role",
                actor_scopes=["approvals:quality:decide"],
            ),
            RecordingWorkflowRuntime(),
        )

    with session_factory() as session:
        approvals = list(session.scalars(select(ApprovalRecord)))
        audit_events = list(session.scalars(select(AuditEvent)))

    assert len(approvals) == 1
    assert approvals[0].status == "reject"
    assert len(audit_events) == 2


def test_approval_decision_endpoint_persists_result(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RecordingWorkflowRuntime()
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_shift_maintenance_window/decision",
        json={
            "decision": "approve",
            "actor_id": "maintenance-owner-role",
            "actor_scopes": ["approvals:maintenance:decide"],
            "note": "Approved in synthetic endpoint test.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["approval_id"] == "appr_shift_maintenance_window"
    assert body["action_id"] == "shift_maintenance_window"
    assert body["audit_event_type"] == "approval.decision.recorded"
    assert body["permission_decision"] == {"allowed": True, "reason": "allowed"}
    assert body["workflow_signal_status"] == "approval_signaled"
    assert body["workflow_signal"]["payload"] == {
        "approval_id": "appr_shift_maintenance_window",
        "approved": True,
        "decision": "approve",
    }

    with session_factory() as session:
        approval = session.scalars(select(ApprovalRecord)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert approval.status == "approve"
    assert approval.decision_actor_id == "maintenance-owner-role"
    assert audit_event.actor_id == "maintenance-owner-role"


def test_approval_decision_endpoint_binds_actor_and_scopes_from_oidc_token(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RecordingWorkflowRuntime()
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="plant-operations-owner-role",
            tenant_id="tenant_demo_manufacturing",
            scopes=["approvals:supply:decide"],
        )
    )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision",
        headers={"Authorization": "Bearer valid-token"},
        json={
            "decision": "approve",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": [],
            "note": "Approved with token-derived scopes.",
        },
    )

    assert response.status_code == 201
    assert response.json()["actor_id"] == "plant-operations-owner-role"
    assert response.json()["permission_decision"] == {"allowed": True, "reason": "allowed"}
    with session_factory() as session:
        audit_event = session.scalars(select(AuditEvent)).one()
    assert audit_event.actor_id == "plant-operations-owner-role"


def test_approval_decision_endpoint_requires_oidc_when_configured(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision",
        json={
            "decision": "approve",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": ["approvals:supply:decide"],
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


def test_approval_decision_endpoint_rejects_oidc_actor_impersonation(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="plant-operations-owner-role",
            tenant_id="tenant_demo_manufacturing",
            scopes=["approvals:supply:decide"],
        )
    )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision",
        headers={"Authorization": "Bearer valid-token"},
        json={
            "decision": "approve",
            "actor_id": "quality-owner-role",
            "actor_scopes": ["approvals:supply:decide"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "PERMISSION_DENIED",
        "message": "The request actor does not match the authenticated OIDC actor.",
        "reason": "actor_mismatch",
    }


def test_approval_decision_endpoint_rejects_oidc_tenant_mismatch(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="plant-operations-owner-role",
            tenant_id="tenant_other",
            scopes=["approvals:supply:decide"],
        )
    )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision",
        headers={"Authorization": "Bearer valid-token"},
        json={
            "decision": "approve",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": ["approvals:supply:decide"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "PERMISSION_DENIED",
        "message": "The authenticated OIDC tenant cannot access this tenant scope.",
        "reason": "tenant_mismatch",
    }
    with session_factory() as session:
        assert session.scalars(select(AuditEvent)).all() == []


async def test_approval_decision_records_signal_failure_without_blocking_persistence(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await record_demo_approval_decision(
            repository,
            "appr_quality_hold_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.REJECT,
                actor_id="quality-owner-role",
                actor_scopes=["approvals:quality:decide"],
            ),
            FailingWorkflowRuntime(),
        )

    with session_factory() as session:
        approval = session.scalars(select(ApprovalRecord)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert approval.status == "reject"
    assert result.workflow_signal_status == "runtime_signal_unavailable"
    assert result.workflow_signal.payload["reason"] == "synthetic_runtime_down"
    assert audit_event.payload["workflow_signal"]["status"] == "runtime_signal_unavailable"


def test_approval_decision_endpoint_handles_missing_approval(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/missing/decision",
        json={"decision": "approve", "actor_id": "plant-operations-owner-role"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found"


def test_approval_decision_endpoint_denies_actor_without_required_scope(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision",
        json={
            "decision": "approve",
            "actor_id": "quality-owner-role",
            "actor_scopes": ["approvals:quality:decide"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "PERMISSION_DENIED",
        "message": "The actor cannot decide this approval.",
        "required_permission": "approvals:supply:decide",
        "reason": "missing_scope:approvals:supply:decide",
    }

    with session_factory() as session:
        assert list(session.scalars(select(ApprovalRecord))) == []
        assert list(session.scalars(select(AuditEvent))) == []


def test_openapi_exposes_approval_decision_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/approvals/{approval_id}/decision" in response.json()["paths"]
