"""OpenTelemetry bootstrap and instrumentation tests for the Axis API.

All assertions use in-memory exporters, so no live OTLP collector is required.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from jose import jwt
from jose.utils import base64url_encode
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from axis_api.config import Settings
from axis_api.identity import StaticJwksOidcVerifier
from axis_api.main import create_app
from axis_api.telemetry import (
    SENSITIVE_ATTRIBUTE_FORBIDDEN_SUBSTRINGS,
    configure_api_telemetry,
    extract_trace_context,
    inject_trace_context,
    observability_posture,
    scrub_span_attributes,
    shutdown_providers,
)


def _base_settings(**overrides: object) -> Settings:
    values = {"postgres_dsn": "sqlite+pysqlite://"}
    values.update(overrides)
    return Settings(**values)


def _enabled_settings(**overrides: object) -> Settings:
    return _base_settings(otel_enabled=True, **overrides)


def _oct_jwks(secret: str) -> dict:
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": "axis-test",
                "k": base64url_encode(secret.encode()).decode(),
            }
        ]
    }


def _token(secret: str, claims: dict) -> str:
    return jwt.encode(claims, secret, algorithm="HS256", headers={"kid": "axis-test"})


def _app_with_in_memory_telemetry(
    settings: Settings,
) -> tuple[TestClient, InMemorySpanExporter, InMemoryMetricReader]:
    exporter = InMemorySpanExporter()
    reader = InMemoryMetricReader()
    runtime = configure_api_telemetry(settings, span_exporter=exporter, metric_reader=reader)
    app = create_app(settings, telemetry=runtime)
    return TestClient(app), exporter, reader


# --- bootstrap gating -------------------------------------------------------


def test_configure_api_telemetry_is_noop_when_disabled() -> None:
    runtime = configure_api_telemetry(_base_settings())
    assert runtime.enabled is False
    assert runtime.tracer_provider is None
    assert runtime.meter_provider is None


def test_configure_api_telemetry_builds_provider_when_enabled() -> None:
    runtime = configure_api_telemetry(
        _enabled_settings(),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )
    assert runtime.enabled is True
    assert runtime.tracer_provider is not None
    assert runtime.metrics_enabled is True


def test_disabled_app_emits_no_spans() -> None:
    # Even with an in-memory exporter attached, a disabled runtime must not
    # instrument the app (this mirrors the default deployment).
    exporter = InMemorySpanExporter()
    runtime = configure_api_telemetry(_base_settings(), span_exporter=exporter)
    client = TestClient(create_app(_base_settings(), telemetry=runtime))

    assert client.get("/health").status_code == 200
    assert exporter.get_finished_spans() == ()


# --- request instrumentation ------------------------------------------------


def test_enabled_app_produces_request_span() -> None:
    client, exporter, _ = _app_with_in_memory_telemetry(_enabled_settings())

    assert client.get("/health").status_code == 200

    spans = exporter.get_finished_spans()
    assert spans, "expected at least one request span"
    assert any(span.attributes.get("http.route") == "/health" for span in spans)


def test_request_span_carries_tenant_and_actor_but_no_sensitive_attributes() -> None:
    secret = "axis-telemetry-secret"
    settings = _enabled_settings(
        oidc_auth_required=True,
        oidc_issuer="https://issuer.example/realms/axis",
        oidc_audience="limes-axis-api",
        oidc_jwks_url="https://issuer.example/realms/axis/protocol/openid-connect/certs",
        oidc_algorithms=["HS256"],
    )
    exporter = InMemorySpanExporter()
    runtime = configure_api_telemetry(
        settings, span_exporter=exporter, metric_reader=InMemoryMetricReader()
    )
    app = create_app(settings, telemetry=runtime)
    app.state.identity_verifier = StaticJwksOidcVerifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        algorithms=settings.oidc_algorithms,
        jwks=_oct_jwks(secret),
        tenant_claim=settings.oidc_tenant_claim,
    )
    token = _token(
        secret,
        {
            "iss": settings.oidc_issuer,
            "aud": settings.oidc_audience,
            "sub": "plant-operations-owner-role",
            "axis_tenant": "tenant_demo_manufacturing",
            "scope": "audit:read",
            "exp": 4102444800,
        },
    )
    client = TestClient(app)

    response = client.get("/identity/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    spans = exporter.get_finished_spans()
    request_spans = [s for s in spans if s.attributes.get("http.route") == "/identity/session"]
    assert request_spans
    attributes = request_spans[0].attributes
    assert attributes.get("axis.tenant_id") == "tenant_demo_manufacturing"
    assert attributes.get("axis.actor_id") == "plant-operations-owner-role"

    # Privacy: no attribute key may look sensitive, and the bearer token must not
    # appear in any attribute value.
    for key, value in attributes.items():
        lowered = key.casefold()
        assert not any(term in lowered for term in SENSITIVE_ATTRIBUTE_FORBIDDEN_SUBSTRINGS)
        assert token not in str(value)


def test_operation_counters_export_data_points() -> None:
    reader = InMemoryMetricReader()
    runtime = configure_api_telemetry(
        _enabled_settings(),
        span_exporter=InMemorySpanExporter(),
        metric_reader=reader,
    )

    runtime.action_run_counter.add(1, {"outcome": "recorded"})
    runtime.approval_decision_counter.add(1, {"decision": "approve"})
    runtime.audit_export_counter.add(1, {"format": "json"})
    runtime.connector_sync_rows_counter.add(5, {"connector_id": "c1", "status": "synced"})

    data = reader.get_metrics_data()
    metric_names = {
        metric.name
        for resource_metric in data.resource_metrics
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
    }
    assert {
        "axis.action_runs",
        "axis.approval_decisions",
        "axis.audit_exports",
        "axis.connector_sync_rows",
    } <= metric_names


# --- privacy: query-string scrubbing + key guard ----------------------------


def test_request_url_query_string_is_scrubbed_from_exported_spans() -> None:
    # Plant a known-sensitive value in the request query string; the framework
    # records it verbatim in http.url / http.target, so the privacy exporter must
    # strip the entire query before export.
    client, exporter, _ = _app_with_in_memory_telemetry(_enabled_settings())
    secret = "SUPERSECRETQUERYVALUE"

    response = client.get(f"/health?access_token={secret}&cursor=abc123")
    assert response.status_code == 200

    spans = exporter.get_finished_spans()
    assert spans
    for span in spans:
        for key, value in span.attributes.items():
            assert secret not in str(value), f"secret leaked via {key}"
            assert "abc123" not in str(value), f"query leaked via {key}"
    # The path is preserved even though the query is gone.
    request_spans = [s for s in spans if s.attributes.get("http.route") == "/health"]
    assert request_spans
    url = request_spans[0].attributes.get("http.url")
    assert url is not None and url.endswith("/health") and "?" not in url


def test_scrub_span_attributes_keeps_benign_ids_and_strips_sensitive() -> None:
    scrubbed = scrub_span_attributes(
        {
            "axis.pipeline_id": "p1",
            "axis.recipe_id": "r1",
            "axis.tenant_id": "tenant_a",
            "net.peer.ip": "203.0.113.7",
            "client.address": "203.0.113.7",
            "id_token": "leak",
            "http.url": "http://host/path?token=leak&cursor=x",
        }
    )
    assert scrubbed is not None
    # Benign ids that merely contain "ip"/"id" as substrings are kept.
    assert scrubbed["axis.pipeline_id"] == "p1"
    assert scrubbed["axis.recipe_id"] == "r1"
    assert scrubbed["axis.tenant_id"] == "tenant_a"
    # Exact client-IP keys and sensitive keys are dropped.
    assert "net.peer.ip" not in scrubbed
    assert "client.address" not in scrubbed
    assert "id_token" not in scrubbed
    # URL query is stripped, path kept.
    assert scrubbed["http.url"] == "http://host/path"


def test_scrub_span_attributes_returns_none_when_nothing_sensitive() -> None:
    assert scrub_span_attributes({"axis.tenant_id": "t", "http.method": "GET"}) is None


# --- provider lifecycle -----------------------------------------------------


def test_shutdown_providers_flushes_and_is_idempotent() -> None:
    runtime = configure_api_telemetry(
        _enabled_settings(),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )
    with runtime.tracer.start_as_current_span("axis.test.flush"):
        pass

    # Must not raise, must be safe to call twice, and None-safe.
    shutdown_providers(runtime.tracer_provider, runtime.meter_provider)
    shutdown_providers(runtime.tracer_provider, runtime.meter_provider)
    shutdown_providers(None, None)


def test_enabled_app_shuts_down_telemetry_on_lifespan_exit() -> None:
    settings = _enabled_settings()
    runtime = configure_api_telemetry(
        settings,
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )
    app = create_app(settings, telemetry=runtime)
    # Entering/exiting the TestClient context runs the lifespan, whose shutdown
    # branch flushes and tears down the app-scoped providers without error.
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


# --- propagation ------------------------------------------------------------


def test_trace_context_round_trips_through_carrier() -> None:
    runtime = configure_api_telemetry(
        _enabled_settings(),
        span_exporter=InMemorySpanExporter(),
        metric_reader=InMemoryMetricReader(),
    )

    with runtime.tracer.start_as_current_span("axis.test.origin") as span:
        carrier = inject_trace_context()
        expected_trace_id = span.get_span_context().trace_id

    assert "traceparent" in carrier
    context = extract_trace_context(carrier)
    from opentelemetry.trace import get_current_span

    extracted = get_current_span(context)
    assert extracted.get_span_context().trace_id == expected_trace_id


def test_inject_is_empty_without_active_recording_span() -> None:
    # No span active + telemetry conceptually disabled -> nothing to propagate.
    assert inject_trace_context() == {}


# --- readiness posture ------------------------------------------------------


def test_observability_posture_reflects_disabled_default() -> None:
    posture = observability_posture(_base_settings())
    assert posture["otel_enabled"] is False
    assert posture["otel_metrics_enabled"] is False
    assert posture["otel_traces_endpoint"] is None


def test_observability_posture_reflects_enabled_settings() -> None:
    posture = observability_posture(
        _enabled_settings(otel_exporter_otlp_endpoint="http://collector:4318")
    )
    assert posture["otel_enabled"] is True
    assert posture["otel_metrics_enabled"] is True
    assert posture["otel_exporter_endpoint_configured"] is True
    assert posture["otel_traces_endpoint"] == "http://collector:4318/v1/traces"


def test_deployment_readiness_exposes_observability_posture() -> None:
    client = TestClient(create_app(_base_settings()))
    body = client.get("/deployment/readiness").json()
    assert body["capabilities"]["otel_enabled"] is False
    checks = {check["check_id"]: check for check in body["checks"]}
    assert checks["observability_instrumentation"]["status"] == "action_required"
    # Observability is recommended, not a production blocker.
    assert "observability_instrumentation" not in body["production_blockers"]


def test_deployment_readiness_marks_observability_ready_when_enabled() -> None:
    settings = _enabled_settings(otel_exporter_otlp_endpoint="http://collector:4318")
    client, _, _ = _app_with_in_memory_telemetry(settings)
    body = client.get("/deployment/readiness").json()
    assert body["capabilities"]["otel_enabled"] is True
    checks = {check["check_id"]: check for check in body["checks"]}
    assert checks["observability_instrumentation"]["status"] == "ready"
