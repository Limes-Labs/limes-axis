import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_ontology_promotions import (
    ConnectorOntologyPromotionRequest,
    record_demo_connector_ontology_promotion,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import (
    AuditEvent,
    Base,
    ConnectorOntologyPromotion,
    ConnectorOntologyProposal,
)
from axis_api.ontology.mutations import (
    OntologyMutationError,
    OntologyMutationRequest,
    OntologyMutationResult,
)
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorManualImportRequestCreate,
    ConnectorOntologyProposalCreate,
    ConnectorPromotionPolicyCreate,
)


class RecordingOntologyMutationRuntime:
    def __init__(self) -> None:
        self.requests: list[OntologyMutationRequest] = []

    def promote_connector_proposal(
        self,
        request: OntologyMutationRequest,
    ) -> OntologyMutationResult:
        self.requests.append(request)
        return OntologyMutationResult(
            status="type_db_mutation_applied",
            adapter="axis-test-typedb-adapter",
            mutation_ref=f"typedb://axis/{request.node_id}",
            typeql=request.typeql,
            payload=request.audit_payload,
        )


class FailingOntologyMutationRuntime:
    def promote_connector_proposal(
        self,
        request: OntologyMutationRequest,
    ) -> OntologyMutationResult:
        raise OntologyMutationError("synthetic_typedb_down")


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def seed_promotable_connector_proposal(repository: AxisPersistenceRepository) -> None:
    proposal_audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="connector-preview-service",
            event_type="connector.ontology_proposals.recorded",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "proposal_ids": ["proposal_asset_line_2_packaging"],
                "graph_mutation_status": "not_applied",
            },
        )
    )
    repository.create_connector_ontology_proposal(
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
            audit_event_id=proposal_audit_event.id,
            audit_event_type="connector.ontology_proposals.recorded",
            notes=["Proposal persisted for review; graph mutation is not applied."],
        )
    )
    manual_import_audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="plant-operations-owner-role",
            event_type="connector.manual_import.decision_recorded",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "import_id": "import_assets_manual_20260622",
                "decision": "approve",
                "proposal_ids": ["proposal_asset_line_2_packaging"],
                "workflow_signal": {"status": "manual_import_signal_requested"},
            },
        )
    )
    repository.create_connector_manual_import_request(
        ConnectorManualImportRequestCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            import_id="import_assets_manual_20260622",
            idempotency_key="manual-import-assets-20260622",
            status="approval_approved",
            import_mode="manual_import_request",
            requested_by="plant-operations-owner-role",
            owner_role="plant-operations-owner",
            risk_level="high",
            approval_id="appr_connector_import_assets_20260622",
            workflow_id="wf_connector_manual_import_review",
            proposal_ids=["proposal_asset_line_2_packaging"],
            import_summary={
                "proposal_count": "1",
                "mapping_profile": "manufacturing_asset_v1",
            },
            controls=[
                "approval_required",
                "workflow_signal_required",
                "idempotency_enforced",
            ],
            graph_mutation_status="not_applied",
            workflow_signal_status="manual_import_signal_requested",
            decision="approve",
            decision_actor_id="plant-operations-owner-role",
            decision_note="Approved import request; graph mutation remains gated.",
            workflow_signal={
                "workflow_id": "wf_connector_manual_import_review",
                "status": "manual_import_signal_requested",
                "adapter": "axis-test-workflow-adapter",
                "signal_name": "connector_manual_import_decided",
                "payload": {
                    "proposal_ids": ["proposal_asset_line_2_packaging"],
                    "graph_mutation_status": "not_applied",
                },
            },
            audit_event_id=manual_import_audit_event.id,
            audit_event_type="connector.manual_import.decision_recorded",
            notes=["Manual import request only; graph mutation is not applied."],
        )
    )


def seed_required_promotion_policy(
    repository: AxisPersistenceRepository,
    *,
    policy_id: str = "policy_connector_asset_promotion_v1",
    allowed_risk_levels: list[str] | None = None,
    allowed_ontology_types: list[str] | None = None,
    status: str = "enabled",
    enforcement_mode: str = "required",
) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="platform-governance-owner-role",
            event_type="connector.promotion_policy.authored",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "policy_id": policy_id,
                "status": status,
                "enforcement_mode": enforcement_mode,
                "required_scopes": ["connectors:ontology:promote"],
            },
        )
    )
    repository.create_connector_promotion_policy(
        ConnectorPromotionPolicyCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            policy_id=policy_id,
            policy_version="2026-06-22",
            status=status,
            enforcement_mode=enforcement_mode,
            created_by="platform-governance-owner-role",
            required_scopes=["connectors:ontology:promote"],
            required_manual_import_status="approval_approved",
            required_workflow_signal_status="manual_import_signal_requested",
            allowed_risk_levels=allowed_risk_levels or ["high", "medium"],
            allowed_ontology_types=allowed_ontology_types or ["manufacturing_asset"],
            review_window_hours=24,
            permission_decision={"allowed": True, "reason": "allowed"},
            audit_event_id=audit_event.id,
            audit_event_type="connector.promotion_policy.authored",
            notes=["Required policy for connector ontology promotion."],
        )
    )


