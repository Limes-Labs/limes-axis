import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connector_manifests import (
    ConnectorManifestCreateRequest,
    ConnectorManifestLifecycleRequest,
    ConnectorManifestLifecycleValidationError,
    ConnectorManifestQuery,
    build_connector_manifest_registry,
    record_demo_connector_manifest,
    transition_demo_connector_manifest_lifecycle,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository


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


def external_db_manifest_request() -> ConnectorManifestCreateRequest:
    return ConnectorManifestCreateRequest(
        tenant_id="tenant_demo_manufacturing",
        registered_by="platform-connector-owner-role",
        manifest={
            "connector_id": "external_db_shift_orders",
            "display_name": "Shift orders database mirror",
            "connector_type": "external_db",
            "version": "2026-06-22",
            "source_type": "database",
            "sync_modes": ["schema_preview", "manual_import"],
            "runtime_boundary": "axis-connector-sandbox",
            "required_permissions": [
                "connectors:read",
                "connectors:external_db:preview",
            ],
            "credential_requirements": {
                "storage": "external_reference",
                "required_secret_refs": ["cred_external_db_readonly"],
                "notes": ["Metadata-only credential handle reference."],
            },
            "schema_fields": [
                {
                    "source_column": "order_id",
                    "target_field": "node_id",
                    "ontology_target": "production_order",
                    "data_type": "string",
                    "required": True,
                    "description": "Stable production order identifier.",
                }
            ],
            "mapping_notes": ["Registered as a preview-only manifest."],
        },
        runtime_policy={
            "allowed_operations": ["schema_validate", "metadata_preview"],
            "blocked_operations": [
                "live_query",
                "live_write",
                "credential_capture",
                "external_egress",
            ],
            "egress_policy": "no-external-egress",
            "max_file_size_mb": 5,
            "row_limit": 100,
            "payload_policy": "metadata-only-redacted-preview",
        },
        preview_sample={
            "file_name": "profile_postgres_ops_readonly:operations.shift_orders",
            "record_count": 1,
            "headers": ["order_id"],
            "sample_rows": [{"order_id": "order_shift_100"}],
        },
        notes=["Manifest is registered without enabling live sync."],
    )


def live_capable_external_db_manifest_request() -> ConnectorManifestCreateRequest:
    request_payload = external_db_manifest_request().model_dump()
    request_payload["manifest"]["sync_modes"] = [
        "schema_preview",
        "manual_import",
        "live_query",
    ]
    request_payload["manifest"]["mapping_notes"] = [
        "Registered with live query capability behind a separate lifecycle gate."
    ]
    request_payload["runtime_policy"]["allowed_operations"] = [
        "schema_validate",
        "metadata_preview",
        "live_query",
        "external_egress",
    ]
    request_payload["runtime_policy"]["blocked_operations"] = [
        "live_write",
        "credential_capture",
    ]
    request_payload["runtime_policy"]["egress_policy"] = (
        "allowlisted-private-egress-with-policy-evidence"
    )
    request_payload["runtime_policy"]["payload_policy"] = (
        "metadata-and-row-digest-redacted-live-query"
    )
    request_payload["notes"] = [
        "Manifest is registered live-capable but not live-enabled until lifecycle approval."
    ]
    return ConnectorManifestCreateRequest.model_validate(request_payload)


def test_build_connector_manifest_registry_maps_persisted_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        created = record_demo_connector_manifest(repository, external_db_manifest_request())
        registry = build_connector_manifest_registry(
            repository,
            ConnectorManifestQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.registry_status == "ready"
    assert registry.metrics[0].label == "Persisted Manifests"
    assert registry.metrics[0].value == "1"
    assert len(registry.manifests) == 1
    manifest = registry.manifests[0]
    assert manifest.manifest_id == created.manifest_id
    assert manifest.connector_id == "external_db_shift_orders"
    assert manifest.status == "registered_preview_only"
    assert manifest.audit_event_type == "connector.manifest.registered"
    assert manifest.manifest["connector_id"] == "external_db_shift_orders"
    assert manifest.runtime_policy["blocked_operations"] == [
        "live_query",
        "live_write",
        "credential_capture",
        "external_egress",
    ]
    serialized = registry.model_dump_json().lower()
    assert "connection_string" not in serialized
    assert "postgres://" not in serialized
    assert "password" not in serialized


def test_connector_manifests_endpoint_returns_tenant_scoped_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        record_demo_connector_manifest(
            AxisPersistenceRepository(session),
            external_db_manifest_request(),
        )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/manifests",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["manifests"][0]["connector_id"] == "external_db_shift_orders"
    assert body["manifests"][0]["audit_event_type"] == "connector.manifest.registered"
    assert "postgres://" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_create_connector_manifest_endpoint_rejects_raw_connection_material(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    request = external_db_manifest_request().model_dump()
    request["manifest"]["connection_string"] = "postgres://user:password@example.local/db"

    response = client.post("/demo/manufacturing/connectors/manifests", json=request)

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "raw_connection_field"


def test_create_connector_manifest_endpoint_rejects_invalid_manifest_payload(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    request = external_db_manifest_request().model_dump()
    request["manifest"].pop("connector_id")

    response = client.post("/demo/manufacturing/connectors/manifests", json=request)

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "invalid_manifest_payload"


def test_create_connector_manifest_endpoint_persists_public_safe_manifest(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/manifests",
        json=external_db_manifest_request().model_dump(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["connector_id"] == "external_db_shift_orders"
    assert body["status"] == "registered_preview_only"
    assert body["audit_event_id"] is not None
    assert body["audit_event_type"] == "connector.manifest.registered"
    assert body["manifest"]["connector_id"] == "external_db_shift_orders"


def test_create_connector_manifest_endpoint_rejects_duplicate_manifest(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)
    request = external_db_manifest_request().model_dump()

    first = client.post("/demo/manufacturing/connectors/manifests", json=request)
    second = client.post("/demo/manufacturing/connectors/manifests", json=request)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["reason"] == "manifest_already_exists"
    assert second.json()["detail"]["connector_id"] == "external_db_shift_orders"


def test_transition_connector_manifest_lifecycle_marks_active_preview(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(repository, external_db_manifest_request())
        transitioned = transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_preview",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Ready for governed preview configuration.",
                evidence_refs=["approval:connector-manifest-preview-activation"],
            ),
        )

    assert transitioned.status == "active_preview"
    assert transitioned.audit_event_type == "connector.manifest.lifecycle_transitioned"
    assert transitioned.notes[-1] == "Lifecycle transition: active_preview"
    assert transitioned.manifest["connector_id"] == "external_db_shift_orders"
    assert "password" not in transitioned.model_dump_json().lower()


def test_transition_connector_manifest_lifecycle_enables_active_live_with_gate(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(
            repository,
            live_capable_external_db_manifest_request(),
        )
        transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_preview",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Ready for governed preview configuration.",
                evidence_refs=["approval:connector-manifest-preview-activation"],
            ),
        )

        transitioned = transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_live",
                actor_scopes=[
                    "connectors:manifest:lifecycle",
                    "connectors:manifest:enable_live",
                ],
                transition_reason="Governance approval for allowlisted live query preflight.",
                evidence_refs=[
                    "approval:connector-live-enable",
                    "policy:egress-allowlist-reviewed",
                    "credential:external-db-readonly-lease-policy",
                ],
            ),
        )
        audit_event = repository.get_audit_event(
            "tenant_demo_manufacturing",
            transitioned.audit_event_id,
        )

    assert transitioned.status == "active_live"
    assert transitioned.audit_event_type == "connector.manifest.live_enabled"
    assert transitioned.notes[-1] == "Lifecycle transition: active_live"
    assert transitioned.manifest["sync_modes"] == [
        "schema_preview",
        "manual_import",
        "live_query",
    ]
    assert transitioned.runtime_policy["allowed_operations"] == [
        "schema_validate",
        "metadata_preview",
        "live_query",
        "external_egress",
    ]
    assert audit_event is not None
    assert audit_event.event_type == "connector.manifest.live_enabled"
    assert audit_event.payload["required_scope"] == "connectors:manifest:enable_live"
    assert audit_event.payload["live_sync_enabled"] == "true"
    assert audit_event.payload["external_sync_started"] == "false"
    assert audit_event.payload["evidence_refs"] == [
        "approval:connector-live-enable",
        "policy:egress-allowlist-reviewed",
        "credential:external-db-readonly-lease-policy",
    ]
    assert "password" not in transitioned.model_dump_json().lower()


def test_transition_connector_manifest_lifecycle_requires_live_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(
            repository,
            live_capable_external_db_manifest_request(),
        )
        transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_preview",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Ready for governed preview configuration.",
                evidence_refs=["approval:connector-manifest-preview-activation"],
            ),
        )

        with pytest.raises(ConnectorManifestLifecycleValidationError) as exc_info:
            transition_demo_connector_manifest_lifecycle(
                repository,
                "external_db_shift_orders",
                ConnectorManifestLifecycleRequest(
                    tenant_id="tenant_demo_manufacturing",
                    transitioned_by="platform-connector-owner-role",
                    target_status="active_live",
                    actor_scopes=["connectors:manifest:lifecycle"],
                    transition_reason="Governance approval for live query.",
                    evidence_refs=[
                        "approval:connector-live-enable",
                        "policy:egress-allowlist-reviewed",
                        "credential:external-db-readonly-lease-policy",
                    ],
                ),
            )

    assert exc_info.value.reason == "missing_manifest_live_scope"


