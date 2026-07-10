"""Worker OpenTelemetry bootstrap + activity instrumentation tests.

Uses in-memory exporters and a real in-memory SQLite session factory, so no live
Temporal or OTLP collector is required.
"""

from __future__ import annotations

import pytest
from axis_api.config import Settings
from axis_api.models import Base
from axis_api.telemetry import shutdown_providers
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import get_current_span
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_worker.maintenance_activities import MaintenanceActivities
from axis_worker.telemetry import configure_worker_telemetry


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


def _enabled_runtime() -> tuple[object, InMemorySpanExporter, InMemoryMetricReader]:
    exporter = InMemorySpanExporter()
    reader = InMemoryMetricReader()
    runtime = configure_worker_telemetry(
        Settings(otel_enabled=True),
        span_exporter=exporter,
        metric_reader=reader,
    )
    return runtime, exporter, reader


def test_configure_worker_telemetry_is_noop_when_disabled() -> None:
    runtime = configure_worker_telemetry(Settings())
    assert runtime.enabled is False
    assert runtime.tracer_provider is None
    assert runtime.meter_provider is None


def test_configure_worker_telemetry_builds_provider_when_enabled() -> None:
    runtime, _, _ = _enabled_runtime()
    assert runtime.enabled is True
    assert runtime.tracer_provider is not None


def test_shutdown_providers_is_safe_and_idempotent() -> None:
    # Mirrors run_worker's finally-block teardown of the app-scoped providers.
    runtime, _, _ = _enabled_runtime()
    with runtime.tracer.start_as_current_span("axis.test.flush"):
        pass
    shutdown_providers(runtime.tracer_provider, runtime.meter_provider)
    shutdown_providers(runtime.tracer_provider, runtime.meter_provider)


async def test_disabled_activity_emits_no_spans(session_factory) -> None:
    exporter = InMemorySpanExporter()
    runtime = configure_worker_telemetry(
        Settings(), span_exporter=exporter, metric_reader=InMemoryMetricReader()
    )
    activities = MaintenanceActivities(
        Settings(), session_factory=session_factory, telemetry=runtime
    )

    result = await activities.run_orphaned_session_sweep()

    assert result["job"] == "orphaned_session_sweep"
    assert exporter.get_finished_spans() == ()


async def test_enabled_activity_produces_span_and_metric(session_factory) -> None:
    runtime, exporter, reader = _enabled_runtime()
    activities = MaintenanceActivities(
        Settings(), session_factory=session_factory, telemetry=runtime
    )

    result = await activities.run_orphaned_session_sweep()
    assert result["job"] == "orphaned_session_sweep"

    spans = exporter.get_finished_spans()
    assert any(
        span.name == "axis.scheduled_job.orphaned_session_sweep" for span in spans
    )
    job_span = next(
        span for span in spans if span.name == "axis.scheduled_job.orphaned_session_sweep"
    )
    assert job_span.attributes.get("axis.job") == "orphaned_session_sweep"
    assert job_span.attributes.get("axis.outcome") == result["status"]

    metric_names = {
        metric.name
        for resource_metric in reader.get_metrics_data().resource_metrics
        for scope_metric in resource_metric.scope_metrics
        for metric in scope_metric.metrics
    }
    assert "axis.scheduled_job_runs" in metric_names


async def test_activity_span_links_to_propagated_context() -> None:
    runtime, exporter, _ = _enabled_runtime()

    # Simulate an originating trace (e.g. the API request that signalled a
    # workflow) and its propagated carrier.
    with runtime.tracer.start_as_current_span("axis.test.origin") as origin:
        from axis_api.telemetry import inject_trace_context

        carrier = inject_trace_context()
        origin_trace_id = origin.get_span_context().trace_id

    with runtime.activity_span("axis.test.child", carrier=carrier) as child:
        assert child.get_span_context().trace_id == origin_trace_id
        assert get_current_span().get_span_context().trace_id == origin_trace_id
