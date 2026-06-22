from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from axis_api.audit import AuditEventCreate
from axis_api.models import (
    ActionRun,
    ApprovalRecord,
    AuditEvent,
    Base,
    ConnectorConfiguration,
    ConnectorCredentialHandle,
    ConnectorCredentialRotation,
    ConnectorOntologyProposal,
    ConnectorRun,
)
from axis_api.persistence import (
    ActionRunCreate,
    ActionRunResultRecord,
    ApprovalDecisionRecord,
    ApprovalRecordCreate,
    AxisPersistenceRepository,
    ConnectorConfigurationCreate,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialRotationCreate,
    ConnectorOntologyProposalCreate,
    ConnectorRunCreate,
    PersistenceRecordNotFound,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_persistence_metadata_exposes_foundation_tables() -> None:
    assert {
        "audit_events",
        "approval_records",
        "action_runs",
        "connector_configurations",
        "connector_credential_handles",
        "connector_credential_rotations",
        "connector_runs",
        "connector_ontology_proposals",
    }.issubset(Base.metadata.tables.keys())
    assert ApprovalRecord.__table__.c.tenant_id.index is True
    assert ActionRun.__table__.c.idempotency_key.index is True
    assert AuditEvent.__table__.c.event_type.index is True
    assert ConnectorConfiguration.__table__.c.connector_id.index is True
    assert ConnectorCredentialHandle.__table__.c.handle_id.index is True
    assert ConnectorCredentialRotation.__table__.c.handle_id.index is True
    assert ConnectorRun.__table__.c.run_id.index is True
    assert ConnectorOntologyProposal.__table__.c.proposal_id.index is True


def test_repository_appends_audit_events_without_cross_tenant_leakage(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    first = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-test",
            event_type="approval.created",
            payload={"approval_id": "appr_1"},
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_other",
            actor_id="axis-test",
            event_type="approval.created",
            payload={"approval_id": "appr_other"},
        )
    )

    events = repository.list_audit_events("tenant_demo_manufacturing")

    assert len(events) == 1
    assert events[0].id == first.id
    assert events[0].payload == {"approval_id": "appr_1"}


def test_repository_records_approval_decisions(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    approval = repository.create_approval_record(
        ApprovalRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            approval_id="appr_expedite_supplier_batch",
            workflow_id="wf_supplier_delay_review",
            action_id="request_supplier_expedite",
            requested_by="agent_supply_risk",
            owner_role="plant-operations-owner",
            risk_level="high",
            payload={"required_permission": "approvals:supply:decide"},
        )
    )

    decided = repository.record_approval_decision(
        ApprovalDecisionRecord(
            tenant_id="tenant_demo_manufacturing",
            approval_id="appr_expedite_supplier_batch",
            decision="approved",
            decision_actor_id="plant-operations-owner-role",
            decision_note="Approved inside synthetic test scope.",
        )
    )

    assert decided.id == approval.id
    assert decided.status == "approved"
    assert decided.decision == "approved"
    assert decided.decision_actor_id == "plant-operations-owner-role"
    assert decided.decided_at is not None
    assert repository.list_approval_records("tenant_demo_manufacturing", status="approved") == [
        decided
    ]


def test_repository_raises_for_missing_approval_decision(session: Session) -> None:
    repository = AxisPersistenceRepository(session)

    with pytest.raises(PersistenceRecordNotFound, match="Approval record not found"):
        repository.record_approval_decision(
            ApprovalDecisionRecord(
                tenant_id="tenant_demo_manufacturing",
                approval_id="missing",
                decision="approved",
                decision_actor_id="plant-operations-owner-role",
            )
        )


