from copy import deepcopy
from runpy import run_path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import ActionRun, AuditEvent, Base, PlatformPolicy
from axis_api.persistence import AxisPersistenceRepository, DemoReferenceRecordCreate
from axis_api.platform_policies import (
    PlatformPolicyEvaluationContext,
    PlatformPolicyScope,
    evaluate_platform_policies,
)


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


def build_test_client(
    *,
    seed_action_registry: bool = False,
    settings: Settings | None = None,
) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    app = create_app(settings or Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    if seed_action_registry:
        seed_action_registry_reference(factory)
    return TestClient(app), factory


def action_registry_payload() -> dict:
    migration = run_path("migrations/versions/0025_action_registry_reference.py")
    return deepcopy(migration["ACTION_REGISTRY_PAYLOAD"])


def seed_action_registry_reference(factory: sessionmaker[Session]) -> None:
    registry_payload = action_registry_payload()
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="actions",
                reference_id="manufacturing-action-registry",
                status="active",
                source="bootstrap",
                version=registry_payload["schema_version"],
                payload=registry_payload,
            )
        )


def policy_payload(
    *,
    policy_id: str = "policy_platform_high_risk_gate_v1",
    effect: str = "require_approval",
    conditions: dict | None = None,
    tenant_id: str = "tenant_demo_manufacturing",
) -> dict:
    return {
        "tenant_id": tenant_id,
        "policy_id": policy_id,
        "policy_version": "2026-07-05",
        "display_name": "High risk action gate",
        "description": "Gate governed action execution on declared risk conditions.",
        "scope": "action_execution",
        "effect": effect,
        "conditions": conditions
        if conditions is not None
        else {
            "action_domains": ["Operations"],
            "risk_levels": ["low"],
        },
        "created_by": "platform-governance-owner-role",
        "actor_scopes": ["platform:policy:author"],
        "notes": ["Platform policy authored for governed action execution."],
    }


def revision_payload(
    *,
    policy_id: str = "policy_platform_high_risk_gate_v1",
    effect: str = "deny",
    idempotency_key: str = "idem_platform_policy_revision_v2",
) -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "policy_id": policy_id,
        "policy_version": "2026-07-05.2",
        "display_name": "High risk action gate",
        "description": "Deny governed action execution on declared risk conditions.",
        "effect": effect,
        "conditions": {
            "action_domains": ["Operations"],
            "risk_levels": ["low"],
        },
        "updated_by": "platform-governance-owner-role",
        "actor_scopes": ["platform:policy:revise"],
        "idempotency_key": idempotency_key,
        "notes": ["Revision tightens the gate from approval to denial."],
    }


def evaluation_payload(
    *,
    tenant_id: str = "tenant_demo_manufacturing",
    context: dict | None = None,
) -> dict:
    return {
        "tenant_id": tenant_id,
        "actor_id": "platform-governance-owner-role",
        "actor_scopes": ["platform:policy:evaluate"],
        "scope": "action_execution",
        "context": context
        if context is not None
        else {
            "action_id": "generate_daily_plant_brief",
            "action_domain": "Operations",
            "risk_level": "low",
            "autonomy_level": "L1",
        },
    }


def daily_brief_run_payload() -> dict:
    return {
        "actor_id": "agent_daily_brief",
        "actor_scopes": ["briefs:generate", "audit:read", "workflows:read"],
        "idempotency_key": "tenant_demo_manufacturing:generate_daily_plant_brief:test",
        "payload": {
            "tenant_id": "tenant_demo_manufacturing",
            "scope": "daily_operations",
            "evidence_refs": ["wf_supplier_delay_review"],
        },
    }


def test_platform_policy_create_endpoint_persists_policy_and_audit() -> None:
    client, factory = build_test_client()

    response = client.post("/platform/policies", json=policy_payload())

    client.close()
    assert response.status_code == 201
    body = response.json()
    assert body["policy_id"] == "policy_platform_high_risk_gate_v1"
    assert body["revision_number"] == 1
    assert body["status"] == "active"
    assert body["scope"] == "action_execution"
    assert body["effect"] == "require_approval"
    assert body["required_authoring_scope"] == "platform:policy:author"
    assert body["idempotent_replay"] is False
    with factory() as session:
        policy = session.scalars(select(PlatformPolicy)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "platform.policy.authored")
        ).one()

    assert policy.tenant_id == "tenant_demo_manufacturing"
    assert policy.revision_number == 1
    assert policy.status == "active"
    assert body["audit_event_id"] == str(audit_event.id)
    assert audit_event.payload["policy_id"] == "policy_platform_high_risk_gate_v1"
    assert audit_event.payload["effect"] == "require_approval"
    assert audit_event.payload["permission_decision"] == {"allowed": True, "reason": "allowed"}


