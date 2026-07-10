from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.model_endpoints import (
    MODEL_ENDPOINT_ADMIN_SCOPE,
    ModelEndpointConflict,
    ModelEndpointCreateRequest,
    ModelEndpointNotFound,
    ModelEndpointPermissionDenied,
    ModelEndpointStatusUpdateRequest,
    ModelEndpointValidationError,
    build_model_endpoint_registry,
    record_model_endpoint,
    update_model_endpoint_status,
)
from axis_api.model_invocations import decide_model_route
from axis_api.models import AuditEvent, Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
)

TENANT_ID = "tenant_demo_manufacturing"


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


def endpoint_request(**overrides) -> ModelEndpointCreateRequest:
    payload = {
        "tenant_id": TENANT_ID,
        "endpoint_id": "vllm_plant_local",
        "display_name": "Plant-local vLLM",
        "provider_type": "openai_compatible",
        "hosting_boundary": "self_hosted",
        "base_url": "http://vllm.axis-models.svc.cluster.local:8000",
        "default_model": "mistral-7b-instruct",
        "task_types": ["summarize", "classify"],
        "cost_input_per_1k": Decimal("0.5"),
        "cost_output_per_1k": Decimal("1.5"),
        "created_by": "platform-admin",
        "actor_scopes": [MODEL_ENDPOINT_ADMIN_SCOPE],
    }
    payload.update(overrides)
    return ModelEndpointCreateRequest(**payload)


def seed_credential_handle(repository: AxisPersistenceRepository, handle_id: str) -> None:
    repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id=TENANT_ID,
            connector_id="file_csv_manufacturing_assets",
            handle_id=handle_id,
            display_name="Model endpoint bearer secret",
            status="active",
            secret_provider="vault",
            secret_ref="vault://axis/models/plant-local-bearer",
            purpose="model_endpoint_auth",
            rotation_interval_days=30,
            created_by="platform-admin",
            labels={},
            notes=[],
        )
    )


def test_record_model_endpoint_persists_record_and_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record = record_model_endpoint(repository, endpoint_request())

        assert record.tenant_id == TENANT_ID
        assert record.endpoint_id == "vllm_plant_local"
        assert record.status == "enabled"
        assert record.task_types == ["classify", "summarize"]
        assert record.cost_input_per_1k == pytest.approx(0.5)
        assert record.cost_output_per_1k == pytest.approx(1.5)
        assert record.audit_event_id is not None
        assert record.audit_event_type == "model.endpoint.registered"

        audit_event = session.scalars(select(AuditEvent)).one()
        assert audit_event.event_type == "model.endpoint.registered"
        assert audit_event.payload["endpoint_id"] == "vllm_plant_local"
        assert audit_event.payload["permission_decision"] == {
            "allowed": True,
            "reason": "allowed",
        }


