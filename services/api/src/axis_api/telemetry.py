"""OpenTelemetry bootstrap for the Axis API (off by default).

The whole subsystem is gated by :attr:`Settings.otel_enabled` (``AXIS_OTEL_ENABLED``,
default ``false``). When disabled, :func:`configure_api_telemetry` returns a
:class:`TelemetryRuntime` whose tracer/meter are the process-global *no-op*
providers, so instrumented code paths create non-recording spans and no-op metric
instruments — zero exporters installed, negligible overhead, and no behavior
change for existing deployments or the default test suite.

When enabled we build an app-scoped :class:`~opentelemetry.sdk.trace.TracerProvider`
and :class:`~opentelemetry.sdk.metrics.MeterProvider` (never mutating the OTel
global providers, so multiple app instances and tests stay isolated) with a
``Resource`` describing ``service.name`` / ``service.version`` /
``deployment.environment`` and an OTLP/HTTP exporter pointed at
``AXIS_OTEL_EXPORTER_OTLP_ENDPOINT``.

Privacy: span attributes and metric labels follow the same rule as audit
payloads — only stable, non-sensitive identifiers (tenant id, actor id, resource
ids, outcomes). Never record tokens, secrets, client IPs, or raw payload values.
See :data:`SENSITIVE_ATTRIBUTE_FORBIDDEN_SUBSTRINGS`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from opentelemetry import metrics, trace
from opentelemetry.metrics import Counter, Meter, MeterProvider
from opentelemetry.propagators.textmap import CarrierT
from opentelemetry.trace import Span, Tracer, TracerProvider
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from axis_api.config import Settings

DEFAULT_SERVICE_NAME = "limes-axis-api"
SERVICE_VERSION = "0.0.0"
_INSTRUMENTATION_SCOPE = "axis_api"

# Non-sensitive span attribute / metric label keys. These mirror the identifiers
# already surfaced in audit payloads.
ATTR_TENANT_ID = "axis.tenant_id"
ATTR_ACTOR_ID = "axis.actor_id"
ATTR_ACTION_ID = "axis.action_id"
ATTR_ACTION_RUN_ID = "axis.action_run_id"
ATTR_APPROVAL_ID = "axis.approval_id"
ATTR_CONNECTOR_ID = "axis.connector_id"
ATTR_EXECUTION_MODE = "axis.execution_mode"
ATTR_OUTCOME = "axis.outcome"
ATTR_WORKFLOW_ID = "axis.workflow_id"
ATTR_SIGNAL_NAME = "axis.signal_name"
ATTR_SIGNAL_STATUS = "axis.signal_status"
ATTR_DECISION = "axis.decision"
ATTR_EXPORT_FORMAT = "axis.export_format"
ATTR_JOB = "axis.job"

# Defence-in-depth guard: attribute keys containing any of these substrings must
# never be attached to a span. Callers are expected to only pass the curated keys
# above; this is a belt-and-braces filter enforced by ``set_span_attributes``.
SENSITIVE_ATTRIBUTE_FORBIDDEN_SUBSTRINGS = (
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "ip",
    "client.address",
    "api_key",
    "apikey",
)

_W3C_PROPAGATOR = TraceContextTextMapPropagator()


def _is_sensitive_attribute_key(key: str) -> bool:
    lowered = key.casefold()
    return any(token in lowered for token in SENSITIVE_ATTRIBUTE_FORBIDDEN_SUBSTRINGS)


def set_span_attributes(span: Span, attributes: Mapping[str, object]) -> None:
    """Attach non-null, non-sensitive attributes to ``span``.

    Silently drops ``None`` values (so callers can pass optional ids uniformly)
    and any key that trips the sensitive-substring guard.
    """

    for key, value in attributes.items():
        if value is None:
            continue
        if _is_sensitive_attribute_key(key):
            continue
        span.set_attribute(key, value)


def annotate_current_span(attributes: Mapping[str, object]) -> None:
    """Attach attributes to whatever span is active in the current context.

    Used by the principal resolver to tag the auto-instrumentation request span
    with tenant/actor once identity is known. A no-op when no span is recording.
    """

    span = trace.get_current_span()
    if not span.is_recording():
        return
    set_span_attributes(span, attributes)


def inject_trace_context(carrier: CarrierT | None = None) -> dict[str, str]:
    """Serialise the active W3C trace context into a carrier dict.

    Returns an empty dict when no span is recording (telemetry disabled or no
    active span), so the outbound signal payload is unchanged in that case.
    """

    target: dict[str, str] = {} if carrier is None else carrier  # type: ignore[assignment]
    _W3C_PROPAGATOR.inject(target)
    return target


def extract_trace_context(carrier: CarrierT):
    """Rebuild an OTel context from a carrier produced by :func:`inject_trace_context`."""

    return _W3C_PROPAGATOR.extract(carrier)


@dataclass(frozen=True)
class TelemetryRuntime:
    """Handle to the tracer, meter, and metric instruments for one service.

    When ``enabled`` is ``False`` the tracer/meter are the OTel no-op globals and
    all instruments are no-ops, so instrumented code stays branch-free.
    """

    enabled: bool
    tracer: Tracer
    meter: Meter
    tracer_provider: TracerProvider | None
    meter_provider: MeterProvider | None
    action_run_counter: Counter
    connector_sync_rows_counter: Counter
    approval_decision_counter: Counter
    audit_export_counter: Counter

    @property
    def metrics_enabled(self) -> bool:
        return self.meter_provider is not None


def _noop_runtime() -> TelemetryRuntime:
    tracer = trace.get_tracer(_INSTRUMENTATION_SCOPE, SERVICE_VERSION)
    meter = metrics.get_meter(_INSTRUMENTATION_SCOPE, SERVICE_VERSION)
    return _build_runtime(
        enabled=False,
        tracer=tracer,
        meter=meter,
        tracer_provider=None,
        meter_provider=None,
    )


def _build_runtime(
    *,
    enabled: bool,
    tracer: Tracer,
    meter: Meter,
    tracer_provider: TracerProvider | None,
    meter_provider: MeterProvider | None,
) -> TelemetryRuntime:
    return TelemetryRuntime(
        enabled=enabled,
        tracer=tracer,
        meter=meter,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        action_run_counter=meter.create_counter(
            "axis.action_runs",
            unit="1",
            description="Persisted manufacturing action runs by outcome.",
        ),
        connector_sync_rows_counter=meter.create_counter(
            "axis.connector_sync_rows",
            unit="1",
            description="Rows ingested by connector sync execution.",
        ),
        approval_decision_counter=meter.create_counter(
            "axis.approval_decisions",
            unit="1",
            description="Recorded approval decisions by decision value.",
        ),
        audit_export_counter=meter.create_counter(
            "axis.audit_exports",
            unit="1",
            description="Audit evidence export operations.",
        ),
    )


class _PrivacyFilteringSpanExporter:
    """Wrap a span exporter and strip sensitive attributes before export.

    The FastAPI/ASGI auto-instrumentation records standard HTTP attributes that
    include the client IP (``net.peer.ip`` / ``client.address``). Axis follows the
    same privacy rules as its audit payloads — no IPs, tokens, or secrets — so we
    drop any attribute whose key trips the sensitive-substring guard on every span
    regardless of which exporter is configured.
    """

    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped

    def export(self, spans):
        for span in spans:
            attributes = span.attributes
            if attributes and any(_is_sensitive_attribute_key(key) for key in attributes):
                span._attributes = {
                    key: value
                    for key, value in attributes.items()
                    if not _is_sensitive_attribute_key(key)
                }
        return self._wrapped.export(spans)

    def shutdown(self):
        return self._wrapped.shutdown()

    def force_flush(self, timeout_millis: int = 30_000):
        return self._wrapped.force_flush(timeout_millis)


def build_resource(settings: Settings, *, service_name: str, service_version: str):
    """Build an OTel ``Resource`` from settings (imported lazily to stay light)."""

    from opentelemetry.sdk.resources import Resource

    return Resource.create(
        {
            "service.name": settings.otel_service_name or service_name,
            "service.version": service_version,
            "deployment.environment": settings.environment,
        }
    )


def build_sdk_providers(
    settings: Settings,
    *,
    service_name: str,
    service_version: str,
    span_exporter=None,
    metric_reader=None,
):
    """Build app-scoped tracer/meter providers + tracer/meter for one service.

    Shared by the API and worker bootstraps. Never touches the OTel global
    providers, so each caller (and each test) stays isolated. Returns
    ``(tracer_provider, meter_provider_or_none, tracer, meter)``.
    """

    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    resource = build_resource(
        settings,
        service_name=service_name,
        service_version=service_version,
    )
    tracer_provider = SdkTracerProvider(resource=resource)
    if span_exporter is not None:
        tracer_provider.add_span_processor(
            SimpleSpanProcessor(_PrivacyFilteringSpanExporter(span_exporter))
        )
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                _PrivacyFilteringSpanExporter(
                    OTLPSpanExporter(endpoint=_traces_endpoint(settings))
                )
            )
        )
    tracer = tracer_provider.get_tracer(_INSTRUMENTATION_SCOPE, service_version)

    meter_provider = None
    if settings.otel_metrics_enabled or metric_reader is not None:
        from opentelemetry.sdk.metrics import MeterProvider as SdkMeterProvider

        reader = metric_reader or _otlp_metric_reader(settings)
        meter_provider = SdkMeterProvider(resource=resource, metric_readers=[reader])
        meter = meter_provider.get_meter(_INSTRUMENTATION_SCOPE, service_version)
    else:
        meter = metrics.get_meter(_INSTRUMENTATION_SCOPE, service_version)

    return tracer_provider, meter_provider, tracer, meter


def configure_api_telemetry(
    settings: Settings,
    *,
    span_exporter=None,
    metric_reader=None,
) -> TelemetryRuntime:
    """Bootstrap tracing/metrics for the API.

    ``span_exporter`` / ``metric_reader`` are injection points for tests (e.g. an
    in-memory span exporter); in production they are ``None`` and an OTLP/HTTP
    exporter is built from settings. Returns a no-op runtime when disabled.
    """

    if not settings.otel_enabled:
        return _noop_runtime()

    tracer_provider, meter_provider, tracer, meter = build_sdk_providers(
        settings,
        service_name=DEFAULT_SERVICE_NAME,
        service_version=SERVICE_VERSION,
        span_exporter=span_exporter,
        metric_reader=metric_reader,
    )
    return _build_runtime(
        enabled=True,
        tracer=tracer,
        meter=meter,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )


def instrument_fastapi_app(app, runtime: TelemetryRuntime) -> None:
    """Attach FastAPI/ASGI auto-instrumentation using the app-scoped providers."""

    if not runtime.enabled:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=runtime.tracer_provider,
        meter_provider=runtime.meter_provider,
    )


def _traces_endpoint(settings: Settings) -> str:
    return settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces"


def _metrics_endpoint(settings: Settings) -> str:
    return settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/metrics"


def _otlp_metric_reader(settings: Settings):
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    return PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=_metrics_endpoint(settings)),
    )


def observability_posture(settings: Settings) -> dict[str, object]:
    """Return the observability readiness posture surfaced by the readiness report."""

    return {
        "otel_enabled": settings.otel_enabled,
        "otel_metrics_enabled": settings.otel_enabled and settings.otel_metrics_enabled,
        "otel_exporter_endpoint_configured": bool(
            settings.otel_exporter_otlp_endpoint.strip()
        ),
        "otel_traces_endpoint": _traces_endpoint(settings) if settings.otel_enabled else None,
    }
