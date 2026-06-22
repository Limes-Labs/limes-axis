from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connector_promotion_policies import (
    ConnectorPromotionPolicyCreateRequest,
    ConnectorPromotionPolicyEnableRequest,
    ConnectorPromotionPolicyReviseRequest,
    build_connector_promotion_policy_registry,
    enable_demo_connector_promotion_policy,
    record_demo_connector_promotion_policy,
    revise_demo_connector_promotion_policy,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base, ConnectorPromotionPolicy
from axis_api.persistence import AxisPersistenceRepository


def policy_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "connector_id": "file_csv_manufacturing_assets",
        "policy_id": "policy_connector_asset_promotion_v1",
        "policy_version": "2026-06-22",
        "status": "draft",
        "enforcement_mode": "advisory",
        "created_by": "platform-governance-owner-role",
        "actor_scopes": ["connectors:promotion_policy:author"],
        "required_scopes": ["connectors:ontology:promote"],
        "required_manual_import_status": "approval_approved",
        "required_workflow_signal_status": "manual_import_signal_requested",
        "allowed_risk_levels": ["high", "medium"],
        "allowed_ontology_types": ["manufacturing_asset"],
        "review_window_hours": 24,
        "notes": ["Policy draft for connector proposal promotion review."],
    }


def enable_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "policy_id": "policy_connector_asset_promotion_v1",
        "enabled_by": "platform-governance-owner-role",
        "actor_scopes": ["connectors:promotion_policy:enable"],
        "approval_id": "appr_policy_enable_connector_asset_promotion_v1",
        "approval_decision": "approve",
        "workflow_signal_status": "policy_enable_signal_recorded",
        "note": "Enable required policy after governance review.",
    }


def revision_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "connector_id": "file_csv_manufacturing_assets",
        "policy_id": "policy_connector_asset_promotion_v2",
        "policy_version": "2026-06-22.2",
        "status": "draft",
        "enforcement_mode": "advisory",
        "updated_by": "platform-governance-owner-role",
        "actor_scopes": ["connectors:promotion_policy:revise"],
        "idempotency_key": "idem_policy_revision_asset_promotion_v2",
        "revises_policy_id": "policy_connector_asset_promotion_v1",
        "revision_approval_id": "appr_policy_revision_asset_promotion_v2",
        "revision_decision": "approve",
        "revision_workflow_signal_status": "policy_revision_signal_recorded",
        "required_scopes": ["connectors:ontology:promote"],
        "required_manual_import_status": "approval_approved",
        "required_workflow_signal_status": "manual_import_signal_requested",
        "allowed_risk_levels": ["high", "medium", "low"],
        "allowed_ontology_types": ["manufacturing_asset"],
        "review_window_hours": 48,
        "notes": ["Draft revision widens allowed risk levels after review."],
    }


def build_test_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    app = create_app(
        Settings(
            database_url="sqlite+pysqlite://",
            auth_required=False,
            cors_origins=["http://testserver"],
        )
    )
    app.state.session_factory = factory
    return TestClient(app), factory


def test_record_connector_promotion_policy_writes_audit_and_registry() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        policy = record_demo_connector_promotion_policy(
            repository,
            ConnectorPromotionPolicyCreateRequest(**policy_payload()),
        )

    with factory() as session:
        persisted_policy = session.scalars(select(ConnectorPromotionPolicy)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy.authored"
            )
        ).one()
        registry = build_connector_promotion_policy_registry(
            AxisPersistenceRepository(session),
            tenant_id="tenant_demo_manufacturing",
        )

    client.close()
    assert policy.policy_id == "policy_connector_asset_promotion_v1"
    assert policy.status == "draft"
    assert policy.permission_decision.model_dump() == {"allowed": True, "reason": "allowed"}
    assert policy.audit_event_type == "connector.promotion_policy.authored"
    assert persisted_policy.audit_event_id == audit_event.id
    assert audit_event.payload["required_authoring_scope"] == "connectors:promotion_policy:author"
    assert registry.metrics[0].label == "Promotion Policies"
    assert registry.metrics[0].value == "1"
    assert registry.policies[0].policy_id == "policy_connector_asset_promotion_v1"


def test_connector_promotion_policy_endpoint_creates_policy() -> None:
    client, factory = build_test_client()
    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )

    with factory() as session:
        policy_count = len(session.scalars(select(ConnectorPromotionPolicy)).all())

    client.close()
    assert response.status_code == 201
    assert response.json()["policy_id"] == "policy_connector_asset_promotion_v1"
    assert response.json()["audit_event_type"] == "connector.promotion_policy.authored"
    assert policy_count == 1


