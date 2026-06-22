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


def replacement_policy_set_payload() -> dict:
    payload = policy_set_payload()
    payload.update(
        {
            "policy_set_id": "policy_set_connector_asset_required_20260622_v2",
            "policy_set_version": "2026-06-22.2",
            "activation_reason": "Replace active set after governance review.",
            "replaces_policy_set_id": "policy_set_connector_asset_required_20260622",
            "replacement_approval_id": "approval_policy_set_replace_20260622",
            "replacement_decision": "approve",
            "replacement_workflow_signal_status": "policy_set_replacement_signal_recorded",
        }
    )
    return payload


def rollback_policy_set_payload() -> dict:
    payload = policy_set_payload()
    payload.update(
        {
            "policy_set_id": "policy_set_connector_asset_required_20260622_rollback",
            "policy_set_version": "2026-06-22.3",
            "activation_reason": "Rollback active set after governance review.",
            "replaces_policy_set_id": "policy_set_connector_asset_required_20260622_v2",
            "rollback_to_policy_set_id": "policy_set_connector_asset_required_20260622",
            "rollback_approval_id": "approval_policy_set_rollback_20260622",
            "rollback_decision": "approve",
            "rollback_workflow_signal_status": "policy_set_rollback_signal_recorded",
        }
    )
    return payload


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


def test_connector_promotion_policy_set_endpoint_replaces_active_set_with_evidence() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))

    first_response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    )
    replacement_response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=replacement_policy_set_payload(),
    )

    with factory() as session:
        records = {
            record.policy_set_id: record
            for record in session.scalars(select(ConnectorPromotionPolicySet)).all()
        }
        active_records = [
            record for record in records.values() if record.status == "active"
        ]
        replacement_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy_set.replaced"
            )
        ).one()

    client.close()
    assert first_response.status_code == 201
    assert replacement_response.status_code == 201
    body = replacement_response.json()
    assert body["policy_set_id"] == "policy_set_connector_asset_required_20260622_v2"
    assert body["status"] == "active"
    assert body["audit_event_type"] == "connector.promotion_policy_set.replaced"
    assert body["replaces_policy_set_id"] == "policy_set_connector_asset_required_20260622"
    assert body["replacement_approval_id"] == "approval_policy_set_replace_20260622"
    assert body["replacement_decision"] == "approve"
    assert body["replacement_workflow_signal_status"] == (
        "policy_set_replacement_signal_recorded"
    )
    assert len(records) == 2
    assert len(active_records) == 1
    assert active_records[0].policy_set_id == "policy_set_connector_asset_required_20260622_v2"
    assert records["policy_set_connector_asset_required_20260622"].status == "superseded"
    assert records["policy_set_connector_asset_required_20260622"].replaced_by_policy_set_id == (
        "policy_set_connector_asset_required_20260622_v2"
    )
    assert records["policy_set_connector_asset_required_20260622_v2"].replaces_policy_set_id == (
        "policy_set_connector_asset_required_20260622"
    )
    assert records["policy_set_connector_asset_required_20260622_v2"].audit_event_id == (
        replacement_event.id
    )
    assert replacement_event.payload["previous_policy_set_id"] == (
        "policy_set_connector_asset_required_20260622"
    )
    assert replacement_event.payload["policy_set_id"] == (
        "policy_set_connector_asset_required_20260622_v2"
    )
    assert replacement_event.payload["replacement_approval_id"] == (
        "approval_policy_set_replace_20260622"
    )
    assert replacement_event.payload["replacement_decision"] == "approve"
    assert replacement_event.payload["replacement_workflow_signal_status"] == (
        "policy_set_replacement_signal_recorded"
    )


def test_connector_promotion_policy_set_endpoint_rejects_replacement_without_approval() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))

    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    ).status_code == 201
    payload = replacement_policy_set_payload()
    payload["replacement_approval_id"] = None

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=payload,
    )

    with factory() as session:
        records = session.scalars(select(ConnectorPromotionPolicySet)).all()

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_set_replacement_approval_required"
    assert len(records) == 1
    assert records[0].status == "active"


def test_connector_promotion_policy_set_endpoint_rolls_back_active_set_with_evidence() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))

    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    ).status_code == 201
    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=replacement_policy_set_payload(),
    ).status_code == 201

    rollback_response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=rollback_policy_set_payload(),
    )

    with factory() as session:
        records = {
            record.policy_set_id: record
            for record in session.scalars(select(ConnectorPromotionPolicySet)).all()
        }
        active_records = [
            record for record in records.values() if record.status == "active"
        ]
        rollback_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy_set.rolled_back"
            )
        ).one()

    client.close()
    assert rollback_response.status_code == 201
    body = rollback_response.json()
    assert body["policy_set_id"] == "policy_set_connector_asset_required_20260622_rollback"
    assert body["status"] == "active"
    assert body["audit_event_type"] == "connector.promotion_policy_set.rolled_back"
    assert body["replaces_policy_set_id"] == "policy_set_connector_asset_required_20260622_v2"
    assert body["rollback_to_policy_set_id"] == "policy_set_connector_asset_required_20260622"
    assert body["rollback_approval_id"] == "approval_policy_set_rollback_20260622"
    assert body["rollback_decision"] == "approve"
    assert body["rollback_workflow_signal_status"] == "policy_set_rollback_signal_recorded"
    assert len(records) == 3
    assert len(active_records) == 1
    assert active_records[0].policy_set_id == (
        "policy_set_connector_asset_required_20260622_rollback"
    )
    assert records["policy_set_connector_asset_required_20260622_v2"].status == "superseded"
    assert records["policy_set_connector_asset_required_20260622_v2"].replaced_by_policy_set_id == (
        "policy_set_connector_asset_required_20260622_rollback"
    )
    assert records[
        "policy_set_connector_asset_required_20260622_rollback"
    ].rollback_to_policy_set_id == "policy_set_connector_asset_required_20260622"
    assert records[
        "policy_set_connector_asset_required_20260622_rollback"
    ].audit_event_id == rollback_event.id
    assert rollback_event.payload["previous_policy_set_id"] == (
        "policy_set_connector_asset_required_20260622_v2"
    )
    assert rollback_event.payload["rollback_to_policy_set_id"] == (
        "policy_set_connector_asset_required_20260622"
    )
    assert rollback_event.payload["rollback_approval_id"] == (
        "approval_policy_set_rollback_20260622"
    )
    assert rollback_event.payload["rollback_workflow_signal_status"] == (
        "policy_set_rollback_signal_recorded"
    )


def test_connector_promotion_policy_set_endpoint_rejects_rollback_without_workflow_signal() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))

    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    ).status_code == 201
    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=replacement_policy_set_payload(),
    ).status_code == 201
    payload = rollback_policy_set_payload()
    payload["rollback_workflow_signal_status"] = None

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=payload,
    )

    with factory() as session:
        records = session.scalars(select(ConnectorPromotionPolicySet)).all()

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_set_rollback_signal_required"
    assert len(records) == 2
    assert [record.status for record in records].count("active") == 1


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