def test_repository_records_action_runs_and_results(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    action_run = repository.create_action_run(
        ActionRunCreate(
            tenant_id="tenant_demo_manufacturing",
            action_id="request_supplier_expedite",
            idempotency_key="tenant_demo_manufacturing:request_supplier_expedite:appr_1",
            execution_mode="approval_gated_dry_run",
            requested_by="agent_supply_risk",
            approval_id="appr_expedite_supplier_batch",
            workflow_id="wf_supplier_delay_review",
            payload={"supplier_batch_id": "batch_motors_773"},
        )
    )

    found = repository.get_action_run_by_idempotency_key(
        "tenant_demo_manufacturing",
        "request_supplier_expedite",
        "tenant_demo_manufacturing:request_supplier_expedite:appr_1",
    )
    completed = repository.record_action_run_result(
        ActionRunResultRecord(
            tenant_id="tenant_demo_manufacturing",
            action_run_id=action_run.id,
            status="completed",
            result_payload={"dry_run": "recorded"},
        )
    )

    assert found == action_run
    assert completed.status == "completed"
    assert completed.result_payload == {"dry_run": "recorded"}
    assert repository.list_action_runs("tenant_demo_manufacturing", status="completed") == [
        completed
    ]


def test_action_run_idempotency_is_unique_per_tenant_action(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    payload = ActionRunCreate(
        tenant_id="tenant_demo_manufacturing",
        action_id="request_supplier_expedite",
        idempotency_key="duplicate-key",
        execution_mode="approval_gated_dry_run",
        requested_by="agent_supply_risk",
    )

    repository.create_action_run(payload)

    with pytest.raises(IntegrityError):
        repository.create_action_run(payload)


def test_repository_records_connector_configurations_tenant_scoped(
    session: Session,
) -> None:
    repository = AxisPersistenceRepository(session)
    created = repository.create_connector_configuration(
        ConnectorConfigurationCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            display_name="Manufacturing assets CSV intake",
            status="configured_preview_only",
            sync_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            created_by="plant-operations-owner-role",
            configuration_payload={
                "file_name_pattern": "*.csv",
                "mapping_profile": "manufacturing_asset_v1",
            },
            credential_ref_ids=[],
            notes=["Preview-only tenant configuration."],
        )
    )
    repository.create_connector_configuration(
        ConnectorConfigurationCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            display_name="Other tenant CSV intake",
            status="configured_preview_only",
            sync_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            created_by="other-owner-role",
            configuration_payload={"file_name_pattern": "*.csv"},
            credential_ref_ids=[],
            notes=[],
        )
    )

    records = repository.list_connector_configurations("tenant_demo_manufacturing")

    assert records == [created]
    assert records[0].configuration_payload == {
        "file_name_pattern": "*.csv",
        "mapping_profile": "manufacturing_asset_v1",
    }
    assert records[0].credential_ref_ids == []
    assert records[0].status == "configured_preview_only"


def test_repository_records_connector_credential_handles_and_rotations(
    session: Session,
) -> None:
    repository = AxisPersistenceRepository(session)
    created = repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            handle_id="cred_file_csv_readonly",
            display_name="File CSV readonly vault reference",
            status="active",
            secret_provider="external_vault",
            secret_ref="vault://axis/demo/connectors/file-csv-readonly",
            purpose="preview_import_readonly",
            rotation_interval_days=30,
            last_rotated_at=datetime(2026, 6, 1, tzinfo=UTC),
            next_rotation_due_at=datetime(2026, 7, 1, tzinfo=UTC),
            created_by="plant-operations-owner-role",
            labels={"environment": "demo"},
            notes=["Metadata-only handle; no raw credential value is stored."],
        )
    )
    repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            handle_id="cred_other",
            display_name="Other tenant handle",
            status="active",
            secret_provider="external_vault",
            secret_ref="vault://axis/demo/connectors/other",
            purpose="preview_import_readonly",
            rotation_interval_days=30,
            last_rotated_at=datetime(2026, 6, 1, tzinfo=UTC),
            next_rotation_due_at=datetime(2026, 7, 1, tzinfo=UTC),
            created_by="other-owner-role",
        )
    )

    rotation = repository.record_connector_credential_rotation(
        ConnectorCredentialRotationCreate(
            tenant_id="tenant_demo_manufacturing",
            handle_id="cred_file_csv_readonly",
            rotated_by="security-operations-role",
            rotated_at=datetime(2026, 6, 22, tzinfo=UTC),
            evidence_ref="change-window-2026-06-22",
            status="rotated",
            notes=["Reference rotated in external vault; Axis stored metadata only."],
        )
    )

    handles = repository.list_connector_credential_handles("tenant_demo_manufacturing")
    rotations = repository.list_connector_credential_rotations(
        "tenant_demo_manufacturing",
        "cred_file_csv_readonly",
    )

    assert handles == [created]
    assert handles[0].secret_ref == "vault://axis/demo/connectors/file-csv-readonly"
    assert handles[0].rotation_interval_days == 30
    assert handles[0].labels == {"environment": "demo"}
    assert rotations == [rotation]
    assert rotations[0].evidence_ref == "change-window-2026-06-22"


