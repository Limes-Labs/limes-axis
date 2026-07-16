"""Per-tenant usage metering: the cumulative consumption ledger beneath billing.

Quotas (see ``platform_tenants``) are instantaneous ceilings; metering is the
cumulative accounting layer. This module owns:

* the typed metric keys that map to the existing enforcement choke points,
* the epoch-aligned period bucketing used to aggregate consumption,
* a bounded in-process aggregator (:class:`UsageAccumulator`) that batches
  hot-path ``api_request`` counts and periodically flushes them to per-period
  ledger rows through source-keyed journal events, and
* the read model + aggregation used by the operator-scoped usage read route.

Low-volume domain events append synchronously in their source transaction.
Request-volume counts remain in memory until flush, but every drained batch has
a stable source identity: retrying an ambiguous commit is exactly-once. A hard
process crash before the batch is assigned and flushed remains a documented
best-effort boundary for ``api_request`` accounting.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from axis_api.db import session_scope
from axis_api.models import utc_now
from axis_api.persistence import (
    AxisPersistenceRepository,
    TenantUsageEventAppend,
    TenantUsagePeriodTotal,
)

# A dedicated read scope keeps billing-adjacent consumption reads separable from
# the general tenant read surface while still gated by the operator scope.
REQUIRED_USAGE_READ_SCOPE = "platform:tenant:usage"

DEFAULT_USAGE_PERIOD_WINDOW_SECONDS = 86_400

# Soft bound on distinct (tenant, metric, period) keys held between flushes. In
# practice the key space is tiny (tenants x 3 metrics x a couple of periods) and
# the aggregator is drained every few seconds, so this only guards against a
# pathological unbounded-growth scenario.
_MAX_PENDING_KEYS = 200_000


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


class UsageRecordResult(StrEnum):
    ACCEPTED = "accepted"
    DISABLED = "disabled"
    IGNORED = "ignored"
    OVERFLOW = "overflow"


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


@dataclass
class _PendingCounter:
    quantity: int
    last_occurred_at: datetime


@dataclass
class PendingUsage:
    source_id: str
    tenant_id: str
    metric_key: str
    period_start: datetime
    quantity: int
    occurred_at: datetime


@dataclass
class UsageAccumulator:
    """Bounded, thread-safe in-process aggregator for hot-path usage counts.

    ``record`` folds a delta into an in-memory per-bucket counter under a lock.
    ``flush`` assigns a source identity to each drained batch and appends it to
    the journal before updating the rollup in the same transaction. Failed
    batches retain their identities across retry and remain separate from new
    traffic, preventing ambiguous commits from double-counting either batch.
    """

    window_seconds: int = DEFAULT_USAGE_PERIOD_WINDOW_SECONDS
    enabled: bool = True
    max_pending_keys: int = _MAX_PENDING_KEYS
    _pending: dict[tuple[str, str, datetime], _PendingCounter] = field(
        default_factory=dict
    )
    _retry_pending: list[PendingUsage] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _overflow_total: int = 0
    _degraded: bool = False

    def record(
        self,
        tenant_id: str | None,
        metric: str,
        quantity: int = 1,
        *,
        occurred_at: datetime | None = None,
    ) -> UsageRecordResult:
        if not self.enabled:
            return UsageRecordResult.DISABLED
        if not tenant_id or quantity <= 0:
            return UsageRecordResult.IGNORED
        moment = occurred_at or utc_now()
        period_start = usage_period_start(moment, self.window_seconds)
        key = (tenant_id, metric, period_start)
        with self._lock:
            counter = self._pending.get(key)
            if counter is None:
                if len(self._pending) + len(self._retry_pending) >= self.max_pending_keys:
                    self._overflow_total += quantity
                    self._degraded = True
                    return UsageRecordResult.OVERFLOW
                counter = _PendingCounter(quantity=0, last_occurred_at=moment)
                self._pending[key] = counter
            counter.quantity += quantity
            if moment > counter.last_occurred_at:
                counter.last_occurred_at = moment
        return UsageRecordResult.ACCEPTED

    def health(self) -> dict[str, int | bool]:
        """Expose bounded, non-tenant operational state for diagnostics."""

        with self._lock:
            return {
                "healthy": not self._degraded,
                "pending_keys": len(self._pending) + len(self._retry_pending),
                "max_pending_keys": self.max_pending_keys,
                "overflow_total": self._overflow_total,
            }

    def mark_flush_succeeded(self) -> None:
        """Clear active backpressure degradation while retaining loss telemetry."""

        with self._lock:
            if len(self._pending) + len(self._retry_pending) < self.max_pending_keys:
                self._degraded = False

    def drain(self) -> list[PendingUsage]:
        with self._lock:
            drained = [
                PendingUsage(
                    source_id=str(uuid4()),
                    tenant_id=tenant_id,
                    metric_key=metric_key,
                    period_start=period_start,
                    quantity=counter.quantity,
                    occurred_at=counter.last_occurred_at,
                )
                for (tenant_id, metric_key, period_start), counter in self._pending.items()
            ]
            drained = [*self._retry_pending, *drained]
            self._retry_pending.clear()
            self._pending.clear()
        return drained

    def restore(self, items: list[PendingUsage]) -> None:
        with self._lock:
            self._retry_pending = [*items, *self._retry_pending]

    def flush(self, session_factory: sessionmaker[Session]) -> int:
        """Drain pending buckets and durably upsert-add them to the ledger.

        Returns the total quantity flushed. On a DB error the drained deltas are
        restored and the error is re-raised so the caller can observe the
        failure; the next flush retries them.
        """
        items = self.drain()
        if not items:
            return 0
        flushed_quantity = 0
        try:
            with session_scope(session_factory) as session:
                repository = AxisPersistenceRepository(session)
                for item in items:
                    inserted = repository.append_tenant_usage_event(
                        TenantUsageEventAppend(
                            source_type="api_request_batch",
                            source_id=item.source_id,
                            tenant_id=item.tenant_id,
                            metric_key=item.metric_key,
                            period_start=item.period_start,
                            period_window_seconds=self.window_seconds,
                            quantity=item.quantity,
                            occurred_at=item.occurred_at,
                        )
                    )
                    if inserted:
                        flushed_quantity += item.quantity
        except Exception:
            # Any flush failure (a wrapped or unwrapped driver/pool error, or a
            # failure constructing the session) must not drop the drained deltas:
            # restore them so the next flush retries with no loss, then re-raise.
            self.restore(items)
            raise
        self.mark_flush_succeeded()
        return flushed_quantity


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
    "Hot-path API counts are buffered in process before periodic durable flushes; "
    "this accounting path is not a billing-grade event transport.",
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
