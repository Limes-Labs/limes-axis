from __future__ import annotations

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
from axis_api.models import ApprovalDecisionOutbox, ApprovalRecord, AuditEvent, Base
from axis_api.persistence import (
    ApprovalDecisionOutboxCreate,
    AxisPersistenceRepository,
    DemoReferenceRecordCreate,
)

MIGRATIONS_DIR = Path(__file__).parents[1] / "migrations" / "versions"


class RuntimeMustNotBeCalled:
    def __init__(self) -> None:
        self.call_count = 0

    async def signal_approval_decision(self, request: object) -> None:
        self.call_count += 1
        raise AssertionError("transactional outbox mode must not signal during the API request")


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


class FailingOutboxRepository(AxisPersistenceRepository):
    def create_approval_decision_outbox(
        self, record: ApprovalDecisionOutboxCreate
    ) -> ApprovalDecisionOutbox:
        raise RuntimeError("synthetic outbox insert failure")


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    migration = run_path(str(MIGRATIONS_DIR / "0027_approval_inbox_reference.py"))
    payload = deepcopy(migration["APPROVAL_INBOX_PAYLOAD"])
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id=payload["tenant_id"],
                surface="approvals",
                reference_id="manufacturing-approval-inbox",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    yield factory
    engine.dispose()


def _decision_payload() -> dict:
    return {
        "decision": "approve",
        "actor_id": "plant-operations-owner-role",
        "actor_scopes": ["approvals:supply:decide"],
        "note": "Approved once through the durable outbox.",
    }


def test_api_atomically_enqueues_once_and_exact_replay_reuses_the_event(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            approval_decision_outbox_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    runtime = RuntimeMustNotBeCalled()
    app.state.workflow_runtime = runtime
    client = TestClient(app)
    endpoint = "/demo/manufacturing/approvals/appr_expedite_supplier_batch/decision"

    first = client.post(endpoint, json=_decision_payload())
    replay = client.post(endpoint, json=_decision_payload())

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["decision_event_id"] == first.json()["decision_event_id"]
    assert replay.json()["audit_event_id"] == first.json()["audit_event_id"]
    assert runtime.call_count == 0

    with session_factory() as session:
        outboxes = list(session.scalars(select(ApprovalDecisionOutbox)))
        approvals = list(session.scalars(select(ApprovalRecord)))
        audits = list(session.scalars(select(AuditEvent)))

    assert len(outboxes) == 1
    assert len(approvals) == 1
    assert len(audits) == 1
    row = outboxes[0]
    event_id = first.json()["decision_event_id"]
    assert str(row.id) == event_id
    assert row.payload["decision_event_id"] == event_id
    assert row.payload["tenant_id"] == row.tenant_id
    assert row.payload["workflow_id"] == row.workflow_id
    assert row.payload["approval_id"] == row.approval_id
    assert row.payload["decision"] == row.decision
    assert row.payload["actor_id"] == row.decision_actor_id
    assert row.status == "pending"
    assert row.attempt_count == 0


def test_decision_delivery_returns_404_when_no_outbox_row_exists(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory

    response = TestClient(app).get(
        "/demo/manufacturing/approvals/appr_missing/decision-delivery"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "NOT_FOUND",
        "message": "Approval decision delivery record not found.",
        "approval_id": "appr_missing",
    }


def test_decision_delivery_exposes_operational_metadata_without_lease_or_payload(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            approval_decision_outbox_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RuntimeMustNotBeCalled()
    client = TestClient(app)
    approval_id = "appr_expedite_supplier_batch"

    decision = client.post(
        f"/demo/manufacturing/approvals/{approval_id}/decision",
        json=_decision_payload(),
    )
    delivery = client.get(
        f"/demo/manufacturing/approvals/{approval_id}/decision-delivery"
    )

    assert decision.status_code == 201
    assert delivery.status_code == 200
    body = delivery.json()
    assert set(body) == {
        "tenant_id",
        "approval_id",
        "decision_event_id",
        "workflow_id",
        "status",
        "attempt_count",
        "available_at",
        "last_attempt_at",
        "delivered_at",
        "dead_lettered_at",
        "last_error_code",
    }
    assert body["decision_event_id"] == decision.json()["decision_event_id"]
    assert body["status"] == "pending"
    assert body["attempt_count"] == 0
    assert body["last_attempt_at"] is None
    assert body["delivered_at"] is None
    assert body["dead_lettered_at"] is None
    assert body["last_error_code"] is None
    assert "claim_token" not in body
    assert "lease_expires_at" not in body
    assert "payload" not in body
    assert "decision_actor_id" not in body


def test_decision_delivery_read_is_bound_to_authenticated_tenant(
    session_factory: sessionmaker[Session],
) -> None:
    bootstrap_app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            approval_decision_outbox_enabled=True,
        )
    )
    bootstrap_app.state.session_factory = session_factory
    bootstrap_app.state.workflow_runtime = RuntimeMustNotBeCalled()
    approval_id = "appr_expedite_supplier_batch"
    created = TestClient(bootstrap_app).post(
        f"/demo/manufacturing/approvals/{approval_id}/decision",
        json=_decision_payload(),
    )
    assert created.status_code == 201

    app = create_app(
        Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True)
    )
    app.state.session_factory = session_factory
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="plant-operations-owner-role",
            tenant_id="tenant_demo_manufacturing",
            scopes=["approvals:supply:decide"],
        )
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer valid-token"}

    own_tenant = client.get(
        f"/demo/manufacturing/approvals/{approval_id}/decision-delivery",
        headers=headers,
    )
    other_tenant = client.get(
        f"/demo/manufacturing/approvals/{approval_id}/decision-delivery",
        params={"tenant_id": "tenant_other"},
        headers=headers,
    )

    assert own_tenant.status_code == 200
    assert other_tenant.status_code == 403
    assert other_tenant.json()["detail"]["reason"] == "tenant_mismatch"


async def test_outbox_insert_failure_rolls_back_the_terminal_decision(
    session_factory: sessionmaker[Session],
) -> None:
    with (
        pytest.raises(RuntimeError, match="synthetic outbox insert failure"),
        session_scope(session_factory) as session,
    ):
        await record_demo_approval_decision(
            FailingOutboxRepository(session),
            "appr_expedite_supplier_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.APPROVE,
                actor_id="plant-operations-owner-role",
                actor_scopes=["approvals:supply:decide"],
                note="This entire transaction must roll back.",
            ),
            RuntimeMustNotBeCalled(),
            workflow_signal_outbox_enabled=True,
        )

    with session_factory() as session:
        assert list(session.scalars(select(ApprovalDecisionOutbox))) == []
        assert list(session.scalars(select(ApprovalRecord))) == []
        assert list(session.scalars(select(AuditEvent))) == []
