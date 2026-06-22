from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connector_promotion_policies import (
    ConnectorPromotionPolicyCreateRequest,
    build_connector_promotion_policy_registry,
    record_demo_connector_promotion_policy,
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
