from copy import deepcopy
from pathlib import Path
from runpy import run_path

import pytest
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
from axis_api.connector_reference import ConnectorReferenceRecordNotFound
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base, ConnectorPromotionPolicy, ConnectorPromotionPolicySet
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorPromotionPolicyCreate,
    DemoReferenceRecordCreate,
)


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


def build_test_client(
    *,
    seed_connector_registry: bool = True,
) -> tuple[TestClient, sessionmaker[Session]]:
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
    if seed_connector_registry:
        seed_connector_registry_reference(factory)
    return TestClient(app), factory


def connector_registry_payload() -> dict:
    migration = run_path("migrations/versions/0023_connector_registry_reference.py")
    return deepcopy(migration["CONNECTOR_REGISTRY_PAYLOAD"])


def seed_connector_registry_reference(
    factory: sessionmaker[Session],
    payload: dict | None = None,
) -> None:
    registry_payload = deepcopy(payload or connector_registry_payload())
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="connectors",
                reference_id="manufacturing-connector-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=registry_payload,
            )
        )


def policy_set_request(connector_id: str = "file_csv_manufacturing_assets"):
    payload = policy_set_payload()
    payload["connector_id"] = connector_id
    return ConnectorPromotionPolicySetActivateRequest(**payload)


def seed_enabled_required_policy(
    repository: AxisPersistenceRepository,
    policy_id: str,
    *,
    allowed_risk_levels: list[str] | None = None,
    connector_id: str = "file_csv_manufacturing_assets",
) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="platform-governance-owner-role",
            event_type="connector.promotion_policy.enabled",
            payload={
                "connector_id": connector_id,
                "policy_id": policy_id,
                "status": "enabled",
                "enforcement_mode": "required",
            },
        )
    )
    repository.create_connector_promotion_policy(
        ConnectorPromotionPolicyCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id=connector_id,
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


def seed_policy_set_dependencies(
    repository: AxisPersistenceRepository,
    *,
    connector_id: str = "file_csv_manufacturing_assets",
) -> None:
    seed_enabled_required_policy(
        repository,
        "policy_connector_asset_required_scope",
        connector_id=connector_id,
    )
    seed_enabled_required_policy(
        repository,
        "policy_connector_asset_required_risk",
        connector_id=connector_id,
    )


def seed_revised_draft_policy(repository: AxisPersistenceRepository) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="platform-governance-owner-role",
            event_type="connector.promotion_policy.revised",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "policy_id": "policy_connector_asset_required_scope_v2",
                "revises_policy_id": "policy_connector_asset_required_scope",
                "status": "draft",
                "enforcement_mode": "advisory",
            },
        )
    )
    repository.create_connector_promotion_policy(
        ConnectorPromotionPolicyCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            policy_id="policy_connector_asset_required_scope_v2",
            policy_version="2026-06-22.2",
            status="draft",
            enforcement_mode="advisory",
            created_by="platform-governance-owner-role",
            required_authoring_scope="connectors:promotion_policy:revise",
            required_scopes=["connectors:ontology:promote"],
            required_manual_import_status="approval_approved",
            required_workflow_signal_status="manual_import_signal_requested",
            allowed_risk_levels=["medium"],
            allowed_ontology_types=["manufacturing_asset"],
            review_window_hours=24,
            permission_decision={"allowed": True, "reason": "allowed"},
            audit_event_id=audit_event.id,
            audit_event_type="connector.promotion_policy.revised",
            revises_policy_id="policy_connector_asset_required_scope",
            revision_idempotency_key="idem_policy_revision_required_scope_v2",
            revision_approval_id="approval_policy_revision_required_scope_v2",
            revision_decision="approve",
            revision_workflow_signal_status="policy_revision_signal_recorded",
            notes=["Approved revision candidate awaiting policy-set adoption."],
        )
    )


def replacement_with_policy_revision_adoption_payload() -> dict:
    payload = replacement_policy_set_payload()
    payload["policy_ids"] = [
        "policy_connector_asset_required_scope_v2",
        "policy_connector_asset_required_risk",
    ]
    payload["policy_revision_adoptions"] = [
        {
            "current_policy_id": "policy_connector_asset_required_scope",
            "revised_policy_id": "policy_connector_asset_required_scope_v2",
            "revision_idempotency_key": "idem_policy_revision_required_scope_v2",
            "adoption_approval_id": "approval_policy_revision_adoption_required_scope_v2",
            "adoption_decision": "approve",
            "adoption_workflow_signal_status": "policy_revision_adoption_signal_recorded",
        }
    ]
    return payload


def test_connector_promotion_policy_set_path_does_not_load_demo_connector_registry_seed() -> None:
    source = Path("src/axis_api/connector_promotion_policy_sets.py").read_text()

    assert "get_manufacturing_connector_registry" not in source


def test_record_connector_promotion_policy_set_requires_persisted_connector_registry() -> None:
    client, factory = build_test_client(seed_connector_registry=False)
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_policy_set_dependencies(repository)
        with pytest.raises(ConnectorReferenceRecordNotFound):
            record_demo_connector_promotion_policy_set(repository, policy_set_request())

    client.close()


def test_record_connector_promotion_policy_set_uses_persisted_connector_manifest() -> None:
    client, factory = build_test_client()
    payload = connector_registry_payload()
    persisted_only_connector = deepcopy(payload["connectors"][0])
    persisted_only_connector["manifest"]["connector_id"] = "persisted_policy_set_connector"
    persisted_only_connector["manifest"]["display_name"] = "Persisted policy set connector"
    payload["connectors"].append(persisted_only_connector)
    seed_connector_registry_reference(factory, payload)

    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_policy_set_dependencies(
            repository,
            connector_id="persisted_policy_set_connector",
        )
        policy_set = record_demo_connector_promotion_policy_set(
            repository,
            policy_set_request("persisted_policy_set_connector"),
        )
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.promotion_policy_set.activated",
        )

    client.close()
    assert policy_set.connector_id == "persisted_policy_set_connector"
    assert events[0].payload["connector_id"] == "persisted_policy_set_connector"


