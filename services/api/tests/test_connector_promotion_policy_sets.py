from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_promotion_policy_sets import (
    ConnectorPromotionPolicySetActivateRequest,
    build_connector_promotion_policy_set_registry,
    record_demo_connector_promotion_policy_set,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base, ConnectorPromotionPolicySet
from axis_api.persistence import AxisPersistenceRepository, ConnectorPromotionPolicyCreate


def policy_set_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "connector_id": "file_csv_manufacturing_assets",
        "policy_set_id": "policy_set_connector_asset_required_20260622",
        "policy_set_version": "2026-06-22.1",
        "status": "active",
        "activated_by": "platform-governance-owner-role",
        "actor_scopes": ["connectors:promotion_policy_set:activate"],
        "policy_ids": [
            "policy_connector_asset_required_scope",
            "policy_connector_asset_required_risk",
        ],
        "activation_reason": "Activate versioned required policy set for asset promotions.",
        "notes": ["Active set resolves multi-policy required gate selection."],
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


def seed_enabled_required_policy(
    repository: AxisPersistenceRepository,
    policy_id: str,
    *,
    allowed_risk_levels: list[str] | None = None,
) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="platform-governance-owner-role",
            event_type="connector.promotion_policy.enabled",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "policy_id": policy_id,
                "status": "enabled",
                "enforcement_mode": "required",
            },
        )
    )
    repository.create_connector_promotion_policy(
        ConnectorPromotionPolicyCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            policy_id=policy_id,
            policy_version="2026-06-22",
            status="enabled",
            enforcement_mode="required",
            created_by="platform-governance-owner-role",
            required_scopes=["connectors:ontology:promote"],
            required_manual_import_status="approval_approved",
            required_workflow_signal_status="manual_import_signal_requested",
            allowed_risk_levels=allowed_risk_levels or ["high", "medium"],
            allowed_ontology_types=["manufacturing_asset"],
            review_window_hours=24,
            permission_decision={"allowed": True, "reason": "allowed"},
            audit_event_id=audit_event.id,
            audit_event_type="connector.promotion_policy.enabled",
            notes=["Required policy enabled for connector ontology promotion."],
        )
    )


def seed_policy_set_dependencies(repository: AxisPersistenceRepository) -> None:
    seed_enabled_required_policy(repository, "policy_connector_asset_required_scope")
    seed_enabled_required_policy(repository, "policy_connector_asset_required_risk")


def test_record_connector_promotion_policy_set_writes_audit_and_registry() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_policy_set_dependencies(repository)
        policy_set = record_demo_connector_promotion_policy_set(
            repository,
            ConnectorPromotionPolicySetActivateRequest(**policy_set_payload()),
        )

    with factory() as session:
        persisted_set = session.scalars(select(ConnectorPromotionPolicySet)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy_set.activated"
            )
        ).one()
        registry = build_connector_promotion_policy_set_registry(
            AxisPersistenceRepository(session),
            tenant_id="tenant_demo_manufacturing",
        )

    client.close()
    assert policy_set.policy_set_id == "policy_set_connector_asset_required_20260622"
    assert policy_set.status == "active"
    assert policy_set.policy_ids == [
        "policy_connector_asset_required_scope",
        "policy_connector_asset_required_risk",
    ]
    assert persisted_set.audit_event_id == audit_event.id
    assert audit_event.payload["policy_set_version"] == "2026-06-22.1"
    assert audit_event.payload["policy_ids"] == [
        "policy_connector_asset_required_scope",
        "policy_connector_asset_required_risk",
    ]
    assert registry.metrics[0].label == "Policy Sets"
    assert registry.metrics[0].value == "1"
    assert registry.metrics[1].label == "Active Sets"
    assert registry.metrics[1].value == "1"


def test_connector_promotion_policy_set_endpoint_creates_active_set() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    )

    with factory() as session:
        policy_set_count = len(session.scalars(select(ConnectorPromotionPolicySet)).all())

    client.close()
    assert response.status_code == 201
    assert response.json()["policy_set_id"] == "policy_set_connector_asset_required_20260622"
    assert response.json()["policy_set_version"] == "2026-06-22.1"
    assert response.json()["audit_event_type"] == "connector.promotion_policy_set.activated"
    assert policy_set_count == 1


def test_connector_promotion_policy_set_endpoint_rejects_missing_permission() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))
    payload = policy_set_payload()
    payload["actor_scopes"] = []

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=payload,
    )

    client.close()
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == (
        "connectors:promotion_policy_set:activate"
    )


def test_connector_promotion_policy_set_endpoint_rejects_policy_not_enabled() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_enabled_required_policy(repository, "policy_connector_asset_required_scope")
        seed_enabled_required_policy(repository, "policy_connector_asset_required_risk")
        disabled_policy = repository.get_connector_promotion_policy(
            "tenant_demo_manufacturing",
            "policy_connector_asset_required_risk",
        )
        disabled_policy.status = "draft"

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    )

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_set_policy_not_enabled_required"


def test_openapi_exposes_connector_promotion_policy_set_endpoints() -> None:
    app = create_app(Settings(auth_required=False))
    paths = app.openapi()["paths"]

    assert "/demo/manufacturing/connectors/promotion-policy-sets" in paths
    assert "get" in paths["/demo/manufacturing/connectors/promotion-policy-sets"]
    assert "post" in paths["/demo/manufacturing/connectors/promotion-policy-sets"]