def promotion_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "promotion_id": "promote_asset_line_2_packaging_20260622",
        "idempotency_key": "promote-asset-line-2-packaging-20260622",
        "proposal_id": "proposal_asset_line_2_packaging",
        "manual_import_id": "import_assets_manual_20260622",
        "actor_id": "plant-operations-owner-role",
        "actor_scopes": ["connectors:ontology:promote"],
        "note": "Promote approved proposal into TypeDB asset graph.",
    }


def promotion_payload_with_policy() -> dict:
    payload = promotion_payload()
    payload["policy_id"] = "policy_connector_asset_promotion_v1"
    return payload


def test_record_connector_ontology_promotion_applies_mutation_and_updates_records(
    session_factory: sessionmaker[Session],
) -> None:
    ontology_runtime = RecordingOntologyMutationRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_promotable_connector_proposal(repository)
        result = record_demo_connector_ontology_promotion(
            repository,
            ConnectorOntologyPromotionRequest(**promotion_payload()),
            ontology_runtime,
        )

    with session_factory() as session:
        promotion = session.scalars(select(ConnectorOntologyPromotion)).one()
        proposal = session.scalars(select(ConnectorOntologyProposal)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.ontology_promotion.applied"
            )
        ).one()

    assert result.status == "promoted_to_graph"
    assert result.graph_mutation_status == "type_db_mutation_applied"
    assert result.permission_decision.model_dump() == {"allowed": True, "reason": "allowed"}
    assert result.ontology_mutation.status == "type_db_mutation_applied"
    assert result.ontology_mutation.payload["node_id"] == "asset_line_2_packaging"
    assert result.ontology_mutation.payload["field_summary_keys"] == [
        "asset_name",
        "domain",
        "risk_level",
        "station",
    ]
    assert result.proposal.status == "promoted_to_graph"
    assert result.proposal.graph_mutation_status == "type_db_mutation_applied"
    assert result.proposal.promotion_id == "promote_asset_line_2_packaging_20260622"
    assert promotion.idempotency_key == "promote-asset-line-2-packaging-20260622"
    assert promotion.status == "promoted_to_graph"
    assert promotion.graph_mutation_status == "type_db_mutation_applied"
    assert proposal.status == "promoted_to_graph"
    assert proposal.graph_mutation_status == "type_db_mutation_applied"
    assert proposal.promotion_id == "promote_asset_line_2_packaging_20260622"
    assert proposal.ontology_mutation["status"] == "type_db_mutation_applied"
    assert audit_event.payload["promotion_id"] == "promote_asset_line_2_packaging_20260622"
    assert audit_event.payload["manual_import_id"] == "import_assets_manual_20260622"
    assert audit_event.payload["graph_mutation_status"] == "type_db_mutation_applied"
    assert ontology_runtime.requests[0].typeql.startswith("insert")
    assert "axis_asset" in ontology_runtime.requests[0].typeql
    assert "asset_line_2_packaging" in ontology_runtime.requests[0].typeql
    assert "csv_content" not in str(audit_event.payload).lower()