def test_connector_promotion_policy_set_endpoint_reports_missing_connector_registry() -> None:
    client, factory = build_test_client(seed_connector_registry=False)
    with session_scope(factory) as session:
        seed_policy_set_dependencies(AxisPersistenceRepository(session))

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    )

    client.close()
    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "NOT_FOUND",
        "message": "Manufacturing connector registry reference record not found.",
        "surface": "connectors",
    }


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


def test_connector_promotion_policy_set_endpoint_adopts_revised_policy_atomically() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_policy_set_dependencies(repository)
        seed_revised_draft_policy(repository)

    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    ).status_code == 201
    replacement_response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=replacement_with_policy_revision_adoption_payload(),
    )

    with factory() as session:
        policies = {
            record.policy_id: record
            for record in session.scalars(select(ConnectorPromotionPolicy)).all()
        }
        policy_sets = {
            record.policy_set_id: record
            for record in session.scalars(select(ConnectorPromotionPolicySet)).all()
        }
        active_sets = [record for record in policy_sets.values() if record.status == "active"]
        adoption_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy.revision_adopted"
            )
        ).one()
        replacement_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy_set.replaced"
            )
        ).one()

    client.close()
    assert replacement_response.status_code == 201
    body = replacement_response.json()
    assert body["policy_set_id"] == "policy_set_connector_asset_required_20260622_v2"
    assert body["policy_ids"] == [
        "policy_connector_asset_required_scope_v2",
        "policy_connector_asset_required_risk",
    ]
    assert body["policy_revision_adoptions"] == [
        {
            "current_policy_id": "policy_connector_asset_required_scope",
            "revised_policy_id": "policy_connector_asset_required_scope_v2",
            "revision_idempotency_key": "idem_policy_revision_required_scope_v2",
            "adoption_approval_id": "approval_policy_revision_adoption_required_scope_v2",
            "adoption_decision": "approve",
            "adoption_workflow_signal_status": "policy_revision_adoption_signal_recorded",
            "audit_event_id": str(adoption_event.id),
            "audit_event_type": "connector.promotion_policy.revision_adopted",
        }
    ]
    assert len(active_sets) == 1
    assert active_sets[0].policy_set_id == "policy_set_connector_asset_required_20260622_v2"
    assert policy_sets["policy_set_connector_asset_required_20260622"].status == "superseded"
    assert policies["policy_connector_asset_required_scope"].status == "superseded"
    assert policies["policy_connector_asset_required_scope"].replaced_by_policy_id == (
        "policy_connector_asset_required_scope_v2"
    )
    assert policies["policy_connector_asset_required_scope_v2"].status == "enabled"
    assert policies["policy_connector_asset_required_scope_v2"].enforcement_mode == "required"
    assert policies["policy_connector_asset_required_scope_v2"].audit_event_id == adoption_event.id
    assert policies["policy_connector_asset_required_scope_v2"].audit_event_type == (
        "connector.promotion_policy.revision_adopted"
    )
    assert replacement_event.payload["policy_revision_adoptions"] == body[
        "policy_revision_adoptions"
    ]


def test_connector_promotion_policy_set_endpoint_rejects_revision_adoption_without_signal() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_policy_set_dependencies(repository)
        seed_revised_draft_policy(repository)

    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    ).status_code == 201
    payload = replacement_with_policy_revision_adoption_payload()
    payload["policy_revision_adoptions"][0]["adoption_workflow_signal_status"] = None

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=payload,
    )

    with factory() as session:
        policies = {
            record.policy_id: record
            for record in session.scalars(select(ConnectorPromotionPolicy)).all()
        }
        policy_sets = session.scalars(select(ConnectorPromotionPolicySet)).all()

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_revision_adoption_signal_required"
    assert [record.status for record in policy_sets].count("active") == 1
    assert policies["policy_connector_asset_required_scope"].status == "enabled"
    assert policies["policy_connector_asset_required_scope_v2"].status == "draft"


def test_connector_promotion_policy_set_endpoint_rolls_back_adoption_when_set_invalid() -> None:
    client, factory = build_test_client()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_policy_set_dependencies(repository)
        seed_revised_draft_policy(repository)

    assert client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=policy_set_payload(),
    ).status_code == 201
    with session_scope(factory) as session:
        risk_policy = AxisPersistenceRepository(session).get_connector_promotion_policy(
            "tenant_demo_manufacturing",
            "policy_connector_asset_required_risk",
        )
        risk_policy.status = "draft"

    response = client.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        json=replacement_with_policy_revision_adoption_payload(),
    )

    with factory() as session:
        policies = {
            record.policy_id: record
            for record in session.scalars(select(ConnectorPromotionPolicy)).all()
        }
        policy_sets = session.scalars(select(ConnectorPromotionPolicySet)).all()
        adoption_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.promotion_policy.revision_adopted"
            )
        ).all()

    client.close()
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "policy_set_policy_not_enabled_required"
    assert [record.status for record in policy_sets].count("active") == 1
    assert policies["policy_connector_asset_required_scope"].status == "enabled"
    assert policies["policy_connector_asset_required_scope"].replaced_by_policy_id is None
    assert policies["policy_connector_asset_required_scope_v2"].status == "draft"
    assert policies["policy_connector_asset_required_scope_v2"].enforcement_mode == "advisory"
    assert policies["policy_connector_asset_required_risk"].status == "draft"
    assert adoption_events == []


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