def test_enable_connector_promotion_policy_requires_approval_and_writes_audit() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_promotion_policy(
            repository,
            ConnectorPromotionPolicyCreateRequest(**policy_payload()),
        )
        enabled_policy = enable_demo_connector_promotion_policy(
            repository,
            ConnectorPromotionPolicyEnableRequest(**enable_payload()),
        )

    with factory() as session:
        persisted_policy = session.scalars(select(ConnectorPromotionPolicy)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy.enabled"
            )
        ).one()
        registry = build_connector_promotion_policy_registry(
            AxisPersistenceRepository(session),
            tenant_id="tenant_demo_manufacturing",
        )

    client.close()
    assert enabled_policy.status == "enabled"
    assert enabled_policy.enforcement_mode == "required"
    assert enabled_policy.audit_event_type == "connector.promotion_policy.enabled"
    assert persisted_policy.status == "enabled"
    assert persisted_policy.enforcement_mode == "required"
    assert persisted_policy.audit_event_id == audit_event.id
    assert audit_event.payload["approval_id"] == "appr_policy_enable_connector_asset_promotion_v1"
    assert audit_event.payload["approval_decision"] == "approve"
    assert audit_event.payload["workflow_signal_status"] == "policy_enable_signal_recorded"
    assert audit_event.payload["required_enable_scope"] == "connectors:promotion_policy:enable"
    assert registry.metrics[1].value == "0"
    assert registry.metrics[2].value == "1"


def test_connector_promotion_policy_enable_endpoint_updates_policy() -> None:
    client, factory = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/enable",
        json=enable_payload(),
    )

    with factory() as session:
        policy = session.scalars(select(ConnectorPromotionPolicy)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy.enabled"
            )
        ).one()

    client.close()
    assert response.status_code == 200
    assert response.json()["status"] == "enabled"
    assert response.json()["enforcement_mode"] == "required"
    assert response.json()["audit_event_type"] == "connector.promotion_policy.enabled"
    assert policy.status == "enabled"
    assert policy.audit_event_id == audit_event.id


def test_revise_connector_promotion_policy_creates_append_only_draft_version() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_promotion_policy(
            repository,
            ConnectorPromotionPolicyCreateRequest(**policy_payload()),
        )
        revised_policy = revise_demo_connector_promotion_policy(
            repository,
            ConnectorPromotionPolicyReviseRequest(**revision_payload()),
        )
        replayed_policy = revise_demo_connector_promotion_policy(
            repository,
            ConnectorPromotionPolicyReviseRequest(**revision_payload()),
        )

    with factory() as session:
        records = {
            record.policy_id: record
            for record in session.scalars(select(ConnectorPromotionPolicy)).all()
        }
        revision_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy.revised"
            )
        ).all()
        registry = build_connector_promotion_policy_registry(
            AxisPersistenceRepository(session),
            tenant_id="tenant_demo_manufacturing",
        )

    client.close()
    assert revised_policy.policy_id == "policy_connector_asset_promotion_v2"
    assert revised_policy.policy_version == "2026-06-22.2"
    assert revised_policy.status == "draft"
    assert revised_policy.enforcement_mode == "advisory"
    assert revised_policy.revises_policy_id == "policy_connector_asset_promotion_v1"
    assert revised_policy.revision_idempotency_key == "idem_policy_revision_asset_promotion_v2"
    assert revised_policy.idempotent_replay is False
    assert replayed_policy.policy_id == "policy_connector_asset_promotion_v2"
    assert replayed_policy.idempotent_replay is True
    assert len(records) == 2
    assert records["policy_connector_asset_promotion_v1"].status == "superseded"
    assert records["policy_connector_asset_promotion_v1"].replaced_by_policy_id == (
        "policy_connector_asset_promotion_v2"
    )
    assert records["policy_connector_asset_promotion_v2"].revises_policy_id == (
        "policy_connector_asset_promotion_v1"
    )
    assert len(revision_events) == 1
    assert revision_events[0].payload["previous_policy_id"] == (
        "policy_connector_asset_promotion_v1"
    )
    assert revision_events[0].payload["policy_id"] == "policy_connector_asset_promotion_v2"
    assert revision_events[0].payload["idempotency_key"] == (
        "idem_policy_revision_asset_promotion_v2"
    )
    assert registry.metrics[0].value == "2"