def test_record_connector_ontology_promotion_enforces_required_policy_and_persists_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    ontology_runtime = RecordingOntologyMutationRuntime()
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_promotable_connector_proposal(repository)
        seed_required_promotion_policy(repository)
        result = record_demo_connector_ontology_promotion(
            repository,
            ConnectorOntologyPromotionRequest(**promotion_payload_with_policy()),
            ontology_runtime,
        )

    with session_factory() as session:
        promotion = session.scalars(select(ConnectorOntologyPromotion)).one()
        proposal = session.scalars(select(ConnectorOntologyProposal)).one()
        audit_event = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "connector.ontology_promotion.applied"
            )
        ).one()

    assert result.policy_decision is not None
    assert result.policy_decision.status == "policy_enforced"
    assert result.policy_decision.allowed is True
    assert result.policy_decision.policy_id == "policy_connector_asset_promotion_v1"
    assert result.policy_decision.policy_version == "2026-06-22"
    assert result.policy_decision.enforcement_mode == "required"
    assert result.policy_decision.reason == "policy_constraints_satisfied"
    assert result.policy_decision.matched_constraints["risk_level"] == "high"
    assert result.policy_decision.matched_constraints["ontology_type"] == "manufacturing_asset"
    assert promotion.policy_id == "policy_connector_asset_promotion_v1"
    assert promotion.policy_decision["status"] == "policy_enforced"
    assert proposal.policy_id == "policy_connector_asset_promotion_v1"
    assert proposal.policy_decision["reason"] == "policy_constraints_satisfied"
    assert audit_event.payload["policy_id"] == "policy_connector_asset_promotion_v1"
    assert audit_event.payload["policy_decision"]["status"] == "policy_enforced"
    matched_constraints = audit_event.payload["policy_decision"]["matched_constraints"]
    assert matched_constraints["workflow_signal_status"] == "manual_import_signal_requested"


def test_connector_ontology_promotion_endpoint_applies_mutation(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    app.state.ontology_mutation_runtime = RecordingOntologyMutationRuntime()
    with session_scope(session_factory) as session:
        seed_promotable_connector_proposal(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "promoted_to_graph"
    assert body["graph_mutation_status"] == "type_db_mutation_applied"
    assert body["proposal"]["status"] == "promoted_to_graph"
    assert body["proposal"]["promotion_id"] == "promote_asset_line_2_packaging_20260622"
    assert body["ontology_mutation"]["status"] == "type_db_mutation_applied"
    assert body["audit_event_type"] == "connector.ontology_promotion.applied"


def test_connector_ontology_promotion_endpoint_rejects_missing_permission(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_promotable_connector_proposal(AxisPersistenceRepository(session))
    client = TestClient(app)
    payload = promotion_payload()
    payload["actor_scopes"] = []

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"


def test_connector_ontology_promotion_endpoint_requires_approved_manual_import(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_promotable_connector_proposal(repository)
        manual_import = repository.get_connector_manual_import_request(
            "tenant_demo_manufacturing",
            "import_assets_manual_20260622",
        )
        manual_import.status = "approval_required"
        manual_import.decision = None
        manual_import.workflow_signal = None
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload(),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "manual_import_not_approved"


def test_connector_ontology_promotion_endpoint_rejects_missing_policy(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_promotable_connector_proposal(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload_with_policy(),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "promotion_policy_not_found"


def test_connector_ontology_promotion_endpoint_rejects_policy_risk_mismatch(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_promotable_connector_proposal(repository)
        seed_required_promotion_policy(repository, allowed_risk_levels=["low"])
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload_with_policy(),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "promotion_policy_rejected"
    with session_factory() as session:
        assert list(session.scalars(select(ConnectorOntologyPromotion))) == []


def test_connector_ontology_promotion_endpoint_records_runtime_unavailable(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    app.state.ontology_mutation_runtime = FailingOntologyMutationRuntime()
    with session_scope(session_factory) as session:
        seed_promotable_connector_proposal(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "promotion_failed"
    assert body["graph_mutation_status"] == "type_db_mutation_unavailable"
    assert body["ontology_mutation"]["payload"]["reason"] == "synthetic_typedb_down"
    assert body["proposal"]["status"] == "proposed_from_preview"
    assert body["proposal"]["graph_mutation_status"] == "not_applied"


def test_connector_ontology_promotion_is_idempotent_for_same_payload(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    app.state.ontology_mutation_runtime = RecordingOntologyMutationRuntime()
    with session_scope(session_factory) as session:
        seed_promotable_connector_proposal(AxisPersistenceRepository(session))
    client = TestClient(app)

    first_response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload(),
    )
    second_response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload(),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.json()["idempotent_replay"] is True
    assert second_response.json()["audit_event_id"] == first_response.json()["audit_event_id"]


def test_connector_ontology_promotion_rejects_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    app.state.ontology_mutation_runtime = RecordingOntologyMutationRuntime()
    with session_scope(session_factory) as session:
        seed_promotable_connector_proposal(AxisPersistenceRepository(session))
    client = TestClient(app)
    conflicting_payload = promotion_payload()
    conflicting_payload["proposal_id"] = "proposal_other"

    assert client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=promotion_payload(),
    ).status_code == 201

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        json=conflicting_payload,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "idempotency_conflict"
    assert response.json()["detail"]["promotion_id"] == "promote_asset_line_2_packaging_20260622"


def test_openapi_exposes_connector_ontology_promotion_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/ontology-proposals/promotions" in paths
