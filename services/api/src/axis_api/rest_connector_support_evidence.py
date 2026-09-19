"""Honest support evidence for the REST collection host, from existing durable records.

[#862](https://github.com/Limes-Labs/limes-axis/issues/862) needs one place that
says *exactly what was verified*, without inventing a second status store. This
module is a pure projection over records other owners already wrote: the source
binding checkpoint, the extraction batch rows and the ingestion request row. It
adds no tables, no counters and no background health checks.

Two vocabularies are kept separate on purpose:

* ``VerificationScope`` answers "what did this evidence actually exercise?"
  (contract-only, a local wire-level run, or a real provider). A local run never
  claims provider verification, and provider claims require a provider evidence
  reference.
* The SDK :class:`~axis_sdk.connector_authoring.health.HealthObservation` /
  :func:`project_health` answer "is the evidence fresh?" A past green run does
  not certify current availability: unknown evidence stays ``unknown`` and a
  success older than the caller's freshness budget is ``stale``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from axis_sdk.connector_authoring.health import (
    HealthBudgets,
    HealthObservation,
    OperationalError,
    OperationalHealth,
    project_health,
)
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from axis_api.persistence import AxisPersistenceRepository

REST_SUPPORT_ADAPTER = "axis-rest-collection-source"

# Public-safe reason codes. They describe evidence gaps, never source contents.
NO_COMMITTED_EVIDENCE = "no_committed_evidence"
LOCAL_ONLY_VERIFICATION = "local_only_verification"
PROVIDER_NOT_VERIFIED = "provider_not_verified"
LAST_REQUEST_DEAD_LETTERED = "last_request_dead_lettered"
RETRY_SCHEDULED = "retry_scheduled"
CHECKPOINT_INVALID = "checkpoint_invalid"

_TERMINAL_TRAVERSALS = frozenset({"complete", "page_limit_reached"})
_ERROR_CODES = {
    "rate_limited": OperationalError.THROTTLED,
    "source_unavailable": OperationalError.SOURCE_UNAVAILABLE,
    "invalid_checkpoint": OperationalError.INVALID_CHECKPOINT,
    "resource_mismatch": OperationalError.SCHEMA_DRIFT,
    "context_mismatch": OperationalError.SCHEMA_DRIFT,
    "time_budget_exceeded": OperationalError.PARTIAL_DATA,
}


class VerificationScope(StrEnum):
    """What an evidence record actually exercised."""

    CONTRACT_ONLY = "contract_only"
    LOCAL_WIRE_LEVEL = "local_wire_level"
    PROVIDER_VERIFIED = "provider_verified"


class RestSupportEvidence(BaseModel):
    """Public-safe projection of one binding's recorded host activity.

    Counts, digests, attempts and reason codes only: no rows, cursors,
    endpoints or credentials.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1, max_length=80)
    connector_id: str = Field(min_length=1, max_length=160)
    binding_id: str = Field(min_length=1, max_length=180)
    resource_name: str = Field(min_length=1, max_length=240)
    scope: VerificationScope
    provider_evidence_ref: str | None = Field(default=None, max_length=300)
    request_id: str | None = Field(default=None, max_length=180)
    request_status: str | None = Field(default=None, max_length=40)
    attempt_count: int = Field(default=0, ge=0)
    retry_state: Literal["idle", "scheduled", "in_progress", "exhausted"] = "idle"
    next_retry_at: AwareDatetime | None = None
    batch_count: int = Field(default=0, ge=0)
    record_count: int = Field(default=0, ge=0)
    byte_size: int = Field(default=0, ge=0)
    pages_committed: int = Field(default=0, ge=0)
    completion: str | None = Field(default=None, max_length=40)
    last_digest_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    checkpoint_state: Literal["unknown", "absent", "not_applicable", "committed", "invalid"] = (
        "unknown"
    )
    last_committed_at: AwareDatetime | None = None
    last_error: OperationalError | None = None
    last_error_at: AwareDatetime | None = None
    reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def honest_scope(self):
        if self.scope == VerificationScope.PROVIDER_VERIFIED and not self.provider_evidence_ref:
            raise ValueError("Provider verification requires a provider evidence reference")
        if self.scope == VerificationScope.CONTRACT_ONLY and self.batch_count:
            raise ValueError("Contract-only evidence cannot carry committed batches")
        return self

    @property
    def has_committed_evidence(self) -> bool:
        return self.batch_count > 0 and self.last_digest_sha256 is not None


def _aware(value: datetime | None) -> datetime | None:
    """SQLite yields naive datetimes; durable timestamps are UTC by contract."""

    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _retry_state(row) -> tuple[str, datetime | None]:
    if row is None:
        return "idle", None
    if row.status == "failed" and row.dead_lettered_at is not None:
        return "exhausted", None
    if row.status == "pending" and row.attempt_count > 0:
        return "scheduled", _aware(row.available_at)
    # In-flight retries only exist after an unresolved error; a fresh claim has
    # no error yet, so the SDK's coherent retry vocabulary forbids it.
    if row.status == "dispatching" and row.last_error:
        return "in_progress", None
    return "idle", None