def test_repository_records_connector_runs_tenant_scoped(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="connector-runtime-adapter",
            event_type="connector.run.recorded",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "run_id": "run_file_csv_assets_preview_20260622",
                "execution_mode": "preview",
            },
        )
    )
    created = repository.create_connector_run(
        ConnectorRunCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            run_id="run_file_csv_assets_preview_20260622",
            status="recorded_preview_only",
            execution_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            requested_by="plant-operations-owner-role",
            credential_handle_ids=["cred_file_csv_readonly"],
            input_summary={"file_name": "manufacturing-assets-demo.csv", "record_count": "2"},
            result_summary={"accepted_record_count": "2", "rejected_record_count": "0"},
            audit_event_id=audit_event.id,
            notes=["Run record only; no connector execution occurred."],
        )
    )
    repository.create_connector_run(
        ConnectorRunCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            run_id="run_other",
            status="recorded_preview_only",
            execution_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            requested_by="other-owner-role",
            input_summary={"file_name": "other.csv"},
            result_summary={},
            audit_event_id=audit_event.id,
        )
    )

    records = repository.list_connector_runs("tenant_demo_manufacturing")

    assert records == [created]
    assert records[0].run_id == "run_file_csv_assets_preview_20260622"
    assert records[0].audit_event_id == audit_event.id
    assert records[0].credential_handle_ids == ["cred_file_csv_readonly"]
    assert records[0].input_summary == {
        "file_name": "manufacturing-assets-demo.csv",
        "record_count": "2",
    }


def test_repository_records_connector_ontology_proposals_tenant_scoped(
    session: Session,
) -> None:
    repository = AxisPersistenceRepository(session)
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="connector-preview-service",
            event_type="connector.ontology_proposals.recorded",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "proposal_ids": ["proposal_asset_line_2_packaging"],
                "write_mode": "proposal_only",
            },
        )
    )
    created = repository.create_connector_ontology_proposal(
        ConnectorOntologyProposalCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            proposal_id="proposal_asset_line_2_packaging",
            source_run_id="run_file_csv_assets_preview_20260622",
            source_file_name="manufacturing-assets-demo.csv",
            mapping_profile="manufacturing_asset_v1",
            status="proposed_from_preview",
            write_mode="proposal_only",
            graph_mutation_status="not_applied",
            proposed_by="plant-operations-owner-role",
            node_id="asset_line_2_packaging",
            node_type="asset",
            ontology_type="manufacturing_asset",
            field_summary={
                "asset_name": "Line 2 Packaging",
                "domain": "Operations",
                "station": "Line 2",
                "risk_level": "high",
            },
            evidence_refs=["manufacturing-assets-demo.csv", "asset_line_2_packaging"],
            audit_event_id=audit_event.id,
            notes=["Proposal persisted for review; graph mutation is not applied."],
        )
    )
    repository.create_connector_ontology_proposal(
        ConnectorOntologyProposalCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            proposal_id="proposal_other",
            source_file_name="other.csv",
            mapping_profile="manufacturing_asset_v1",
            proposed_by="other-owner-role",
            node_id="asset_other",
            node_type="asset",
            ontology_type="manufacturing_asset",
            field_summary={"asset_name": "Other"},
            evidence_refs=["other.csv", "asset_other"],
            audit_event_id=audit_event.id,
        )
    )

    records = repository.list_connector_ontology_proposals("tenant_demo_manufacturing")

    assert records == [created]
    assert records[0].proposal_id == "proposal_asset_line_2_packaging"
    assert records[0].source_run_id == "run_file_csv_assets_preview_20260622"
    assert records[0].write_mode == "proposal_only"
    assert records[0].graph_mutation_status == "not_applied"
    assert records[0].audit_event_id == audit_event.id
    assert records[0].field_summary == {
        "asset_name": "Line 2 Packaging",
        "domain": "Operations",
        "station": "Line 2",
        "risk_level": "high",
    }