def test_record_model_endpoint_requires_admin_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(ModelEndpointPermissionDenied) as excinfo:
            record_model_endpoint(repository, endpoint_request(actor_scopes=["models:invoke"]))

        assert excinfo.value.required_permission == MODEL_ENDPOINT_ADMIN_SCOPE
        assert excinfo.value.decision.reason == (
            f"missing_scope:{MODEL_ENDPOINT_ADMIN_SCOPE}"
        )


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"provider_type": "anthropic_sdk"}, "unsupported_provider_type"),
        ({"hosting_boundary": "public_cloud"}, "unsupported_hosting_boundary"),
        ({"status": "paused"}, "unsupported_endpoint_status"),
        ({"task_types": ["summarize", "  "]}, "invalid_task_types"),
        ({"base_url": "vllm.internal:8000"}, "invalid_base_url"),
        ({"base_url": "ftp://vllm.internal:8000"}, "invalid_base_url"),
        (
            {"base_url": "https://user:hunter2@models.example.com"},
            "base_url_contains_secret",
        ),
        (
            {"base_url": "https://models.example.com/v1?api_key=raw-secret"},
            "base_url_contains_secret",
        ),
        (
            {"hosting_boundary": "external", "egress_policy_id": None},
            "egress_policy_required",
        ),
        (
            {"hosting_boundary": "approved_private_endpoint", "egress_policy_id": None},
            "egress_policy_required",
        ),
        (
            {"credential_handle_id": "handle_does_not_exist"},
            "credential_handle_not_found",
        ),
    ],
)
def test_record_model_endpoint_validation_matrix(
    session_factory: sessionmaker[Session],
    overrides: dict,
    expected_reason: str,
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(ModelEndpointValidationError) as excinfo:
            record_model_endpoint(repository, endpoint_request(**overrides))

        assert excinfo.value.reason == expected_reason


def test_record_model_endpoint_accepts_known_credential_handle(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_credential_handle(repository, "handle_model_bearer")
        record = record_model_endpoint(
            repository,
            endpoint_request(credential_handle_id="handle_model_bearer"),
        )

        assert record.credential_handle_id == "handle_model_bearer"


def test_record_model_endpoint_rejects_duplicate_endpoint_id(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_model_endpoint(repository, endpoint_request())
        with pytest.raises(ModelEndpointConflict) as excinfo:
            record_model_endpoint(repository, endpoint_request())

        assert excinfo.value.endpoint_id == "vllm_plant_local"


def test_build_model_endpoint_registry_filters_by_status(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_model_endpoint(repository, endpoint_request())
        record_model_endpoint(
            repository,
            endpoint_request(endpoint_id="vllm_disabled", status="disabled"),
        )

        registry = build_model_endpoint_registry(repository, tenant_id=TENANT_ID)
        assert registry.endpoint_count == 2
        assert registry.enabled_endpoint_count == 1

        enabled_only = build_model_endpoint_registry(
            repository,
            tenant_id=TENANT_ID,
            status="enabled",
        )
        assert [endpoint.endpoint_id for endpoint in enabled_only.endpoints] == [
            "vllm_plant_local"
        ]


def status_update_request(**overrides) -> ModelEndpointStatusUpdateRequest:
    payload = {
        "tenant_id": TENANT_ID,
        "target_status": "disabled",
        "reason": "Mis-registered base URL captured routing.",
        "updated_by": "platform-admin",
        "actor_scopes": [MODEL_ENDPOINT_ADMIN_SCOPE],
    }
    payload.update(overrides)
    return ModelEndpointStatusUpdateRequest(**payload)


def test_update_model_endpoint_status_persists_transition_and_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_model_endpoint(repository, endpoint_request())

        updated = update_model_endpoint_status(
            repository,
            "vllm_plant_local",
            status_update_request(),
        )

        assert updated.status == "disabled"
        assert updated.audit_event_type == "model.endpoint.status_changed"
        assert updated.audit_event_id is not None
        assert any("Status transition: disabled" in note for note in updated.notes)

        audit_events = list(session.scalars(select(AuditEvent)))
        status_events = [
            event
            for event in audit_events
            if event.event_type == "model.endpoint.status_changed"
        ]
        assert len(status_events) == 1
        assert status_events[0].payload["endpoint_id"] == "vllm_plant_local"
        assert status_events[0].payload["from_status"] == "enabled"
        assert status_events[0].payload["target_status"] == "disabled"

        registry = build_model_endpoint_registry(repository, tenant_id=TENANT_ID)
        assert registry.enabled_endpoint_count == 0

        re_enabled = update_model_endpoint_status(
            repository,
            "vllm_plant_local",
            status_update_request(target_status="enabled", reason="Endpoint fixed."),
        )
        assert re_enabled.status == "enabled"


def test_update_model_endpoint_status_requires_admin_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_model_endpoint(repository, endpoint_request())

        with pytest.raises(ModelEndpointPermissionDenied) as excinfo:
            update_model_endpoint_status(
                repository,
                "vllm_plant_local",
                status_update_request(actor_scopes=["models:invoke"]),
            )

        assert excinfo.value.required_permission == MODEL_ENDPOINT_ADMIN_SCOPE


def test_update_model_endpoint_status_rejects_unknown_endpoint_and_status(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_model_endpoint(repository, endpoint_request())

        with pytest.raises(ModelEndpointNotFound) as not_found:
            update_model_endpoint_status(
                repository,
                "endpoint_does_not_exist",
                status_update_request(),
            )
        assert not_found.value.endpoint_id == "endpoint_does_not_exist"

        with pytest.raises(ModelEndpointValidationError) as invalid:
            update_model_endpoint_status(
                repository,
                "vllm_plant_local",
                status_update_request(target_status="paused"),
            )
        assert invalid.value.reason == "unsupported_endpoint_status"


def test_disabled_endpoint_is_skipped_by_model_routing(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_model_endpoint(repository, endpoint_request())

        routable = build_model_endpoint_registry(repository, tenant_id=TENANT_ID)
        routed = decide_model_route(routable.endpoints, task_type="summarize")
        assert routed.status == "routed"
        assert routed.endpoint_id == "vllm_plant_local"

        update_model_endpoint_status(
            repository,
            "vllm_plant_local",
            status_update_request(),
        )

        disabled = build_model_endpoint_registry(repository, tenant_id=TENANT_ID)
        blocked = decide_model_route(disabled.endpoints, task_type="summarize")
        assert blocked.status == "blocked"
        assert blocked.reason == "no_matching_endpoint"


def test_model_endpoint_routes_create_list_and_translate_errors(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    payload = endpoint_request().model_dump(mode="json")

    created = client.post("/platform/models/endpoints", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["endpoint_id"] == "vllm_plant_local"
    assert body["audit_event_id"] is not None

    duplicate = client.post("/platform/models/endpoints", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "CONFLICT"
    assert duplicate.json()["detail"]["reason"] == "endpoint_already_exists"

    invalid = client.post(
        "/platform/models/endpoints",
        json={**payload, "endpoint_id": "vllm_external", "hosting_boundary": "external"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["reason"] == "egress_policy_required"

    denied = client.post(
        "/platform/models/endpoints",
        json={**payload, "endpoint_id": "vllm_other", "actor_scopes": []},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PERMISSION_DENIED"
    assert denied.json()["detail"]["required_permission"] == MODEL_ENDPOINT_ADMIN_SCOPE

    listing = client.get("/platform/models/endpoints", params={"tenant_id": TENANT_ID})
    assert listing.status_code == 200
    listing_body = listing.json()
    assert listing_body["endpoint_count"] == 1
    assert listing_body["endpoints"][0]["endpoint_id"] == "vllm_plant_local"


def test_model_endpoint_status_route_updates_and_translates_errors(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    client.post(
        "/platform/models/endpoints",
        json=endpoint_request().model_dump(mode="json"),
    ).raise_for_status()
    status_payload = status_update_request().model_dump(mode="json")

    disabled = client.post(
        "/platform/models/endpoints/vllm_plant_local/status",
        json=status_payload,
    )
    assert disabled.status_code == 200
    disabled_body = disabled.json()
    assert disabled_body["status"] == "disabled"
    assert disabled_body["audit_event_type"] == "model.endpoint.status_changed"
    assert disabled_body["audit_event_id"] is not None

    listing = client.get(
        "/platform/models/endpoints",
        params={"tenant_id": TENANT_ID, "status": "enabled"},
    )
    assert listing.status_code == 200
    assert listing.json()["endpoint_count"] == 0

    missing = client.post(
        "/platform/models/endpoints/endpoint_does_not_exist/status",
        json=status_payload,
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "NOT_FOUND"
    assert missing.json()["detail"]["reason"] == "model_endpoint_not_found"

    invalid = client.post(
        "/platform/models/endpoints/vllm_plant_local/status",
        json={**status_payload, "target_status": "paused"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["reason"] == "unsupported_endpoint_status"

    denied = client.post(
        "/platform/models/endpoints/vllm_plant_local/status",
        json={**status_payload, "actor_scopes": []},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PERMISSION_DENIED"
    assert denied.json()["detail"]["required_permission"] == MODEL_ENDPOINT_ADMIN_SCOPE
