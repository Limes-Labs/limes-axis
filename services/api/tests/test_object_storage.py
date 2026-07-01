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
    S3CompatibleObjectStore,
    build_connector_export_object_store,
    build_object_store_readiness,
)


class RecordingS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

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