def test_platform_policy_create_endpoint_rejects_duplicate_policy() -> None:
    client, _ = build_test_client()

    first = client.post("/platform/policies", json=policy_payload())
    second = client.post("/platform/policies", json=policy_payload())

    client.close()
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["reason"] == "policy_already_exists"


def test_platform_policy_create_endpoint_rejects_missing_permission() -> None:
    client, factory = build_test_client()
    payload = policy_payload()
    payload["actor_scopes"] = []

    response = client.post("/platform/policies", json=payload)

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == "platform:policy:author"
    with factory() as session:
        assert list(session.scalars(select(PlatformPolicy))) == []


def test_platform_policy_create_endpoint_rejects_malformed_conditions() -> None:
    client, factory = build_test_client()
    malformed_payloads = [
        policy_payload(conditions={}),
        policy_payload(conditions={"risk_levels": ["catastrophic"]}),
        policy_payload(conditions={"autonomy_levels": ["L9"]}),
        policy_payload(conditions={"unknown_condition": ["x"]}),
        policy_payload(conditions={"requested_amount_at_least": -10}),
    ]

    responses = [client.post("/platform/policies", json=payload) for payload in malformed_payloads]

    client.close()
    for response in responses:
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "VALIDATION_FAILED"
        assert response.json()["detail"]["reason"] == "invalid_rule_conditions"
    with factory() as session:
        assert list(session.scalars(select(PlatformPolicy))) == []


def test_platform_policy_revision_endpoint_appends_revision() -> None:
    client, factory = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    response = client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=revision_payload(),
    )

    client.close()
    assert response.status_code == 201
    body = response.json()
    assert body["revision_number"] == 2
    assert body["status"] == "active"
    assert body["effect"] == "deny"
    assert body["revises_revision_number"] == 1
    assert body["idempotent_replay"] is False
    with factory() as session:
        revisions = list(
            session.scalars(select(PlatformPolicy).order_by(PlatformPolicy.revision_number))
        )
        revised_event = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "platform.policy.revised")
        ).one()

    assert len(revisions) == 2
    assert revisions[0].status == "superseded"
    assert revisions[0].replaced_by_revision_number == 2
    assert revisions[1].status == "active"
    assert revised_event.payload["revision_number"] == 2
    assert revised_event.payload["idempotency_key"] == "idem_platform_policy_revision_v2"


def test_platform_policy_revision_endpoint_replays_idempotent_request() -> None:
    client, factory = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    first = client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=revision_payload(),
    )
    replay = client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=revision_payload(),
    )

    client.close()
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["revision_number"] == 2
    with factory() as session:
        policy_count = len(list(session.scalars(select(PlatformPolicy))))
        revised_event_count = len(
            list(
                session.scalars(
                    select(AuditEvent).where(AuditEvent.event_type == "platform.policy.revised")
                )
            )
        )

    assert policy_count == 2
    assert revised_event_count == 1


def test_platform_policy_revision_endpoint_rejects_idempotency_conflict() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())
    client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=revision_payload(),
    )
    conflicting = revision_payload(effect="allow_with_evidence")

    response = client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=conflicting,
    )

    client.close()
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "revision_idempotency_conflict"


def test_platform_policy_revision_endpoint_rejects_missing_policy() -> None:
    client, _ = build_test_client()

    response = client.post(
        "/platform/policies/policy_platform_missing/revisions",
        json=revision_payload(policy_id="policy_platform_missing"),
    )

    client.close()
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_platform_policy_revision_endpoint_rejects_path_body_mismatch() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    response = client.post(
        "/platform/policies/policy_platform_other/revisions",
        json=revision_payload(),
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_id_mismatch"


def test_platform_policy_revision_endpoint_rejects_missing_permission() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())
    payload = revision_payload()
    payload["actor_scopes"] = []

    response = client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=payload,
    )

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == "platform:policy:revise"


def test_platform_policy_detail_endpoint_returns_policy_with_revisions() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())
    client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=revision_payload(),
    )

    response = client.get("/platform/policies/policy_platform_high_risk_gate_v1")

    client.close()
    assert response.status_code == 200
    body = response.json()
    assert body["policy_id"] == "policy_platform_high_risk_gate_v1"
    assert body["current_revision"]["revision_number"] == 2
    assert body["current_revision"]["status"] == "active"
    assert [revision["revision_number"] for revision in body["revisions"]] == [1, 2]
    assert body["revisions"][0]["status"] == "superseded"


