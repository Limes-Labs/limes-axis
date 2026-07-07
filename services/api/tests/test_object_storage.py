from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from axis_api.config import Settings
from axis_api.errors import AxisErrorCode
from axis_api.main import connector_export_object_store, create_app
from axis_api.object_storage import (
    LocalObjectStore,
    ObjectStoreConfigurationError,
    ObjectStoreWormEnforcementError,
    S3CompatibleObjectStore,
    build_connector_export_object_store,
    build_object_store_readiness,
    probe_object_lock_capability,
)


class _FakeObjectLockConfig:
    def __init__(self, mode: str | None) -> None:
        self.mode = mode


class RecordingS3Client:
    """Fake MinIO client seam used by the whole object-store suite.

    ``object_lock_enabled`` mirrors a bucket created with S3 object-lock. When
    False, ``get_object_lock_config`` raises like a real bucket without
    object-lock, which drives the fail-closed capability probe.
    """

    def __init__(
        self, *, object_lock_enabled: bool = True, default_mode: str | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.object_lock_enabled = object_lock_enabled
        self.default_mode = default_mode
        self.legal_holds: dict[str, bool] = {}

    def put_object(
        self,
        bucket_name: str,
        object_name: str,
        data: BytesIO,
        length: int,
        content_type: str,
        **kwargs: Any,
    ) -> object:
        self.calls.append(
            {
                "bucket_name": bucket_name,
                "object_name": object_name,
                "data": data.read(),
                "length": length,
                "content_type": content_type,
                "kwargs": kwargs,
            }
        )
        return object()

    def get_object_lock_config(self, bucket_name: str) -> _FakeObjectLockConfig:
        if not self.object_lock_enabled:
            raise RuntimeError("ObjectLockConfigurationNotFoundError")
        return _FakeObjectLockConfig(self.default_mode)

    def enable_object_legal_hold(
        self, bucket_name: str, object_name: str, version_id: str | None = None
    ) -> object:
        self.legal_holds[object_name] = True
        return object()

    def disable_object_legal_hold(
        self, bucket_name: str, object_name: str, version_id: str | None = None
    ) -> object:
        self.legal_holds[object_name] = False
        return object()

    def is_object_legal_hold_enabled(
        self, bucket_name: str, object_name: str, version_id: str | None = None
    ) -> bool:
        return self.legal_holds.get(object_name, False)


def test_local_object_store_rejects_unsafe_keys(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path)

    with pytest.raises(ValueError, match="relative clean paths"):
        store.put_json("../escape.json", {"unsafe": True})

    assert list(tmp_path.rglob("*")) == []


def test_s3_compatible_object_store_writes_json_with_worm_retention() -> None:
    client = RecordingS3Client()
    fixed_now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)

    store = S3CompatibleObjectStore(
        client=client,
        bucket_name="axis-evidence",
        retention_mode="GOVERNANCE",
        retention_days=90,
        legal_hold_enabled=True,
        clock=lambda: fixed_now,
        retention_factory=lambda mode, retain_until: {
            "mode": mode,
            "retain_until": retain_until,
        },
    )

    metadata = store.put_json(
        "tenant_demo_manufacturing/evidence/snapshot.json",
        {"b": 2, "a": 1},
    )

    assert metadata.storage_adapter == "s3_compatible"
    assert metadata.storage_key == "tenant_demo_manufacturing/evidence/snapshot.json"
    assert metadata.storage_uri == "s3://axis-evidence/tenant_demo_manufacturing/evidence/snapshot.json"
    assert metadata.content_type == "application/json"
    assert metadata.size_bytes == len(b'{"a":1,"b":2}')
    assert len(metadata.checksum_sha256) == 64

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["bucket_name"] == "axis-evidence"
    assert call["object_name"] == "tenant_demo_manufacturing/evidence/snapshot.json"
    assert json.loads(call["data"]) == {"a": 1, "b": 2}
    assert call["length"] == len(call["data"])
    assert call["content_type"] == "application/json"
    assert call["kwargs"]["retention"] == {
        "mode": "GOVERNANCE",
        "retain_until": fixed_now + timedelta(days=90),
    }
    assert call["kwargs"]["legal_hold"] is True


def test_build_connector_export_object_store_requires_s3_material() -> None:
    settings = Settings(
        postgres_dsn="sqlite+pysqlite://",
        connector_export_object_store_adapter="s3_compatible",
        connector_export_s3_endpoint="minio.internal:9000",
        connector_export_s3_bucket="axis-evidence",
        connector_export_s3_access_key="axis-service-account",
        connector_export_s3_secret_key=None,
        connector_export_s3_object_lock_enabled=True,
        connector_export_s3_retention_days=90,
    )

    with pytest.raises(ObjectStoreConfigurationError, match="secret key"):
        build_connector_export_object_store(settings)