def _checkpoint_state(binding) -> str:
    checkpoint = binding.source_checkpoint
    if not isinstance(checkpoint, dict):
        return "unknown"
    traversal = checkpoint.get("traversal")
    if traversal in _TERMINAL_TRAVERSALS:
        # A finished traversal has nothing left to time out; freshness of the
        # last success still decides health.
        return "not_applicable"
    cursor = checkpoint.get("cursor")
    if traversal == "in_progress" and isinstance(cursor, dict):
        return "committed"
    if traversal == "in_progress":
        return "invalid"
    return "absent"


def build_rest_support_evidence(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    connector_id: str,
    binding_id: str,
    request_id: str | None,
    scope: VerificationScope,
    provider_evidence_ref: str | None = None,
) -> RestSupportEvidence:
    """Project the recorded evidence; never contacts the source."""

    binding = repository.get_connector_source_binding(tenant_id, binding_id)
    if binding is None or binding.connector_id != connector_id:
        raise LookupError("Unknown source binding for this tenant and connector")
    row = (
        repository.get_connector_source_ingestion_request(tenant_id, request_id)
        if request_id is not None
        else None
    )
    batches = (
        repository.get_connector_source_ingestion_request_batches(
            tenant_id, request_id, limit=100, binding_id=binding_id
        )
        if row is not None
        else []
    )
    retry_state, next_retry_at = _retry_state(row)
    last_batch = batches[-1] if batches else None
    checkpoint = binding.source_checkpoint if isinstance(binding.source_checkpoint, dict) else {}
    pages = int(checkpoint.get("pages_committed") or 0)
    for batch in batches:
        watermark = batch.cursor_watermark or {}
        pages = max(pages, int(watermark.get("page_number") or 0))
    last_error = _ERROR_CODES.get((row.last_error or "").split("+")[0]) if row else None
    reasons: list[str] = []
    if not batches:
        reasons.append(NO_COMMITTED_EVIDENCE)
    if scope == VerificationScope.LOCAL_WIRE_LEVEL:
        reasons.append(LOCAL_ONLY_VERIFICATION)
    if scope != VerificationScope.PROVIDER_VERIFIED:
        reasons.append(PROVIDER_NOT_VERIFIED)
    if row is not None and row.status == "failed":
        reasons.append(LAST_REQUEST_DEAD_LETTERED)
    if retry_state == "scheduled":
        reasons.append(RETRY_SCHEDULED)
    if _checkpoint_state(binding) == "invalid":
        reasons.append(CHECKPOINT_INVALID)
    return RestSupportEvidence(
        tenant_id=tenant_id,
        connector_id=connector_id,
        binding_id=binding_id,
        resource_name=binding.resource_name,
        scope=scope,
        provider_evidence_ref=provider_evidence_ref,
        request_id=request_id,
        request_status=row.status if row is not None else None,
        attempt_count=row.attempt_count if row is not None else 0,
        retry_state=retry_state,
        next_retry_at=next_retry_at if retry_state == "scheduled" else None,
        batch_count=len(batches),
        record_count=sum(batch.row_count for batch in batches),
        byte_size=sum(batch.byte_size for batch in batches),
        pages_committed=pages,
        completion=(last_batch.provenance or {}).get("traversal") if last_batch else None,
        last_digest_sha256=last_batch.digest_sha256 if last_batch else None,
        checkpoint_state=_checkpoint_state(binding),
        last_committed_at=_aware(last_batch.created_at) if last_batch else None,
        last_error=last_error,
        last_error_at=(_aware(row.last_attempt_at) if row is not None else None),
        reasons=tuple(reasons),
    )


def rest_health_observation(
    evidence: RestSupportEvidence,
    *,
    observed_at: datetime,
    source_head_at: datetime | None = None,
    source_watermark_at: datetime | None = None,
) -> HealthObservation:
    """Turn recorded evidence into the SDK health vocabulary.

    Unknown evidence stays unknown: a binding that was never dispatched has no
    freshness, no checkpoint and no success to certify.

    ``source_head_at`` / ``source_watermark_at`` are caller-supplied live-probe
    values. A cursor pull cannot read a source head from its own records, so
    they are never fabricated here: without them the SDK reports ``lag_unknown``
    instead of inventing a snapshot position.
    """

    last_success = evidence.last_committed_at if evidence.has_committed_evidence else None
    checkpoint_state = evidence.checkpoint_state if evidence.has_committed_evidence else "unknown"
    return HealthObservation(
        tenant_id=evidence.tenant_id,
        connector_id=evidence.connector_id,
        resource_id=evidence.resource_name,
        observed_at=observed_at,
        last_success_at=last_success,
        source_head_at=source_head_at,
        source_watermark_at=source_watermark_at,
        checkpoint_state=checkpoint_state,
        checkpoint_committed_at=last_success if checkpoint_state == "committed" else None,
        last_error=evidence.last_error,
        last_error_at=evidence.last_error_at if evidence.last_error else None,
        retry_state=evidence.retry_state,
        attempt_count=evidence.attempt_count,
        next_retry_at=evidence.next_retry_at,
    )


def project_rest_health(
    evidence: RestSupportEvidence,
    *,
    observed_at: datetime,
    budgets: HealthBudgets,
    source_head_at: datetime | None = None,
    source_watermark_at: datetime | None = None,
) -> OperationalHealth:
    """Project health at the caller's observation time, never at evidence time."""

    return project_health(
        rest_health_observation(
            evidence,
            observed_at=observed_at,
            source_head_at=source_head_at,
            source_watermark_at=source_watermark_at,
        ),
        budgets,
    )