def test_platform_policy_detail_endpoint_rejects_unknown_policy() -> None:
    client, _ = build_test_client()

    response = client.get("/platform/policies/policy_platform_missing")

    client.close()
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_platform_policy_registry_endpoint_is_tenant_scoped() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())
    client.post(
        "/platform/policies",
        json=policy_payload(
            policy_id="policy_platform_other_tenant_v1",
            tenant_id="tenant_other",
        ),
    )

    demo_registry = client.get("/platform/policies")
    other_registry = client.get("/platform/policies", params={"tenant_id": "tenant_other"})

    client.close()
    assert demo_registry.status_code == 200
    assert other_registry.status_code == 200
    demo_policy_ids = [policy["policy_id"] for policy in demo_registry.json()["policies"]]
    other_policy_ids = [policy["policy_id"] for policy in other_registry.json()["policies"]]
    assert demo_policy_ids == ["policy_platform_high_risk_gate_v1"]
    assert other_policy_ids == ["policy_platform_other_tenant_v1"]
    assert demo_registry.json()["policy_count"] == 1
    assert demo_registry.json()["active_policy_count"] == 1


def test_platform_policy_detail_endpoint_is_tenant_scoped() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    response = client.get(
        "/platform/policies/policy_platform_high_risk_gate_v1",
        params={"tenant_id": "tenant_other"},
    )

    client.close()
    assert response.status_code == 404


def test_platform_policy_evaluation_endpoint_is_deterministic() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    first = client.post("/platform/policies/evaluate", json=evaluation_payload())
    second = client.post("/platform/policies/evaluate", json=evaluation_payload())

    client.close()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["matched"] is True
    assert body["effect"] == "require_approval"
    assert body["matched_policy_id"] == "policy_platform_high_risk_gate_v1"
    assert body["matched_revision_number"] == 1
    assert body["precedence_rule"] == "effect_severity_then_policy_id"
    assert body["evidence"]["matched_constraints"]["risk_level"] == "low"


def test_platform_policy_evaluation_defaults_to_allow_without_matching_policy() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    response = client.post(
        "/platform/policies/evaluate",
        json=evaluation_payload(
            context={
                "action_id": "request_supplier_expedite",
                "action_domain": "Supply",
                "risk_level": "high",
                "autonomy_level": "L2",
            }
        ),
    )

    client.close()
    assert response.status_code == 200
    body = response.json()
    assert body["matched"] is False
    assert body["effect"] == "allow"
    assert body["matched_policy_id"] is None
    assert body["evaluated_policy_count"] == 1


def test_platform_policy_evaluation_applies_deterministic_precedence() -> None:
    client, _ = build_test_client()
    client.post(
        "/platform/policies",
        json=policy_payload(
            policy_id="policy_platform_evidence_gate_v1",
            effect="allow_with_evidence",
        ),
    )
    client.post(
        "/platform/policies",
        json=policy_payload(policy_id="policy_platform_deny_gate_z1", effect="deny"),
    )
    client.post(
        "/platform/policies",
        json=policy_payload(policy_id="policy_platform_deny_gate_a1", effect="deny"),
    )

    response = client.post("/platform/policies/evaluate", json=evaluation_payload())

    client.close()
    assert response.status_code == 200
    body = response.json()
    assert body["effect"] == "deny"
    assert body["matched_policy_id"] == "policy_platform_deny_gate_a1"
    assert body["evaluated_policy_count"] == 3
    assert [match["policy_id"] for match in body["matched_policies"]] == [
        "policy_platform_deny_gate_a1",
        "policy_platform_deny_gate_z1",
        "policy_platform_evidence_gate_v1",
    ]


def test_platform_policy_evaluation_matches_amount_threshold() -> None:
    client, _ = build_test_client()
    client.post(
        "/platform/policies",
        json=policy_payload(
            policy_id="policy_platform_amount_gate_v1",
            effect="require_approval",
            conditions={"requested_amount_at_least": 1000},
        ),
    )

    above = client.post(
        "/platform/policies/evaluate",
        json=evaluation_payload(context={"requested_amount": 1500}),
    )
    below = client.post(
        "/platform/policies/evaluate",
        json=evaluation_payload(context={"requested_amount": 500}),
    )
    missing = client.post(
        "/platform/policies/evaluate",
        json=evaluation_payload(context={"action_domain": "Operations"}),
    )

    client.close()
    assert above.status_code == 200
    assert above.json()["effect"] == "require_approval"
    assert above.json()["evidence"]["matched_constraints"]["requested_amount"] == 1500
    assert below.status_code == 200
    assert below.json()["effect"] == "allow"
    assert missing.status_code == 200
    assert missing.json()["effect"] == "allow"


