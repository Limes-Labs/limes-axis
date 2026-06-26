from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialLeaseCreate,
    ConnectorEgressPolicyCreate,
    ConnectorSyncCheckpointClaimCreate,
    ConnectorSyncCheckpointCreate,
)


def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def seed_mismatched_connector_evidence(repository: AxisPersistenceRepository) -> None:
    checkpoint_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-sync-worker-role",
            event_type="connector.run.sync_execution_completed",
            payload={
                "connector_id": "external_db_operational_mirror",
                "run_id": "run_evidence_report_20260627",
                "checkpoint_id": "chk_other",
                "external_query_started": False,
                "credential_material_returned": False,
                "graph_mutation_started": False,
            },
        )
    )
    repository.create_connector_sync_checkpoint(
        ConnectorSyncCheckpointCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            run_id="run_evidence_report_20260627",
            checkpoint_id="chk_evidence_report_1",
            checkpoint_type="sync_execution",
            status="sync_execution_completed",
            sequence=1,
            runtime_boundary="axis-workflow-runtime-adapter",
            adapter="axis-postgres-external-db-sync-executor",
            cursor={"high_watermark_kind": "timestamp"},
            result_summary={
                "external_query_started": "false",
                "credential_material_returned": "false",
                "graph_mutation_started": "false",
            },
            evidence_refs=[str(checkpoint_event.id)],
            audit_event_id=checkpoint_event.id,
            audit_event_type="connector.run.sync_execution_completed",
            notes=["Checkpoint seeded with mismatched audit payload."],
        )
    )

    claim_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-sync-worker-role",
            event_type="connector.run.sync_checkpoint_claimed",
            payload={
                "connector_id": "external_db_operational_mirror",
                "run_id": "run_evidence_report_20260627",
                "checkpoint_id": "chk_evidence_report_1",
                "claim_id": "claim_evidence_report_1",
                "claimed_by": "axis-sync-worker-other-role",
                "external_sync_started": False,
                "secret_material_returned": False,
                "worker_claim_only": True,
            },
        )
    )
    repository.create_connector_sync_checkpoint_claim(
        ConnectorSyncCheckpointClaimCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            run_id="run_evidence_report_20260627",
            checkpoint_id="chk_evidence_report_1",
            claim_id="claim_evidence_report_1",
            status="claimed",
            claimed_by="axis-sync-worker-role",
            idempotency_key="idem_claim_evidence_report_1",
            lease_duration_seconds=900,
            lease_expires_at=datetime(2026, 6, 27, 10, 15, tzinfo=UTC),
            claim_result={
                "external_sync_started": False,
                "secret_material_returned": False,
                "worker_claim_only": True,
            },
            audit_event_id=claim_event.id,
            audit_event_type="connector.run.sync_checkpoint_claimed",
            notes=["Claim seeded with mismatched audit payload."],
        )
    )

    lease_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-connector-runtime-role",
            event_type="connector.credential_lease.requested",
            payload={
                "connector_id": "external_db_operational_mirror",
                "handle_id": "cred_external_db_readonly",
                "lease_id": "lease_other",
                "secret_material_returned": "false",
                "external_secret_read": "false",
            },
        )
    )
    repository.create_connector_credential_lease(
        ConnectorCredentialLeaseCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            handle_id="cred_external_db_readonly",
            lease_id="lease_evidence_report_1",
            requested_by="axis-connector-runtime-role",
            lease_purpose="scheduled_sync_preflight",
            secret_provider="external_vault",
            secret_ref="vault://axis/demo/connectors/external-db-readonly",
            vault_kms_policy={"provider_mode": "self_hosted_vault"},
            permission_decision={"allowed": True, "reason": "all_required_scopes_present"},
            lease_result={
                "adapter": "axis-deferred-vault-kms-lease-adapter",
                "status": "lease_deferred",
                "external_secret_read": "false",
                "secret_material_returned": "false",
                "provider_mode": "deferred",
                "provider_lease_ref": "deferred-lease://tenant/lease_evidence_report_1",
            },
            granted_at=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
            expires_at=datetime(2026, 6, 27, 10, 15, tzinfo=UTC),
            renewal_due_at=datetime(2026, 6, 27, 10, 10, tzinfo=UTC),
            audit_event_id=lease_event.id,
            audit_event_type="connector.credential_lease.requested",
            notes=["Lease seeded with mismatched audit payload."],
        )
    )

    policy_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="network-policy-owner-role",
            event_type="connector.egress_policy.registered",
            payload={
                "connector_id": "external_db_operational_mirror",
                "policy_id": "egress_policy_other",
                "connection_profile_id": "profile_postgres_ops_readonly",
                "external_query_started": False,
                "credential_material_returned": False,
            },
        )
    )
    repository.create_connector_egress_policy(
        ConnectorEgressPolicyCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            policy_id="egress_policy_evidence_report_1",
            display_name="External DB private endpoint",
            status="active",
            connection_profile_id="profile_postgres_ops_readonly",
            egress_boundary="approved_private_endpoint",
            policy_mode="approved_private_endpoint",
            runtime_boundary="axis-egress-policy-enforcer",
            private_endpoint_ref="private-endpoint://tenant/external-db-readonly",
            created_by="network-policy-owner-role",
            policy_document={"transport": "private_endpoint"},
            evidence_refs=[str(policy_event.id)],
            audit_event_id=policy_event.id,
            audit_event_type="connector.egress_policy.registered",
            notes=["Policy seeded with mismatched audit payload."],
        )
    )