def test_connector_promotion_policy_revise_endpoint_is_idempotent() -> None:
    client, factory = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )

    first_response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/revise",
        json=revision_payload(),
    )
    replay_response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/revise",
        json=revision_payload(),
    )

    with factory() as session:
        policy_count = len(session.scalars(select(ConnectorPromotionPolicy)).all())
        revision_event_count = len(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.event_type == "connector.promotion_policy.revised"
                )
            ).all()
        )

    client.close()
    assert first_response.status_code == 201
    assert first_response.json()["policy_id"] == "policy_connector_asset_promotion_v2"
    assert first_response.json()["idempotent_replay"] is False
    assert replay_response.status_code == 200
    assert replay_response.json()["policy_id"] == "policy_connector_asset_promotion_v2"
    assert replay_response.json()["idempotent_replay"] is True
    assert policy_count == 2
    assert revision_event_count == 1


def test_connector_promotion_policy_revise_endpoint_rejects_enabled_target() -> None:
    client, _ = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )
    client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/enable",
        json=enable_payload(),
    )

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/revise",
        json=revision_payload(),
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_revision_target_not_draft"


def test_connector_promotion_policy_enable_endpoint_rejects_missing_permission() -> None:
    client, _ = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )
    payload = enable_payload()
    payload["actor_scopes"] = []

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/enable",
        json=payload,
    )

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == (
        "connectors:promotion_policy:enable"
    )


def test_connector_promotion_policy_enable_endpoint_rejects_non_approved_decision() -> None:
    client, _ = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )
    payload = enable_payload()
    payload["approval_decision"] = "reject"

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/enable",
        json=payload,
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_enable_not_approved"


def test_connector_promotion_policy_enable_endpoint_rejects_path_body_mismatch() -> None:
    client, _ = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )
    payload = enable_payload()
    payload["policy_id"] = "policy_other"

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies/policy_connector_asset_promotion_v1/enable",
        json=payload,
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_id_mismatch"


def test_connector_promotion_policy_endpoint_rejects_missing_permission() -> None:
    client, _ = build_test_client()
    payload = policy_payload()
    payload["actor_scopes"] = []

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=payload,
    )

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == (
        "connectors:promotion_policy:author"
    )


def test_connector_promotion_policy_endpoint_rejects_duplicate_policy() -> None:
    client, _ = build_test_client()

    first = client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )
    second = client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )

    client.close()
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["reason"] == "policy_already_exists"


def test_connector_promotion_policy_endpoint_rejects_direct_enabled_authoring() -> None:
    client, _ = build_test_client()
    payload = policy_payload()
    payload["status"] = "enabled"

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=payload,
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_enable_requires_workflow"


def test_connector_promotion_policy_endpoint_rejects_unsupported_connector() -> None:
    client, _ = build_test_client()
    payload = policy_payload()
    payload["connector_id"] = "missing_connector"

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=payload,
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "unsupported_connector_id"


def test_connector_promotion_policy_registry_endpoint_lists_policies() -> None:
    client, _ = build_test_client()
    client.post(
        "/demo/manufacturing/connectors/promotion-policies",
        json=policy_payload(),
    )

    response = client.get("/demo/manufacturing/connectors/promotion-policies")

    client.close()
    assert response.status_code == 200
    assert response.json()["metrics"][0]["label"] == "Promotion Policies"
    assert response.json()["metrics"][0]["value"] == "1"
    assert response.json()["policies"][0]["required_scopes"] == [
        "connectors:ontology:promote"
    ]


def test_openapi_exposes_connector_promotion_policy_endpoints() -> None:
    app = create_app(Settings(auth_required=False))
    paths = app.openapi()["paths"]

    assert "/demo/manufacturing/connectors/promotion-policies" in paths
    assert "get" in paths["/demo/manufacturing/connectors/promotion-policies"]
    assert "post" in paths["/demo/manufacturing/connectors/promotion-policies"]
    assert (
        "/demo/manufacturing/connectors/promotion-policies/{policy_id}/enable" in paths
    )
    assert (
        "post"
        in paths["/demo/manufacturing/connectors/promotion-policies/{policy_id}/enable"]
    )
    assert (
        "/demo/manufacturing/connectors/promotion-policies/{policy_id}/revise" in paths
    )
    assert (
        "post"
        in paths["/demo/manufacturing/connectors/promotion-policies/{policy_id}/revise"]
    )