def test_platform_policy_evaluation_endpoint_rejects_missing_permission() -> None:
    client, _ = build_test_client()
    payload = evaluation_payload()
    payload["actor_scopes"] = []

    response = client.post("/platform/policies/evaluate", json=payload)

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == "platform:policy:evaluate"


def test_platform_policy_evaluation_is_tenant_scoped() -> None:
    client, _ = build_test_client()
    client.post("/platform/policies", json=policy_payload())

    response = client.post(
        "/platform/policies/evaluate",
        json=evaluation_payload(tenant_id="tenant_other"),
    )

    client.close()
    assert response.status_code == 200
    assert response.json()["matched"] is False
    assert response.json()["effect"] == "allow"
    assert response.json()["evaluated_policy_count"] == 0


def test_platform_policy_evaluation_ignores_superseded_revisions() -> None:
    client, factory = build_test_client()
    client.post("/platform/policies", json=policy_payload())
    client.post(
        "/platform/policies/policy_platform_high_risk_gate_v1/revisions",
        json=revision_payload(),
    )

    response = client.post("/platform/policies/evaluate", json=evaluation_payload())

    client.close()
    assert response.status_code == 200
    body = response.json()
    assert body["effect"] == "deny"
    assert body["matched_revision_number"] == 2
    assert body["evaluated_policy_count"] == 1
    with factory() as session:
        repository = AxisPersistenceRepository(session)
        decision = evaluate_platform_policies(
            repository,
            tenant_id="tenant_demo_manufacturing",
            scope=PlatformPolicyScope.ACTION_EXECUTION,
            context=PlatformPolicyEvaluationContext(
                action_domain="Operations",
                risk_level="low",
            ),
        )

    assert decision.matched_revision_number == 2
    assert decision.effect == "deny"


def test_platform_policy_create_endpoint_binds_oidc_actor() -> None:
    client, factory = build_test_client(
        settings=Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True),
    )
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="platform-governance-owner-role",
            tenant_id="tenant_demo_manufacturing",
            scopes=["platform:policy:author"],
        )
    )
    payload = policy_payload()
    payload["actor_scopes"] = []

    response = client.post(
        "/platform/policies",
        headers={"Authorization": "Bearer valid-token"},
        json=payload,
    )

    client.close()
    assert response.status_code == 201
    assert response.json()["created_by"] == "platform-governance-owner-role"
    with factory() as session:
        audit_event = session.scalars(select(AuditEvent)).one()
    assert audit_event.actor_id == "platform-governance-owner-role"


def test_platform_policy_create_endpoint_rejects_oidc_actor_impersonation() -> None:
    client, _ = build_test_client(
        settings=Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True),
    )
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="platform-governance-owner-role",
            tenant_id="tenant_demo_manufacturing",
            scopes=["platform:policy:author"],
        )
    )
    payload = policy_payload()
    payload["created_by"] = "another-actor"

    response = client.post(
        "/platform/policies",
        headers={"Authorization": "Bearer valid-token"},
        json=payload,
    )

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "actor_mismatch"


def test_platform_policy_create_endpoint_rejects_oidc_tenant_mismatch() -> None:
    client, _ = build_test_client(
        settings=Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True),
    )
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="platform-governance-owner-role",
            tenant_id="tenant_other",
            scopes=["platform:policy:author"],
        )
    )

    response = client.post(
        "/platform/policies",
        headers={"Authorization": "Bearer valid-token"},
        json=policy_payload(),
    )

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "tenant_mismatch"


def test_platform_policy_registry_endpoint_requires_read_scope_when_authenticated() -> None:
    client, _ = build_test_client(
        settings=Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True),
    )
    client.app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(
            actor_id="platform-governance-owner-role",
            tenant_id="tenant_demo_manufacturing",
            scopes=[],
        )
    )

    unauthenticated = client.get("/platform/policies")
    denied = client.get(
        "/platform/policies",
        headers={"Authorization": "Bearer valid-token"},
    )

    client.close()
    assert unauthenticated.status_code == 401
    assert denied.status_code == 403
    assert denied.json()["detail"]["reason"] == "missing_required_scope"
    assert denied.json()["detail"]["required_permission"] == "platform:policy:read"


