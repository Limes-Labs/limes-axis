import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_ontology_proposals import (
    ConnectorOntologyProposalQuery,
    build_connector_ontology_proposal_registry,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, ConnectorOntologyProposalCreate


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


def seed_connector_ontology_proposals(repository: AxisPersistenceRepository) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="connector-preview-service",
            event_type="connector.ontology_proposals.recorded",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "proposal_count": 1,
                "write_mode": "proposal_only",
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


def test_build_connector_ontology_proposal_registry_maps_persisted_proposals(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_ontology_proposals(repository)
        registry = build_connector_ontology_proposal_registry(
            repository,
            ConnectorOntologyProposalQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.metrics[0].label == "Ontology Proposals"
    assert registry.metrics[0].value == "1"
    assert registry.metrics[1].label == "Pending Review"
    assert registry.metrics[1].value == "1"
    assert registry.metrics[2].label == "Graph Mutations"
    assert registry.metrics[2].value == "0"
    assert registry.proposals[0].proposal_id == "proposal_asset_line_2_packaging"
    assert registry.proposals[0].graph_mutation_status == "not_applied"
    assert registry.proposals[0].audit_event_type == "connector.ontology_proposals.recorded"
    assert "tenant_other" not in registry.model_dump_json()
    assert "csv_content" not in registry.model_dump_json().lower()
    assert "password" not in registry.model_dump_json().lower()
    assert "credential_value" not in registry.model_dump_json().lower()


def test_connector_ontology_proposals_endpoint_returns_tenant_scoped_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_connector_ontology_proposals(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/ontology-proposals",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["metrics"][2]["value"] == "0"
    assert body["proposals"][0]["proposal_id"] == "proposal_asset_line_2_packaging"
    assert body["proposals"][0]["write_mode"] == "proposal_only"
    assert body["proposals"][0]["graph_mutation_status"] == "not_applied"
    assert "tenant_other" not in str(body)
    assert "csv_content" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_create_connector_ontology_proposals_records_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "source_run_id": "run_file_csv_assets_preview_20260622",
            "source_file_name": "manufacturing-assets-demo.csv",
            "mapping_profile": "manufacturing_asset_v1",
            "write_mode": "proposal_only",
            "proposed_by": "plant-operations-owner-role",
            "proposed_entities": [
                {
                    "proposal_id": "proposal_asset_line_2_packaging",
                    "node_id": "asset_line_2_packaging",
                    "node_type": "asset",
                    "ontology_type": "manufacturing_asset",
                    "field_summary": {
                        "asset_name": "Line 2 Packaging",
                        "domain": "Operations",
                        "station": "Line 2",
                        "risk_level": "high",
                    },
                    "evidence_refs": [
                        "manufacturing-assets-demo.csv",
                        "asset_line_2_packaging",
                    ],
                }
            ],
            "notes": ["Persist preview proposal only; do not mutate the graph."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["metrics"][0]["value"] == "1"
    assert body["metrics"][2]["value"] == "0"
    proposal = body["proposals"][0]
    assert proposal["proposal_id"] == "proposal_asset_line_2_packaging"
    assert proposal["status"] == "proposed_from_preview"
    assert proposal["write_mode"] == "proposal_only"
    assert proposal["graph_mutation_status"] == "not_applied"
    assert proposal["audit_event_type"] == "connector.ontology_proposals.recorded"
    assert proposal["audit_event_id"]
    assert "csv_content" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.ontology_proposals.recorded",
        )

    assert len(events) == 1
    assert events[0].payload["proposal_ids"] == ["proposal_asset_line_2_packaging"]
    assert events[0].payload["write_mode"] == "proposal_only"
    assert events[0].payload["graph_mutation_status"] == "not_applied"
    assert "csv_content" not in str(events[0].payload).lower()


def test_create_connector_ontology_proposals_rejects_raw_payload_fields(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "source_file_name": "manufacturing-assets-demo.csv",
            "mapping_profile": "manufacturing_asset_v1",
            "write_mode": "proposal_only",
            "proposed_by": "plant-operations-owner-role",
            "proposed_entities": [
                {
                    "proposal_id": "proposal_asset_line_2_packaging",
                    "node_id": "asset_line_2_packaging",
                    "node_type": "asset",
                    "ontology_type": "manufacturing_asset",
                    "field_summary": {
                        "asset_name": "Line 2 Packaging",
                        "csv_content": "asset_id,asset_name",
                    },
                    "evidence_refs": ["manufacturing-assets-demo.csv"],
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "raw_payload_field"


def test_create_connector_ontology_proposals_rejects_graph_write_mode(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/ontology-proposals",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "source_file_name": "manufacturing-assets-demo.csv",
            "mapping_profile": "manufacturing_asset_v1",
            "write_mode": "graph_write",
            "proposed_by": "plant-operations-owner-role",
            "proposed_entities": [
                {
                    "proposal_id": "proposal_asset_line_2_packaging",
                    "node_id": "asset_line_2_packaging",
                    "node_type": "asset",
                    "ontology_type": "manufacturing_asset",
                    "field_summary": {"asset_name": "Line 2 Packaging"},
                    "evidence_refs": ["manufacturing-assets-demo.csv"],
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "unsupported_write_mode"


def test_openapi_exposes_connector_ontology_proposal_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/ontology-proposals" in paths