def test_connector_evidence_invariants_endpoint_aggregates_public_safe_records() -> None:
    factory = session_factory()
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = factory
    with session_scope(factory) as session:
        seed_mismatched_connector_evidence(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/evidence-invariants",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "external_db_operational_mirror",
            "actor_id": "connector-evidence-report-reader",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0] == {
        "label": "Evidence Invariants",
        "value": "4",
        "detail": (
            "Public-safe connector evidence issues across checkpoints, claims, "
            "leases and policies"
        ),
        "status": "watch",
    }
    assert [item["evidence_type"] for item in body["invariants"]] == [
        "checkpoint",
        "checkpoint_claim",
        "credential_lease",
        "egress_policy",
    ]
    assert [item["reason"] for item in body["invariants"]] == [
        "checkpoint_audit_event_payload_mismatch",
        "claim_audit_event_payload_mismatch",
        "lease_audit_event_payload_mismatch",
        "egress_policy_audit_event_payload_mismatch",
    ]
    assert body["invariant_counts"] == {
        "checkpoint": 1,
        "checkpoint_claim": 1,
        "credential_lease": 1,
        "egress_policy": 1,
    }
    serialized = str(body).lower()
    assert "private-endpoint://" not in serialized
    assert "vault://" not in serialized
    assert "postgres://" not in serialized
    assert "password" not in serialized
    assert "credential_value" not in serialized

    with session_scope(factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            tenant_id="tenant_demo_manufacturing",
            event_type="connector.evidence_invariants_read",
            limit=10,
        )

    assert len(events) == 1
    event = events[0]
    assert event.actor_id == "connector-evidence-report-reader"
    assert event.payload == {
        "connector_id": "external_db_operational_mirror",
        "limit": 100,
        "returned_invariant_count": 4,
        "invariant_counts": {
            "checkpoint": 1,
            "checkpoint_claim": 1,
            "credential_lease": 1,
            "egress_policy": 1,
        },
        "subject_ids": [
            "chk_evidence_report_1",
            "claim_evidence_report_1",
            "lease_evidence_report_1",
            "egress_policy_evidence_report_1",
        ],
    }
    assert "private-endpoint://" not in str(event.payload).lower()
    assert "vault://" not in str(event.payload).lower()
    assert "credential_value" not in str(event.payload).lower()


def test_openapi_exposes_connector_evidence_invariants_endpoint() -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))

    path = app.openapi()["paths"]["/demo/manufacturing/connectors/evidence-invariants"]

    assert "get" in path
    assert (
        path["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/ManufacturingConnectorEvidenceInvariantReport"
    )
