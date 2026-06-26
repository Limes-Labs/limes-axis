from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_egress_policies import (
    ConnectorEgressPolicyCreateRequest,
    ConnectorEgressPolicyQuery,
    build_connector_egress_policy_registry,
    record_demo_connector_egress_policy,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, ConnectorEgressPolicyCreate


def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return factory


def egress_policy_request() -> ConnectorEgressPolicyCreateRequest:
    return ConnectorEgressPolicyCreateRequest(
        tenant_id="tenant_demo_manufacturing",
        connector_id="external_db_operational_mirror",
        policy_id="egress_policy_private_endpoint_ops",
        display_name="Operations Postgres private endpoint policy",
        connection_profile_id="profile_postgres_ops_readonly",
        egress_boundary="approved_private_endpoint",
        policy_mode="approved_private_endpoint",
        private_endpoint_ref=(
            "private-endpoint://tenant_demo_manufacturing/"
            "persisted-operations-postgres-readonly"
        ),
        created_by="network-policy-owner-role",
        policy_document={
            "allowed_destination": "operations-postgres-readonly.internal",
            "transport": "private_endpoint",
            "live_query_mode": "read_only_snapshot",
        },
        notes=["Tenant-scoped egress policy for external DB preflight."],
    )


def test_build_connector_egress_policy_registry_maps_persisted_records() -> None:
    factory = session_factory()
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        created = record_demo_connector_egress_policy(repository, egress_policy_request())
        registry = build_connector_egress_policy_registry(
            repository,
            ConnectorEgressPolicyQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.metrics[0].label == "Egress Policies"
    assert registry.metrics[0].value == "1"
    assert registry.policies[0].policy_id == created.policy_id
    assert registry.policies[0].status == "active"
    assert registry.policies[0].runtime_boundary == "axis-egress-policy-enforcer"
    assert registry.policies[0].private_endpoint_ref == (
        "private-endpoint://tenant_demo_manufacturing/"
        "persisted-operations-postgres-readonly"
    )
    serialized = registry.model_dump_json().lower()
    assert "postgres://" not in serialized
    assert "password" not in serialized
    assert "credential_value" not in serialized


def test_connector_egress_policy_endpoint_persists_and_lists_records() -> None:
    factory = session_factory()
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    client = TestClient(app)

    create_response = client.post(
        "/demo/manufacturing/connectors/egress-policies",
        json=egress_policy_request().model_dump(mode="json"),
    )
    list_response = client.get(
        "/demo/manufacturing/connectors/egress-policies",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["policy_id"] == "egress_policy_private_endpoint_ops"
    assert created["status"] == "active"
    assert created["audit_event_type"] == "connector.egress_policy.registered"
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["metrics"][0]["value"] == "1"
    assert body["policies"][0]["private_endpoint_ref"] == (
        "private-endpoint://tenant_demo_manufacturing/"
        "persisted-operations-postgres-readonly"
    )
    assert "postgres://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_connector_egress_policy_endpoint_writes_read_audit_event() -> None:
    factory = session_factory()
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_egress_policy(repository, egress_policy_request())
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/egress-policies",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "external_db_operational_mirror",
            "actor_id": "connector-egress-policy-reader",
        },
    )

    assert response.status_code == 200
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        events = repository.list_audit_events(
            tenant_id="tenant_demo_manufacturing",
            event_type="connector.egress_policies_read",
            limit=10,
        )

    assert len(events) == 1
    event = events[0]
    assert event.actor_id == "connector-egress-policy-reader"
    assert event.payload == {
        "connector_id": "external_db_operational_mirror",
        "status": None,
        "limit": 100,
        "returned_policy_count": 1,
        "policy_evidence_invariant_count": 0,
        "policy_ids": ["egress_policy_private_endpoint_ops"],
    }
    assert "private-endpoint://" not in str(event.payload).lower()
    assert "postgres://" not in str(event.payload).lower()
    assert "password" not in str(event.payload).lower()
    assert "credential_value" not in str(event.payload).lower()


def test_connector_egress_policy_endpoint_reports_audit_payload_invariants() -> None:
    factory = session_factory()
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        policy_audit_event = repository.append_audit_event(
            AuditEventCreate(
                tenant_id="tenant_demo_manufacturing",
                actor_id="network-policy-owner-role",
                event_type="connector.egress_policy.registered",
                payload={
                    "connector_id": "external_db_operational_mirror",
                    "policy_id": "egress_policy_other",
                    "connection_profile_id": "profile_postgres_ops_readonly",
                    "egress_boundary": "approved_private_endpoint",
                    "policy_mode": "approved_private_endpoint",
                    "runtime_boundary": "axis-egress-policy-enforcer",
                    "private_endpoint_ref": (
                        "private-endpoint://tenant_demo_manufacturing/"
                        "persisted-operations-postgres-readonly"
                    ),
                    "external_query_started": False,
                    "credential_material_returned": False,
                },
            )
        )
        repository.create_connector_egress_policy(
            ConnectorEgressPolicyCreate(
                tenant_id="tenant_demo_manufacturing",
                connector_id="external_db_operational_mirror",
                policy_id="egress_policy_payload_mismatch_target",
                display_name="Operations Postgres private endpoint policy",
                status="active",
                connection_profile_id="profile_postgres_ops_readonly",
                egress_boundary="approved_private_endpoint",
                policy_mode="approved_private_endpoint",
                runtime_boundary="axis-egress-policy-enforcer",
                private_endpoint_ref=(
                    "private-endpoint://tenant_demo_manufacturing/"
                    "persisted-operations-postgres-readonly"
                ),
                created_by="network-policy-owner-role",
                policy_document={
                    "allowed_destination": "operations-postgres-readonly.internal",
                    "transport": "private_endpoint",
                },
                evidence_refs=[str(policy_audit_event.id)],
                audit_event_id=policy_audit_event.id,
                audit_event_type="connector.egress_policy.registered",
                notes=["Policy seeded with mismatched audit payload."],
            )
        )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/egress-policies",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["metrics"][2]["label"] == "Policy Evidence Invariants"
    assert body["metrics"][2]["value"] == "1"
    assert body["metrics"][2]["status"] == "watch"
    assert body["policy_evidence_invariants"] == [
        {
            "policy_id": "egress_policy_payload_mismatch_target",
            "audit_event_id": str(policy_audit_event.id),
            "reason": "egress_policy_audit_event_payload_mismatch",
            "detail": (
                "Egress policy audit event payload must match connector_id, "
                "policy_id and connection_profile_id."
            ),
        }
    ]
    assert "postgres://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_connector_egress_policy_endpoint_rejects_raw_dsn_material() -> None:
    factory = session_factory()
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    client = TestClient(app)
    payload = egress_policy_request().model_dump(mode="json")
    payload["private_endpoint_ref"] = "postgresql://readonly:secret@db.internal/orders"

    response = client.post(
        "/demo/manufacturing/connectors/egress-policies",
        json=payload,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["reason"] == "raw_network_or_secret_material"