def test_connector_export_object_store_dependency_reports_misconfiguration_as_503() -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_export_object_store_adapter="s3_compatible",
            connector_export_s3_endpoint="minio.internal:9000",
            connector_export_s3_bucket="axis-evidence",
            connector_export_s3_access_key="axis-service-account",
            connector_export_s3_secret_key=None,
            connector_export_s3_object_lock_enabled=True,
            connector_export_s3_retention_days=90,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        connector_export_object_store(SimpleNamespace(app=app))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == AxisErrorCode.CONNECTOR_UNAVAILABLE.value
    assert exc_info.value.detail["reason"] == "object_store_misconfigured"
    assert "axis-service-account" not in str(exc_info.value.detail)


def test_build_connector_export_object_store_uses_configured_s3_client_factory() -> None:
    client = RecordingS3Client()
    captured: dict[str, Any] = {}

    def client_factory(**kwargs: Any) -> RecordingS3Client:
        captured.update(kwargs)
        return client

    settings = Settings(
        postgres_dsn="sqlite+pysqlite://",
        connector_export_object_store_adapter="s3_compatible",
        connector_export_s3_endpoint="https://minio.internal:9443",
        connector_export_s3_region="eu-central-1",
        connector_export_s3_bucket="axis-evidence",
        connector_export_s3_access_key="axis-service-account",
        connector_export_s3_secret_key="axis-secret-key",
        connector_export_s3_object_lock_enabled=True,
        connector_export_s3_retention_mode="COMPLIANCE",
        connector_export_s3_retention_days=365,
        connector_export_s3_legal_hold_enabled=True,
    )

    store = build_connector_export_object_store(settings, s3_client_factory=client_factory)

    assert isinstance(store, S3CompatibleObjectStore)
    assert captured == {
        "endpoint": "minio.internal:9443",
        "access_key": "axis-service-account",
        "secret_key": "axis-secret-key",
        "secure": True,
        "region": "eu-central-1",
    }


def test_object_store_readiness_reports_specific_missing_s3_requirements() -> None:
    readiness = build_object_store_readiness(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_export_object_store_adapter="s3_compatible",
            connector_export_s3_endpoint="minio.internal:9000",
            connector_export_s3_bucket="axis-evidence",
            connector_export_s3_access_key="axis-service-account",
            connector_export_s3_secret_key=None,
            connector_export_s3_object_lock_enabled=False,
            connector_export_s3_retention_days=0,
        )
    )

    assert readiness.adapter == "s3_compatible"
    assert readiness.production_ready is False
    assert readiness.bucket_configured is True
    assert readiness.endpoint_configured is True
    assert readiness.credentials_configured is False
    assert readiness.worm_retention_enabled is False
    assert readiness.missing_requirements == [
        "secret key",
        "object lock",
        "retention days",
    ]


def test_object_store_readiness_treats_http_endpoint_as_insecure() -> None:
    readiness = build_object_store_readiness(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_export_object_store_adapter="s3_compatible",
            connector_export_s3_endpoint="http://minio.internal:9000",
            connector_export_s3_bucket="axis-evidence",
            connector_export_s3_access_key="axis-service-account",
            connector_export_s3_secret_key="axis-secret-key",
            connector_export_s3_secure_transport=True,
            connector_export_s3_object_lock_enabled=True,
            connector_export_s3_retention_days=90,
        )
    )

    assert readiness.production_ready is False
    assert readiness.secure_transport is False
    assert readiness.missing_requirements == ["TLS transport"]


def _compliance_s3_settings() -> Settings:
    return Settings(
        postgres_dsn="sqlite+pysqlite://",
        connector_export_object_store_adapter="s3_compatible",
        connector_export_s3_endpoint="https://minio.internal:9443",
        connector_export_s3_bucket="axis-evidence",
        connector_export_s3_access_key="axis-service-account",
        connector_export_s3_secret_key="axis-secret-key",
        connector_export_s3_secure_transport=True,
        connector_export_s3_object_lock_enabled=True,
        connector_export_s3_retention_mode="COMPLIANCE",
        connector_export_s3_retention_days=365,
        connector_export_s3_legal_hold_enabled=True,
    )


def _compliance_store(client: RecordingS3Client) -> S3CompatibleObjectStore:
    fixed_now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    return S3CompatibleObjectStore(
        client=client,
        bucket_name="axis-evidence",
        retention_mode="COMPLIANCE",
        retention_days=365,
        legal_hold_enabled=True,
        clock=lambda: fixed_now,
    )


def test_retention_until_is_explicit_from_retention_days() -> None:
    fixed_now = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    store = S3CompatibleObjectStore(
        client=RecordingS3Client(),
        bucket_name="axis-evidence",
        retention_mode="COMPLIANCE",
        retention_days=365,
        legal_hold_enabled=False,
        clock=lambda: fixed_now,
    )

    assert store.retention_until() == fixed_now + timedelta(days=365)
    assert store.retention_until(now=fixed_now) == datetime(
        2027, 6, 30, 12, 0, tzinfo=UTC
    )


def test_retention_days_zero_and_none_are_rejected() -> None:
    for invalid_days in (0, -1):
        with pytest.raises(ObjectStoreConfigurationError, match="retention days"):
            S3CompatibleObjectStore(
                client=RecordingS3Client(),
                bucket_name="axis-evidence",
                retention_mode="COMPLIANCE",
                retention_days=invalid_days,
                legal_hold_enabled=False,
            )


