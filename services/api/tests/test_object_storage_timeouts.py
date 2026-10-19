"""Bounded S3 client transport and an off-loop startup probe (issue #942).

The export store used the MinIO library defaults (300 s connect and read
timeouts, 5 retries), and the COMPLIANCE object-lock warm-up ran that probe
synchronously inside the async lifespan, blocking startup and the event loop.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import urllib3
from fastapi.testclient import TestClient

import axis_api.main as main_module
from axis_api.config import Settings
from axis_api.main import create_app
from axis_api.object_storage import (
    ObjectLockCapability,
    S3CompatibleObjectStore,
    build_connector_export_object_store,
)


def _s3_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = dict(
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
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_export_store_client_uses_bounded_timeouts_and_retries() -> None:
    captured: dict[str, Any] = {}

    def factory(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    build_connector_export_object_store(_s3_settings(), s3_client_factory=factory)

    http_client = captured["http_client"]
    assert isinstance(http_client, urllib3.PoolManager)
    timeout = http_client.connection_pool_kw["timeout"]
    assert timeout.connect_timeout == 5.0
    assert timeout.read_timeout == 30.0
    retries = http_client.connection_pool_kw["retries"]
    assert retries.total == 2
    # Certificate verification stays on, exactly as the library default.
    assert http_client.connection_pool_kw["cert_reqs"] == "CERT_REQUIRED"


def test_export_store_transport_bounds_come_from_settings() -> None:
    store = build_connector_export_object_store(
        _s3_settings(
            AXIS_CONNECTOR_EXPORT_S3_CONNECT_TIMEOUT_SECONDS=1.5,
            AXIS_CONNECTOR_EXPORT_S3_READ_TIMEOUT_SECONDS=7,
            AXIS_CONNECTOR_EXPORT_S3_MAX_RETRIES=0,
        )
    )

    assert isinstance(store, S3CompatibleObjectStore)
    http_client = store.client._http  # the real MinIO client keeps ours
    timeout = http_client.connection_pool_kw["timeout"]
    assert (timeout.connect_timeout, timeout.read_timeout) == (1.5, 7.0)
    assert http_client.connection_pool_kw["retries"].total == 0


def test_startup_object_lock_probe_runs_off_the_event_loop_with_a_deadline(
    monkeypatch,
) -> None:
    release = threading.Event()
    calls: list[str] = []

    def blackholed_probe(_settings: Settings) -> ObjectLockCapability:
        calls.append(threading.current_thread().name)
        release.wait(10)
        return ObjectLockCapability(
            adapter="s3_compatible",
            checked=False,
            bucket_object_lock_enabled=False,
            default_retention_mode=None,
            compliance_enforceable=False,
            reason="probe_released",
        )

    monkeypatch.setattr(main_module, "probe_object_lock_capability", blackholed_probe)
    app = create_app(
        _s3_settings(
            AXIS_CONNECTOR_EXPORT_S3_CONNECT_TIMEOUT_SECONDS=0.1,
            AXIS_CONNECTOR_EXPORT_S3_READ_TIMEOUT_SECONDS=0.1,
        )
    )

    started = time.monotonic()
    try:
        with TestClient(app) as client:
            elapsed = time.monotonic() - started
            assert client.get("/health").status_code == 200
    finally:
        release.set()

    assert elapsed < 2.0
    assert calls and calls[0] != threading.main_thread().name
