"""Per-tenant usage metering: the cumulative consumption ledger beneath billing.

Quotas (see ``platform_tenants``) are instantaneous ceilings; metering is the
cumulative accounting layer. This module owns:

* the typed metric keys that map to the existing enforcement choke points,
* the epoch-aligned period bucketing used to aggregate consumption,
* durable request-admission journaling before application handlers execute,
* asynchronous, transactionally claimed projection into period rollups, and
* the read model + aggregation used by the operator-scoped usage read route.

Low-volume domain events append synchronously in their source transaction.
Authenticated request admissions append one event before handler execution and
never contend on the hot rollup row. Projectors running on every API replica
claim disjoint batches and update rollups atomically.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.models import utc_now
from axis_api.persistence import (
    AxisPersistenceRepository,
    TenantUsageEventAppend,
    TenantUsageIdempotencyConflict,
    TenantUsagePeriodTotal,
    TenantUsageProjectionResult,
)

# A dedicated read scope keeps billing-adjacent consumption reads separable from
# the general tenant read surface while still gated by the operator scope.
REQUIRED_USAGE_READ_SCOPE = "platform:tenant:usage"

DEFAULT_USAGE_PERIOD_WINDOW_SECONDS = 86_400

_METERING_EXCLUDED_PATHS = {
    "/health",
    "/ready",
    "/identity/oidc/readiness",
    "/identity/oidc/authorize",
    "/identity/oidc/callback",
    "/identity/session/logout",
    "/identity/session/refresh",
}


class TenantUsageMetric(StrEnum):
    """Consumption metrics, each mapping to an existing enforcement choke point.

    The enum is intentionally extensible: new metered surfaces add a member here
    without a schema change (``metric_key`` is a free-form column).
    """

    API_REQUEST = "api_request"
    CONNECTOR_SYNC_ROWS = "connector_sync_rows"
    SESSION_CREATED = "session_created"
    MODEL_INVOCATIONS = "model_invocations"
    MODEL_INPUT_TOKENS = "model_input_tokens"
    MODEL_OUTPUT_TOKENS = "model_output_tokens"
    AGENT_RUNS = "agent_runs"


def usage_period_start(
    occurred_at: datetime,
    window_seconds: int = DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
) -> datetime:
    """Floor ``occurred_at`` to the left edge of its epoch-aligned period bucket.

    A ``window_seconds`` of 86400 yields UTC-midnight day buckets; smaller
    windows yield finer buckets aligned to the Unix epoch. Naive datetimes are
    treated as UTC so callers never silently bucket local time.
    """
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    else:
        occurred_at = occurred_at.astimezone(UTC)
    window = max(1, window_seconds)
    epoch_seconds = int(occurred_at.timestamp())
    floored = epoch_seconds - (epoch_seconds % window)
    return datetime.fromtimestamp(floored, tz=UTC)


class UsageAdmissionUnavailable(RuntimeError):
    pass


@dataclass
class RequestUsageAdmissionRecorder:
    """Persist authenticated request admission before application execution."""

    enabled: bool
    window_seconds: int
    statement_timeout_ms: int
    id_factory: Callable[[], UUID] = uuid4

    def record(self, request: Request, principal: OidcPrincipal) -> bool:
        if (
            not self.enabled
            or request.method == "OPTIONS"
            or request.url.path in _METERING_EXCLUDED_PATHS
            or not bool(getattr(request.state, "axis_rate_limit_admitted", False))
        ):
            return False
        if bool(getattr(request.state, "axis_usage_admission_recorded", False)):
            return False
        session_factory: sessionmaker[Session] = request.app.state.session_factory

        event = getattr(request.state, "axis_usage_admission_event", None)
        if not isinstance(event, TenantUsageEventAppend):
            occurred_at = utc_now()
            route = request.scope.get("route")
            route_template = getattr(route, "path", "unmatched")
            event = TenantUsageEventAppend(
                tenant_id=principal.tenant_id,
                metric_key=TenantUsageMetric.API_REQUEST.value,
                source_type="api_request_admission",
                source_id=str(self.id_factory()),
                period_start=usage_period_start(occurred_at, self.window_seconds),
                period_window_seconds=self.window_seconds,
                quantity=1,
                occurred_at=occurred_at,
                dimensions={
                    "method": request.method,
                    "route": route_template,
                    "session_source": principal.session_source,
                },
            )
            request.state.axis_usage_admission_event = event

        try:
            with session_scope(session_factory) as session:
                if session.get_bind().dialect.name == "postgresql":
                    timeout = f"{self.statement_timeout_ms}ms"
                    session.execute(
                        text(
                            "SELECT "
                            "set_config('statement_timeout', :timeout, true), "
                            "set_config('lock_timeout', :timeout, true)"
                        ),
                        {"timeout": timeout},
                    )
                AxisPersistenceRepository(session).append_tenant_usage_event(
                    event,
                    project_immediately=False,
                )
            request.state.axis_usage_admission_recorded = True
            return True
        except TenantUsageIdempotencyConflict:
            raise
        except Exception as exc:  # noqa: BLE001 - reconcile ambiguous commits
            if self._event_exists_with_same_payload(session_factory, event):
                request.state.axis_usage_admission_recorded = True
                return True
            raise UsageAdmissionUnavailable(
                "Request usage admission could not be persisted."
            ) from exc

    def _event_exists_with_same_payload(
        self,
        session_factory: sessionmaker[Session],
        event: TenantUsageEventAppend,
    ) -> bool:
        try:
            with session_factory() as session:
                existing = AxisPersistenceRepository(
                    session
                ).get_tenant_usage_event_by_source(
                    event.tenant_id,
                    event.metric_key,
                    event.source_type,
                    event.source_id,
                )
                if existing is None:
                    return False
                return (
                    existing.quantity == event.quantity
                    and _aware(existing.period_start) == _aware(event.period_start)
                    and existing.period_window_seconds == event.period_window_seconds
                    and _aware(existing.occurred_at) == _aware(event.occurred_at)
                    and existing.dimensions == event.dimensions
                )
        except Exception:  # noqa: BLE001 - reconciliation is best-effort
            return False


@dataclass
class UsageEventProjector:
    """Project pending journal events while exposing non-tenant health state."""

    failure_threshold: int
    max_backlog_age_seconds: float
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _initialized: bool = False
    _consecutive_failures: int = 0
    _oldest_pending_at: datetime | None = None
    _last_success_at: datetime | None = None

    def project_available(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int,
        max_batches: int,
    ) -> TenantUsageProjectionResult:
        events_projected = 0
        quantity_projected = 0
        try:
            for _ in range(max_batches):
                with session_scope(session_factory) as session:
                    result = AxisPersistenceRepository(
                        session
                    ).project_pending_tenant_usage_events(batch_size=batch_size)
                events_projected += result.events_projected
                quantity_projected += result.quantity_projected
                if result.events_projected < batch_size:
                    break
            with session_factory() as session:
                oldest_pending_at = AxisPersistenceRepository(
                    session
                ).oldest_pending_tenant_usage_event_at()
        except Exception:
            with self._lock:
                self._initialized = True
                self._consecutive_failures += 1
            raise
        with self._lock:
            self._initialized = True
            self._consecutive_failures = 0
            self._oldest_pending_at = oldest_pending_at
            self._last_success_at = utc_now()
        return TenantUsageProjectionResult(
            events_projected=events_projected,
            quantity_projected=quantity_projected,
        )

    def health(self) -> dict[str, bool | int | float | None]:
        with self._lock:
            oldest = self._oldest_pending_at
            backlog_age_seconds = (
                max(0.0, (utc_now() - _aware(oldest)).total_seconds())
                if oldest is not None
                else 0.0
            )
            heartbeat_age_seconds = (
                max(0.0, (utc_now() - _aware(self._last_success_at)).total_seconds())
                if self._last_success_at is not None
                else None
            )
            healthy = (
                self._initialized
                and self._consecutive_failures < self.failure_threshold
                and backlog_age_seconds <= self.max_backlog_age_seconds
                and heartbeat_age_seconds is not None
                and heartbeat_age_seconds <= self.max_backlog_age_seconds
            )
            return {
                "healthy": healthy,
                "initialized": self._initialized,
                "consecutive_failures": self._consecutive_failures,
                "backlog_age_seconds": backlog_age_seconds,
                "heartbeat_age_seconds": heartbeat_age_seconds,
                "last_success_at": (
                    self._last_success_at.timestamp()
                    if self._last_success_at is not None
                    else None
                ),
            }

    def retry_delay_seconds(self, base_interval_seconds: float) -> float:
        with self._lock:
            failures = self._consecutive_failures
        return min(30.0, base_interval_seconds * (2 ** min(failures, 5)))


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def record_tenant_usage_event(
    repository: AxisPersistenceRepository,
    tenant_id: str | None,
    metric: str,
    quantity: int,
    *,
    source_type: str,
    source_id: str,
    window_seconds: int = DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
    occurred_at: datetime | None = None,
    dimensions: dict | None = None,
) -> bool:
    """Durably append and aggregate a low-volume source event exactly once.

    Used by the connector-sync-rows and session-created choke points, which
    already hold a repository/transaction and are low enough volume that a direct
    per-event upsert is cheap and worth the immediate durability. A missing
    tenant or non-positive quantity is a no-op, so there is no behavior change
    without tenant context.
    """
    if not tenant_id or quantity <= 0:
        return False
    moment = occurred_at or utc_now()
    return repository.append_tenant_usage_event(
        TenantUsageEventAppend(
            tenant_id=tenant_id,
            metric_key=metric,
            source_type=source_type,
            source_id=source_id,
            period_start=usage_period_start(moment, window_seconds),
            period_window_seconds=window_seconds,
            quantity=quantity,
            occurred_at=moment,
            dimensions=dimensions or {},
        )
    )


class TenantUsageMetricTotal(BaseModel):
    metric_key: str = Field(min_length=1)
    quantity: int = Field(ge=0)


class TenantUsagePeriodPoint(BaseModel):
    period_start: datetime
    metric_key: str = Field(min_length=1)
    quantity: int = Field(ge=0)


class TenantUsageSummary(BaseModel):
    tenant_id: str = Field(min_length=1)
    window_start: datetime
    window_end: datetime
    period_window_seconds: int = Field(ge=1)
    metric_totals: list[TenantUsageMetricTotal] = Field(default_factory=list)
    periods: list[TenantUsagePeriodPoint] = Field(default_factory=list)
    usage_notes: list[str] = Field(default_factory=list)


_USAGE_NOTES = [
    "Usage metering is cumulative consumption accounting, not an instantaneous "
    "ceiling; quotas remain the enforcement layer.",
    "api_request counts authenticated tenant-resolved application requests; "
    "connector_sync_rows counts rows read by governed live-sync runs; "
    "session_created counts OIDC browser sessions established.",
    "Totals aggregate over epoch-aligned period buckets; the breakdown lists one "
    "point per metric and period in the window.",
    "Metering is per-tenant and isolated; billing is a future consumer of this "
    "ledger.",
    "api_request events are committed before handler execution and projected "
    "asynchronously into the period rollup.",
]


def build_tenant_usage_summary(
    repository: AxisPersistenceRepository,
    tenant_id: str,
    *,
    window_start: datetime,
    window_end: datetime,
    window_seconds: int = DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
) -> TenantUsageSummary:
    """Aggregate consumption for a tenant over ``[window_start, window_end)``.

    The lower bound is floored to its period bucket so a partial leading bucket
    is included whole; ``window_end`` is an exclusive upper bound. Raises
    ``TenantNotFound`` when the tenant is absent, mirroring the quota reader.
    """
    from axis_api.platform_tenants import TenantNotFound

    if repository.get_tenant(tenant_id) is None:
        raise TenantNotFound()

    period_from = usage_period_start(window_start, window_seconds)
    totals: list[TenantUsagePeriodTotal] = repository.aggregate_tenant_usage(
        tenant_id,
        period_window_seconds=window_seconds,
        period_start_from=period_from,
        period_start_to=window_end,
    )

    metric_totals: dict[str, int] = {}
    periods: list[TenantUsagePeriodPoint] = []
    for total in totals:
        metric_totals[total.metric_key] = (
            metric_totals.get(total.metric_key, 0) + total.quantity
        )
        periods.append(
            TenantUsagePeriodPoint(
                period_start=total.period_start,
                metric_key=total.metric_key,
                quantity=total.quantity,
            )
        )

    return TenantUsageSummary(
        tenant_id=tenant_id,
        window_start=period_from,
        window_end=window_end,
        period_window_seconds=window_seconds,
        metric_totals=[
            TenantUsageMetricTotal(metric_key=metric_key, quantity=quantity)
            for metric_key, quantity in sorted(metric_totals.items())
        ],
        periods=periods,
        usage_notes=list(_USAGE_NOTES),
    )