def test_transition_connector_manifest_lifecycle_requires_lifecycle_scope_for_live(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(
            repository,
            live_capable_external_db_manifest_request(),
        )
        transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_preview",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Ready for governed preview configuration.",
                evidence_refs=["approval:connector-manifest-preview-activation"],
            ),
        )

        with pytest.raises(ConnectorManifestLifecycleValidationError) as exc_info:
            transition_demo_connector_manifest_lifecycle(
                repository,
                "external_db_shift_orders",
                ConnectorManifestLifecycleRequest(
                    tenant_id="tenant_demo_manufacturing",
                    transitioned_by="platform-connector-owner-role",
                    target_status="active_live",
                    actor_scopes=["connectors:manifest:enable_live"],
                    transition_reason="Governance approval for live query.",
                    evidence_refs=[
                        "approval:connector-live-enable",
                        "policy:egress-allowlist-reviewed",
                        "credential:external-db-readonly-lease-policy",
                    ],
                ),
            )

    assert exc_info.value.reason == "missing_manifest_lifecycle_scope"


def test_transition_connector_manifest_lifecycle_requires_live_runtime_policy(
    session_factory: sessionmaker[Session],
) -> None:
    request_payload = live_capable_external_db_manifest_request().model_dump()
    request_payload["runtime_policy"]["blocked_operations"].append("live_query")
    request = ConnectorManifestCreateRequest.model_validate(request_payload)

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(repository, request)
        transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_preview",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Ready for governed preview configuration.",
                evidence_refs=["approval:connector-manifest-preview-activation"],
            ),
        )

        with pytest.raises(ConnectorManifestLifecycleValidationError) as exc_info:
            transition_demo_connector_manifest_lifecycle(
                repository,
                "external_db_shift_orders",
                ConnectorManifestLifecycleRequest(
                    tenant_id="tenant_demo_manufacturing",
                    transitioned_by="platform-connector-owner-role",
                    target_status="active_live",
                    actor_scopes=[
                        "connectors:manifest:lifecycle",
                        "connectors:manifest:enable_live",
                    ],
                    transition_reason="Governance approval for live query.",
                    evidence_refs=[
                        "approval:connector-live-enable",
                        "policy:egress-allowlist-reviewed",
                        "credential:external-db-readonly-lease-policy",
                    ],
                ),
            )

    assert exc_info.value.reason == "manifest_runtime_policy_blocks_live_query"