def test_action_run_endpoint_denies_run_when_platform_policy_denies() -> None:
    client, factory = build_test_client(seed_action_registry=True)
    client.post(
        "/platform/policies",
        json=policy_payload(policy_id="policy_platform_deny_low_risk_v1", effect="deny"),
    )

    response = client.post(
        "/demo/manufacturing/actions/generate_daily_plant_brief/runs",
        json=daily_brief_run_payload(),
    )

    client.close()
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "POLICY_VIOLATION"
    assert detail["reason"] == "platform_policy_denied"
    assert detail["policy_id"] == "policy_platform_deny_low_risk_v1"
    assert detail["policy_revision_number"] == 1
    assert detail["audit_event_type"] == "platform.policy.enforcement.denied"
    with factory() as session:
        assert list(session.scalars(select(ActionRun))) == []
        denial_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "platform.policy.enforcement.denied"
            )
        ).one()

    assert detail["audit_event_id"] == str(denial_event.id)
    assert denial_event.payload["action_id"] == "generate_daily_plant_brief"
    assert denial_event.payload["status"] == "policy_denied"
    assert denial_event.payload["policy_effect"] == "deny"
    assert denial_event.payload["platform_policy_decision"]["matched"] is True


def test_action_run_endpoint_forces_approval_when_platform_policy_requires_it() -> None:
    client, factory = build_test_client(seed_action_registry=True)
    client.post(
        "/platform/policies",
        json=policy_payload(
            policy_id="policy_platform_gate_low_risk_v1",
            effect="require_approval",
        ),
    )

    response = client.post(
        "/demo/manufacturing/actions/generate_daily_plant_brief/runs",
        json=daily_brief_run_payload(),
    )

    client.close()
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "approval_required"
    assert body["approval_required"] is True
    assert body["platform_policy_decision"]["matched"] is True
    assert body["platform_policy_decision"]["effect"] == "require_approval"
    assert body["platform_policy_decision"]["matched_policy_id"] == (
        "policy_platform_gate_low_risk_v1"
    )
    with factory() as session:
        action_run = session.scalars(select(ActionRun)).one()
        run_event = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "action.preview.generated")
        ).one()

    assert action_run.status == "approval_required"
    assert run_event.payload["approval_required"] is True
    assert run_event.payload["platform_policy_decision"]["effect"] == "require_approval"


def test_action_run_endpoint_records_allow_with_evidence_platform_policy_decision() -> None:
    client, factory = build_test_client(seed_action_registry=True)
    client.post(
        "/platform/policies",
        json=policy_payload(
            policy_id="policy_platform_evidence_low_risk_v1",
            effect="allow_with_evidence",
        ),
    )

    response = client.post(
        "/demo/manufacturing/actions/generate_daily_plant_brief/runs",
        json=daily_brief_run_payload(),
    )

    client.close()
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "preview_generated"
    assert body["approval_required"] is False
    assert body["platform_policy_decision"]["effect"] == "allow_with_evidence"
    with factory() as session:
        run_event = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "action.preview.generated")
        ).one()

    assert run_event.payload["platform_policy_decision"]["effect"] == "allow_with_evidence"
    assert run_event.payload["platform_policy_decision"]["matched_policy_id"] == (
        "policy_platform_evidence_low_risk_v1"
    )


def test_action_run_endpoint_defaults_to_allow_without_matching_platform_policy() -> None:
    client, factory = build_test_client(seed_action_registry=True)

    response = client.post(
        "/demo/manufacturing/actions/generate_daily_plant_brief/runs",
        json=daily_brief_run_payload(),
    )

    client.close()
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "preview_generated"
    assert body["platform_policy_decision"]["matched"] is False
    assert body["platform_policy_decision"]["effect"] == "allow"
    with factory() as session:
        run_event = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "action.preview.generated")
        ).one()

    assert run_event.payload["platform_policy_decision"] is None


def test_action_run_endpoint_ignores_platform_policies_from_other_tenants() -> None:
    client, factory = build_test_client(seed_action_registry=True)
    client.post(
        "/platform/policies",
        json=policy_payload(
            policy_id="policy_platform_other_tenant_deny_v1",
            effect="deny",
            tenant_id="tenant_other",
        ),
    )

    response = client.post(
        "/demo/manufacturing/actions/generate_daily_plant_brief/runs",
        json=daily_brief_run_payload(),
    )

    client.close()
    assert response.status_code == 201
    assert response.json()["status"] == "preview_generated"
    with factory() as session:
        assert session.scalars(select(ActionRun)).one() is not None
