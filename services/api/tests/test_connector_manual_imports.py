import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_manual_imports import (
    ConnectorManualImportQuery,
    build_connector_manual_import_registry,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, ConnectorManualImportRequestCreate


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


def manual_import_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "connector_id": "file_csv_manufacturing_assets",
        "import_id": "import_assets_manual_20260622",
        "idempotency_key": "manual-import-assets-20260622",
        "import_mode": "manual_import_request",
        "requested_by": "plant-operations-owner-role",
        "owner_role": "plant-operations-owner",
        "risk_level": "high",
        "approval_id": "appr_connector_import_assets_20260622",
        "workflow_id": "wf_connector_manual_import_review",
        "proposal_ids": ["proposal_asset_line_2_packaging"],
        "import_summary": {
            "proposal_count": "1",
            "mapping_profile": "manufacturing_asset_v1",
        },
        "controls": [
            "approval_required",
            "workflow_signal_required",
            "idempotency_enforced",
        ],
        "notes": ["Manual import request only; graph mutation is not applied."],
    }


def seed_connector_manual_imports(repository: AxisPersistenceRepository) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="plant-operations-owner-role",
            event_type="connector.manual_import.requested",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "import_id": "import_assets_manual_20260622",
                "idempotency_key": "manual-import-assets-20260622",
                "proposal_ids": ["proposal_asset_line_2_packaging"],
                "graph_mutation_status": "not_applied",
            },
        )
    )
    repository.create_connector_manual_import_request(
        ConnectorManualImportRequestCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            import_id="import_assets_manual_20260622",
            idempotency_key="manual-import-assets-20260622",
            status="approval_required",
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
            workflow_signal_status="pending_approval_decision",
            audit_event_id=audit_event.id,
            audit_event_type="connector.manual_import.requested",
            notes=["Manual import request only; graph mutation is not applied."],
        )
    )
    repository.create_connector_manual_import_request(
        ConnectorManualImportRequestCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            import_id="import_other",
            idempotency_key="manual-import-other",
            status="approval_required",
            import_mode="manual_import_request",
            requested_by="other-owner-role",
            owner_role="other-owner",
            risk_level="medium",
            approval_id="appr_other",
            workflow_id="wf_other",
            proposal_ids=["proposal_other"],
            import_summary={"proposal_count": "1"},
            audit_event_id=audit_event.id,
        )
    )


def test_build_connector_manual_import_registry_maps_persisted_requests(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_manual_imports(repository)
        registry = build_connector_manual_import_registry(
            repository,
            ConnectorManualImportQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.metrics[0].label == "Manual Imports"
    assert registry.metrics[0].value == "1"
    assert registry.metrics[1].label == "Approval Required"
    assert registry.metrics[1].value == "1"
    assert registry.metrics[2].label == "Graph Mutations"
    assert registry.metrics[2].value == "0"
    assert registry.imports[0].import_id == "import_assets_manual_20260622"
    assert registry.imports[0].proposal_ids == ["proposal_asset_line_2_packaging"]
    assert registry.imports[0].graph_mutation_status == "not_applied"
    assert registry.imports[0].workflow_signal_status == "pending_approval_decision"
    assert registry.imports[0].audit_event_type == "connector.manual_import.requested"
    assert "tenant_other" not in registry.model_dump_json()
    assert "csv_content" not in registry.model_dump_json().lower()
    assert "password" not in registry.model_dump_json().lower()
    assert "credential_value" not in registry.model_dump_json().lower()


def test_connector_manual_imports_endpoint_returns_tenant_scoped_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_connector_manual_imports(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/manual-imports",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["metrics"][2]["value"] == "0"
    assert body["imports"][0]["import_id"] == "import_assets_manual_20260622"
    assert body["imports"][0]["approval_id"] == "appr_connector_import_assets_20260622"
    assert body["imports"][0]["workflow_id"] == "wf_connector_manual_import_review"
    assert body["imports"][0]["graph_mutation_status"] == "not_applied"
    assert "tenant_other" not in str(body)
    assert "csv_content" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_create_connector_manual_import_records_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=manual_import_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["import_id"] == "import_assets_manual_20260622"
    assert body["status"] == "approval_required"
    assert body["import_mode"] == "manual_import_request"
    assert body["approval_id"] == "appr_connector_import_assets_20260622"
    assert body["workflow_id"] == "wf_connector_manual_import_review"
    assert body["workflow_signal_status"] == "pending_approval_decision"
    assert body["graph_mutation_status"] == "not_applied"
    assert body["audit_event_type"] == "connector.manual_import.requested"
    assert body["audit_event_id"]
    assert body["idempotent_replay"] is False
    assert "csv_content" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.manual_import.requested",
        )

    assert len(events) == 1
    assert events[0].payload["import_id"] == "import_assets_manual_20260622"
    assert events[0].payload["idempotency_key"] == "manual-import-assets-20260622"
    assert events[0].payload["proposal_ids"] == ["proposal_asset_line_2_packaging"]
    assert events[0].payload["graph_mutation_status"] == "not_applied"
    assert events[0].payload["workflow_signal_status"] == "pending_approval_decision"
    assert "csv_content" not in str(events[0].payload).lower()


def test_create_connector_manual_import_is_idempotent_for_same_payload(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    first_response = client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=manual_import_payload(),
    )
    second_response = client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=manual_import_payload(),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.json()["idempotent_replay"] is True
    assert second_response.json()["audit_event_id"] == first_response.json()["audit_event_id"]

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        requests = repository.list_connector_manual_import_requests("tenant_demo_manufacturing")
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.manual_import.requested",
        )

    assert len(requests) == 1
    assert len(events) == 1


def test_create_connector_manual_import_rejects_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    conflicting_payload = manual_import_payload()
    conflicting_payload["import_id"] = "import_assets_manual_other"

    assert client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=manual_import_payload(),
    ).status_code == 201

    response = client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=conflicting_payload,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "idempotency_conflict"


def test_create_connector_manual_import_rejects_raw_summary_fields(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    payload = manual_import_payload()
    payload["import_summary"] = {"csv_content": "asset_id,asset_name"}

    response = client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "raw_payload_field"


def test_create_connector_manual_import_rejects_direct_graph_write_mode(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    payload = manual_import_payload()
    payload["import_mode"] = "direct_graph_write"

    response = client.post(
        "/demo/manufacturing/connectors/manual-imports",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "unsupported_import_mode"


def test_openapi_exposes_connector_manual_import_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/manual-imports" in paths