def test_transition_connector_manifest_endpoint_requires_live_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(
            repository,
            live_capable_external_db_manifest_request(),
        )
        transition_demo_connector_manifest_lifecycle(
            repository,
            "external_db_shift_orders",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="active_preview",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Ready for governed preview configuration.",
                evidence_refs=["approval:connector-manifest-preview-activation"],
            ),
        )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/manifests/external_db_shift_orders/lifecycle",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "transitioned_by": "platform-connector-owner-role",
            "target_status": "active_live",
            "actor_scopes": [
                "connectors:manifest:lifecycle",
                "connectors:manifest:enable_live",
            ],
            "transition_reason": "Governance approval for live query.",
            "evidence_refs": ["approval:connector-live-enable"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "manifest_live_evidence_incomplete"


def test_transition_connector_manifest_lifecycle_rejects_live_enabled_target(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_connector_manifest(repository, external_db_manifest_request())
        with pytest.raises(ConnectorManifestLifecycleValidationError) as exc_info:
            transition_demo_connector_manifest_lifecycle(
                repository,
                "external_db_shift_orders",
                ConnectorManifestLifecycleRequest(
                    tenant_id="tenant_demo_manufacturing",
                    transitioned_by="platform-connector-owner-role",
                    target_status="live_enabled",
                    actor_scopes=["connectors:manifest:lifecycle"],
                    transition_reason="Enable live sync.",
                    evidence_refs=["approval:live-sync"],
                ),
            )

    assert exc_info.value.reason == "unsupported_manifest_lifecycle_target"


def test_transition_connector_manifest_endpoint_updates_manifest_with_audit(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        record_demo_connector_manifest(
            AxisPersistenceRepository(session),
            external_db_manifest_request(),
        )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/manifests/external_db_shift_orders/lifecycle",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "transitioned_by": "platform-connector-owner-role",
            "target_status": "active_preview",
            "actor_scopes": ["connectors:manifest:lifecycle"],
            "transition_reason": "Ready for governed preview configuration.",
            "evidence_refs": ["approval:connector-manifest-preview-activation"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active_preview"
    assert body["audit_event_type"] == "connector.manifest.lifecycle_transitioned"
    assert body["notes"][-1] == "Lifecycle transition: active_preview"


def test_openapi_exposes_connector_manifest_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/manifests" in paths
    assert "get" in paths["/demo/manufacturing/connectors/manifests"]
    assert "post" in paths["/demo/manufacturing/connectors/manifests"]
    assert (
        "/demo/manufacturing/connectors/manifests/{connector_id}/lifecycle" in paths
    )
    assert (
        "post"
        in paths["/demo/manufacturing/connectors/manifests/{connector_id}/lifecycle"]
    )