def test_object_lock_capability_reports_enabled_bucket() -> None:
    client = RecordingS3Client(object_lock_enabled=True, default_mode="COMPLIANCE")
    store = _compliance_store(client)

    capability = store.object_lock_capability()

    assert capability.checked is True
    assert capability.bucket_object_lock_enabled is True
    assert capability.compliance_enforceable is True
    assert capability.default_retention_mode == "COMPLIANCE"


def test_object_lock_capability_fails_closed_without_object_lock() -> None:
    client = RecordingS3Client(object_lock_enabled=False)
    store = _compliance_store(client)

    capability = store.object_lock_capability()

    assert capability.checked is True
    assert capability.bucket_object_lock_enabled is False
    assert capability.compliance_enforceable is False
    assert "probe_failed" in capability.reason


def test_compliance_put_writes_with_object_lock_retention_and_legal_hold() -> None:
    client = RecordingS3Client(object_lock_enabled=True)
    store = _compliance_store(client)

    store.put_json("tenant_demo_manufacturing/evidence/bundle.json", {"a": 1})

    assert len(client.calls) == 1
    kwargs = client.calls[0]["kwargs"]
    retention = kwargs["retention"]
    # The MinIO Retention object carries COMPLIANCE mode + explicit RetainUntilDate.
    assert retention.mode == "COMPLIANCE"
    assert retention.retain_until_date == datetime(2027, 6, 30, 12, 0, tzinfo=UTC)
    assert kwargs["legal_hold"] is True


def test_compliance_put_fails_closed_without_object_lock_bucket() -> None:
    client = RecordingS3Client(object_lock_enabled=False)
    store = _compliance_store(client)

    with pytest.raises(ObjectStoreWormEnforcementError, match="probe_failed"):
        store.put_json("tenant_demo_manufacturing/evidence/bundle.json", {"a": 1})

    assert client.calls == []


def test_governance_put_does_not_probe_object_lock() -> None:
    client = RecordingS3Client(object_lock_enabled=False)
    store = S3CompatibleObjectStore(
        client=client,
        bucket_name="axis-evidence",
        retention_mode="GOVERNANCE",
        retention_days=90,
        legal_hold_enabled=False,
        clock=lambda: datetime(2026, 6, 30, 12, 0, tzinfo=UTC),
    )

    store.put_json("tenant_demo_manufacturing/evidence/bundle.json", {"a": 1})

    # GOVERNANCE never fails closed on the object-lock probe.
    assert len(client.calls) == 1


def test_object_store_legal_hold_apply_and_release() -> None:
    client = RecordingS3Client(object_lock_enabled=True)
    store = _compliance_store(client)
    key = "tenant_demo_manufacturing/evidence/bundle.json"

    store.apply_legal_hold(key)
    assert store.legal_hold_status(key) is True

    store.release_legal_hold(key)
    assert store.legal_hold_status(key) is False


def test_local_store_cannot_provide_worm() -> None:
    capability = LocalObjectStore("/tmp/does-not-matter").object_lock_capability()

    assert capability.compliance_enforceable is False
    assert capability.bucket_object_lock_enabled is False
    assert "local_filesystem_store_cannot_provide_worm" in capability.reason


def test_readiness_compliance_not_ready_without_verified_bucket() -> None:
    readiness = build_object_store_readiness(_compliance_s3_settings())

    # No probe supplied: COMPLIANCE cannot be confirmed enforceable.
    assert readiness.compliance_enforceable is False
    assert readiness.production_ready is False
    assert "verified object-lock bucket" in readiness.missing_requirements
    assert readiness.object_lock_probe_reason == "not_probed"


def test_readiness_compliance_ready_with_verified_probe() -> None:
    client = RecordingS3Client(object_lock_enabled=True, default_mode="COMPLIANCE")
    capability = probe_object_lock_capability(
        _compliance_s3_settings(), s3_client_factory=lambda **_: client
    )

    readiness = build_object_store_readiness(
        _compliance_s3_settings(), object_lock_capability=capability
    )

    assert capability.compliance_enforceable is True
    assert readiness.compliance_enforceable is True
    assert readiness.object_lock_bucket_verified is True
    assert readiness.production_ready is True
    assert "verified object-lock bucket" not in readiness.missing_requirements


def test_readiness_local_store_compliance_not_supportable() -> None:
    settings = Settings(
        postgres_dsn="sqlite+pysqlite://",
        connector_export_object_store_adapter="local_filesystem",
        connector_export_s3_retention_mode="COMPLIANCE",
    )

    readiness = build_object_store_readiness(settings)

    assert readiness.adapter == "local_filesystem"
    assert readiness.compliance_enforceable is False
    assert "local_filesystem_store_cannot_provide_worm" in readiness.object_lock_probe_reason
    assert "verified object-lock bucket" in readiness.missing_requirements


def test_probe_object_lock_capability_local_store_fails_closed() -> None:
    capability = probe_object_lock_capability(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_export_object_store_adapter="local_filesystem",
            connector_export_s3_retention_mode="COMPLIANCE",
        )
    )

    assert capability.compliance_enforceable is False
    assert capability.adapter == "local_filesystem"
