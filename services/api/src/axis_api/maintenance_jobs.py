"""Reusable business logic for scheduled/periodic maintenance jobs.

These functions are the single source of truth for the maintenance work that the
Temporal worker runs on a schedule (see ``services/worker``). They own their DB
transaction boundaries: each takes a SQLAlchemy ``sessionmaker`` and opens its own
sessions so they can be:

* driven by the worker against a real Postgres factory in production, and
* unit-tested directly against an in-memory SQLite factory with no live
  Temporal or worker process.

The functions reuse existing persistence primitives and services rather than
duplicating business logic:

* :func:`axis_api.audit_queries.execute_audit_retention_deletion` performs the
  audit retention sweep, exactly like the ``/demo/manufacturing/audit/retention``
  endpoint;
* the ``refreshing``/expired session sweep reuses the same revoke path
  (:meth:`AxisPersistenceRepository.revoke_oidc_browser_session`) and the same
  ``identity.oidc_session.revoked`` audit event the request path emits;
* the tenant-state reconciliation reuses the tenant/quota persistence readers and
  the documented lifecycle/quota enums.

Every job is tenant-scoped where applicable, idempotent (safe to re-run: a second
pass finds nothing left to do), audited (a job-run evidence event is appended with
counts and no sensitive payloads) and observable (a structured result carries
items scanned/affected and a duration).

Jobs fail closed and are partial-failure safe for DB-class errors: each unit of
work commits in its own transaction, so a later poisoned item can never discard
earlier successes, and the job-run summary evidence is always written in a fresh
transaction. A per-item failure is recorded in ``errors`` and surfaced via
``status="partial_failure"`` instead of being silently swallowed.

Trust boundary: the scheduled actor ``axis-scheduled-jobs`` is a trusted
in-process runner. It self-asserts the retention-deletion scope, which makes the
permission check a no-op for the scheduled path. This is not privilege escalation
- the jobs run inside the trusted worker with direct DB access - but it is called
out explicitly here and in ``docs/platform-scheduled-jobs.md``.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from axis_api.audit import AuditEventCreate
from axis_api.audit_queries import (
    RETENTION_DELETION_REQUIRED_SCOPE,
    AuditRetentionDeletionRequest,
    AuditRetentionDeletionResult,
    execute_audit_retention_deletion,
)
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.models import OidcBrowserSession
from axis_api.persistence import (
    AxisPersistenceRepository,
    OidcBrowserSessionRevocation,
)
from axis_api.platform_tenants import (
    TenantLifecycleStatus,
    TenantQuotaKey,
    blocked_tenant_reason,
)

# Actor and audit-event identifiers for scheduled maintenance evidence.
SCHEDULED_JOBS_ACTOR = "axis-scheduled-jobs"
SESSION_LIFECYCLE_ACTOR = "axis-session-lifecycle"

AUDIT_RETENTION_JOB_EVENT_TYPE = "platform.scheduled_job.audit_retention.completed"
SESSION_SWEEP_JOB_EVENT_TYPE = "platform.scheduled_job.session_sweep.completed"
TENANT_RECONCILIATION_JOB_EVENT_TYPE = "platform.scheduled_job.tenant_reconciliation.completed"

SESSION_SWEEP_ORPHANED_REASON = "refresh_claim_orphaned_sweep"
SESSION_SWEEP_EXPIRED_REASON = "session_expired_sweep"
SESSION_SWEEP_BLOCKED_TENANT_REASON = "tenant_state_reconciliation_sweep"

OIDC_SESSION_REVOKED_EVENT_TYPE = "identity.oidc_session.revoked"
OIDC_SESSION_BOUNDARY = "http_only_cookie_verified_by_axis_api"

# Cap on how many tenants a single job run will page through, purely as a
# runaway guard. It is set high enough that reaching it signals an unusual scale;
# when hit the job emits a WARNING-grade audit marker so the truncation is never
# silent (see _iter_all_tenants).
MAX_TENANTS_PER_RUN = 100_000
_TENANT_PAGE_SIZE = 500

_VALID_TENANT_STATUSES = frozenset(status.value for status in TenantLifecycleStatus)
_VALID_QUOTA_KEYS = frozenset(key.value for key in TenantQuotaKey)


class JobRunResult(BaseModel):
    """Structured, observable outcome of a scheduled maintenance job run."""

    job: str = Field(min_length=1)
    status: str = Field(min_length=1)
    tenants_scanned: int = Field(default=0, ge=0)
    items_scanned: int = Field(default=0, ge=0)
    items_affected: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    audit_event_ids: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))


def _sweep_status(errors: list[str]) -> str:
    return "partial_failure" if errors else "completed"


def _iter_all_tenant_ids(factory: sessionmaker[Session]) -> tuple[list[str], bool]:
    """Page through every tenant id (keyset on the ``id`` primary key).

    ``list_tenants`` is limit-bounded; a single call silently truncates beyond its
    limit. To avoid a silent scaling cliff this pages through all tenants in a
    read-only session. Returns ``(tenant_ids, cap_reached)`` where ``cap_reached``
    is true only if the runaway guard ``MAX_TENANTS_PER_RUN`` was hit, so callers
    can surface it rather than truncate silently.
    """
    tenant_ids: list[str] = []
    cap_reached = False
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        cursor: str | None = None
        while True:
            page = repository.list_tenants_after(cursor, limit=_TENANT_PAGE_SIZE)
            if not page:
                break
            for tenant in page:
                tenant_ids.append(tenant.id)
                if len(tenant_ids) >= MAX_TENANTS_PER_RUN:
                    cap_reached = True
                    break
            if cap_reached or len(page) < _TENANT_PAGE_SIZE:
                break
            cursor = page[-1].id
    return tenant_ids, cap_reached


def _iter_batches(items: list, size: int) -> Iterator[list]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _append_summary_event(
    factory: sessionmaker[Session],
    *,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> str:
    """Append a job-run summary event in a FRESH, isolated transaction.

    Written on its own session so a poisoned working transaction (a per-item DB
    error that marked its session rollback-only) can never prevent the summary
    evidence from being recorded.
    """
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        event = repository.append_audit_event(
            AuditEventCreate(
                tenant_id=tenant_id,
                actor_id=SCHEDULED_JOBS_ACTOR,
                event_type=event_type,
                payload=payload,
            )
        )
        return str(event.id)


def _revoke_session_via_sweep(
    repository: AxisPersistenceRepository,
    session: OidcBrowserSession,
    *,
    revocation_reason: str,
) -> None:
    """Revoke one session, reusing the request-path audit + revoke primitives.

    Emits the same ``identity.oidc_session.revoked`` audit event the interactive
    request path records, then drives the shared revoke persistence method (which
    also drops the at-rest refresh credential).
    """
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=session.tenant_id,
            actor_id=session.actor_id,
            event_type=OIDC_SESSION_REVOKED_EVENT_TYPE,
            payload={
                "session_id_hash": session.session_id_hash,
                "revocation_reason": revocation_reason,
                "session_boundary": OIDC_SESSION_BOUNDARY,
                "federated_logout": False,
                "swept_by": SCHEDULED_JOBS_ACTOR,
            },
        )
    )
    repository.revoke_oidc_browser_session(
        OidcBrowserSessionRevocation(
            session_id_hash=session.session_id_hash,
            revoked_by=SESSION_LIFECYCLE_ACTOR,
            revocation_reason=revocation_reason,
            revoke_audit_event_id=audit_event.id,
        )
    )


def run_audit_retention_deletion_job(
    factory: sessionmaker[Session],
    *,
    settings: Settings,
    tenant_ids: list[str] | None = None,
) -> JobRunResult:
    """Sweep audit retention deletion across tenants on a schedule.

    Reuses :func:`execute_audit_retention_deletion` per tenant with the scheduled
    actor holding the retention-deletion scope. Legal holds and dry-run behavior
    are honored by the reused function. Each tenant is processed in its own
    transaction, so one tenant's failure never rolls back another's deletion.
    Idempotent: once eligible rows are deleted, the next run finds no further
    candidates.
    """
    started_at = time.monotonic()
    cap_reached = False
    if tenant_ids is None:
        tenant_ids, cap_reached = _iter_all_tenant_ids(factory)

    retention_days = settings.scheduled_audit_retention_days
    dry_run = settings.scheduled_audit_retention_dry_run
    per_tenant: dict[str, dict] = {}
    audit_event_ids: list[str] = []
    errors: list[str] = []
    tenants_scanned = 0
    total_candidates = 0
    total_deleted = 0

    for tenant_id in tenant_ids:
        tenants_scanned += 1
        try:
            with session_scope(factory) as session:
                repository = AxisPersistenceRepository(session)
                result: AuditRetentionDeletionResult = execute_audit_retention_deletion(
                    repository,
                    AuditRetentionDeletionRequest(
                        tenant_id=tenant_id,
                        actor_id=SCHEDULED_JOBS_ACTOR,
                        actor_scopes=[RETENTION_DELETION_REQUIRED_SCOPE],
                        retention_days=retention_days,
                        dry_run=dry_run,
                        limit=settings.scheduled_audit_retention_batch_limit,
                        reason="scheduled-audit-retention-deletion",
                    ),
                )
        except Exception as exc:  # noqa: BLE001 - fail closed, record and continue
            errors.append(f"{tenant_id}:{exc.__class__.__name__}")
            per_tenant[tenant_id] = {"status": "error", "error": exc.__class__.__name__}
            continue
        total_candidates += result.candidate_count
        total_deleted += result.deleted_count
        if result.audit_event_id is not None:
            audit_event_ids.append(str(result.audit_event_id))
        per_tenant[tenant_id] = {
            "status": result.status,
            "candidate_count": result.candidate_count,
            "deleted_count": result.deleted_count,
        }

    if cap_reached:
        errors.append(f"jobs_tenant_cap_reached:{tenants_scanned}")

    audit_event_ids.append(
        _append_summary_event(
            factory,
            tenant_id="platform",
            event_type=AUDIT_RETENTION_JOB_EVENT_TYPE,
            payload={
                "category": "scheduled_job",
                "job": "audit_retention_deletion",
                "status": _sweep_status(errors),
                "retention_days": retention_days,
                "dry_run": dry_run,
                "tenants_scanned": tenants_scanned,
                "candidate_count": total_candidates,
                "deleted_count": total_deleted,
                "error_count": len(errors),
                "tenant_cap_reached": cap_reached,
                "raw_payload_exported": False,
            },
        )
    )

    return JobRunResult(
        job="audit_retention_deletion",
        status=_sweep_status(errors),
        tenants_scanned=tenants_scanned,
        items_scanned=total_candidates,
        items_affected=total_deleted,
        duration_ms=_elapsed_ms(started_at),
        audit_event_ids=audit_event_ids,
        details={
            "dry_run": dry_run,
            "retention_days": retention_days,
            "tenant_cap_reached": cap_reached,
            "tenants": per_tenant,
        },
        errors=errors,
    )


def _sweep_session_batch(
    factory: sessionmaker[Session],
    session_ids: list,
    *,
    revocation_reason: str,
    error_prefix: str,
    errors: list[str],
) -> int:
    """Revoke a batch of sessions by id in one transaction; count successes.

    On a batch-level DB error the batch is retried one session per transaction so
    a single poisoned row cannot discard the rest of the batch and successes still
    commit. Returns the number of sessions actually revoked.
    """
    revoked = 0
    try:
        with session_scope(factory) as session:
            repository = AxisPersistenceRepository(session)
            batch_revoked = 0
            for session_row_id in session_ids:
                row = _load_active_or_refreshing_session(repository, session_row_id)
                if row is None:
                    continue
                _revoke_session_via_sweep(repository, row, revocation_reason=revocation_reason)
                batch_revoked += 1
            revoked += batch_revoked
    except Exception:  # noqa: BLE001 - fall back to per-row commits, fail closed
        revoked = 0
        for session_row_id in session_ids:
            try:
                with session_scope(factory) as session:
                    repository = AxisPersistenceRepository(session)
                    row = _load_active_or_refreshing_session(repository, session_row_id)
                    if row is None:
                        continue
                    _revoke_session_via_sweep(
                        repository, row, revocation_reason=revocation_reason
                    )
                    revoked += 1
            except Exception as exc:  # noqa: BLE001 - record and continue
                errors.append(f"{error_prefix}:{session_row_id}:{exc.__class__.__name__}")
    return revoked


def _load_active_or_refreshing_session(
    repository: AxisPersistenceRepository,
    session_row_id,
) -> OidcBrowserSession | None:
    """Reload a session row and skip it if it is no longer sweepable.

    Guards idempotency and concurrency: a row already revoked/rotated between the
    candidate scan and the commit is skipped rather than re-revoked.
    """
    row = repository.get_oidc_browser_session_by_row_id(session_row_id)
    if row is None or row.status not in {"active", "refreshing"}:
        return None
    return row


def run_orphaned_session_sweep_job(
    factory: sessionmaker[Session],
    *,
    settings: Settings,
    tenant_id: str | None = None,
    now: datetime | None = None,
) -> JobRunResult:
    """Revoke orphaned ``refreshing`` and expired ``active`` browser sessions.

    Reuses the same staleness/expiry windows as the request path
    (``oidc_refresh_claim_staleness_seconds``, ``expires_at``,
    ``absolute_expires_at`` and the idle timeout) and the same revoke path, so a
    swept session is indistinguishable from one recovered lazily on presentation.
    Sessions are revoked in per-batch transactions, so a poisoned row cannot
    discard earlier successes. Idempotent: revoked rows leave the candidate set
    (and are re-checked before revoke), so a re-run is a no-op.
    """
    started_at = time.monotonic()
    now = _ensure_utc(now) if now is not None else datetime.now(UTC)
    claim_deadline = now - timedelta(seconds=settings.oidc_refresh_claim_staleness_seconds)
    idle_deadline: datetime | None = None
    if settings.oidc_session_idle_timeout_seconds > 0:
        idle_deadline = now - timedelta(seconds=settings.oidc_session_idle_timeout_seconds)

    limit = settings.scheduled_session_sweep_batch_limit
    errors: list[str] = []

    # Candidate selection runs in a read-only session; revocation runs in its own
    # per-batch transactions below.
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        orphaned_ids = [
            row.id
            for row in repository.list_orphaned_refreshing_oidc_browser_sessions(
                claim_deadline=claim_deadline,
                tenant_id=tenant_id,
                limit=limit,
            )
        ]
        expired_ids = [
            row.id
            for row in repository.list_expired_active_oidc_browser_sessions(
                now=now,
                idle_deadline=idle_deadline,
                tenant_id=tenant_id,
                limit=limit,
            )
        ]

    orphaned_revoked = 0
    for batch in _iter_batches(orphaned_ids, _TENANT_PAGE_SIZE):
        orphaned_revoked += _sweep_session_batch(
            factory,
            batch,
            revocation_reason=SESSION_SWEEP_ORPHANED_REASON,
            error_prefix="orphaned",
            errors=errors,
        )
    expired_revoked = 0
    for batch in _iter_batches(expired_ids, _TENANT_PAGE_SIZE):
        expired_revoked += _sweep_session_batch(
            factory,
            batch,
            revocation_reason=SESSION_SWEEP_EXPIRED_REASON,
            error_prefix="expired",
            errors=errors,
        )

    scanned = len(orphaned_ids) + len(expired_ids)
    affected = orphaned_revoked + expired_revoked
    summary_id = _append_summary_event(
        factory,
        tenant_id=tenant_id or "platform",
        event_type=SESSION_SWEEP_JOB_EVENT_TYPE,
        payload={
            "category": "scheduled_job",
            "job": "orphaned_session_sweep",
            "status": _sweep_status(errors),
            "tenant_scope": tenant_id or "all_tenants",
            "orphaned_scanned": len(orphaned_ids),
            "orphaned_revoked": orphaned_revoked,
            "expired_scanned": len(expired_ids),
            "expired_revoked": expired_revoked,
            "error_count": len(errors),
            "raw_payload_exported": False,
        },
    )

    return JobRunResult(
        job="orphaned_session_sweep",
        status=_sweep_status(errors),
        tenants_scanned=1 if tenant_id is not None else 0,
        items_scanned=scanned,
        items_affected=affected,
        duration_ms=_elapsed_ms(started_at),
        audit_event_ids=[summary_id],
        details={
            "tenant_scope": tenant_id or "all_tenants",
            "orphaned_revoked": orphaned_revoked,
            "expired_revoked": expired_revoked,
        },
        errors=errors,
    )


def _reconcile_one_tenant(
    factory: sessionmaker[Session],
    tenant_id: str,
    *,
    settings: Settings,
    now: datetime,
) -> tuple[dict, str | None]:
    """Reconcile a single tenant in its own transaction.

    Returns ``(per_tenant_detail, per_tenant_audit_event_id_or_None)``. Raising
    propagates to the caller which records the tenant-level failure; the failed
    tenant's transaction is rolled back but every other tenant already committed.
    """
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        tenant = repository.get_tenant(tenant_id)
        if tenant is None:
            return {"status": "missing"}, None

        findings: list[str] = []
        sessions_revoked = 0

        if tenant.status not in _VALID_TENANT_STATUSES:
            findings.append(f"unknown_lifecycle_status:{tenant.status}")

        for quota in repository.list_tenant_quotas(tenant.id):
            if quota.quota_key not in _VALID_QUOTA_KEYS:
                findings.append(f"unknown_quota_key:{quota.quota_key}")
            if quota.quota_value < 0:
                findings.append(f"negative_quota_value:{quota.quota_key}")

        # Fail-closed remediation: a blocked tenant must not retain usable
        # sessions. Revoke lingering active rows via the shared revoke path.
        if blocked_tenant_reason(tenant.status) is not None:
            lingering = repository.list_expired_active_oidc_browser_sessions(
                now=now + timedelta(days=3650),
                tenant_id=tenant.id,
                limit=settings.scheduled_session_sweep_batch_limit,
            )
            for lingering_session in lingering:
                _revoke_session_via_sweep(
                    repository,
                    lingering_session,
                    revocation_reason=SESSION_SWEEP_BLOCKED_TENANT_REASON,
                )
                sessions_revoked += 1
            if sessions_revoked:
                findings.append(f"revoked_sessions_on_blocked_tenant:{sessions_revoked}")

        detail = {
            "lifecycle_status": tenant.status,
            "findings": findings,
            "sessions_revoked": sessions_revoked,
        }
        event_id: str | None = None
        if findings or sessions_revoked:
            event = repository.append_audit_event(
                AuditEventCreate(
                    tenant_id=tenant.id,
                    actor_id=SCHEDULED_JOBS_ACTOR,
                    event_type=TENANT_RECONCILIATION_JOB_EVENT_TYPE,
                    payload={
                        "category": "scheduled_job",
                        "job": "tenant_state_reconciliation",
                        "status": "finding",
                        "lifecycle_status": tenant.status,
                        "findings": findings,
                        "sessions_revoked": sessions_revoked,
                        "raw_payload_exported": False,
                    },
                )
            )
            event_id = str(event.id)
        return detail, event_id


def run_tenant_state_reconciliation_job(
    factory: sessionmaker[Session],
    *,
    settings: Settings,
    tenant_ids: list[str] | None = None,
    now: datetime | None = None,
) -> JobRunResult:
    """Recompute and validate persisted tenant state, emitting audit evidence.

    Real consistency pass (not a no-op): for every tenant it validates the
    lifecycle status against the documented enum, validates every quota row's key
    and value, and - fail-closed - remediates lingering ``active`` browser sessions
    on a suspended/pending-deletion tenant by revoking them through the shared
    revoke path. Each tenant is reconciled in its own transaction, so one tenant's
    failure never rolls back another's. Idempotent: a clean tenant produces no
    findings and no session revocations on re-run.
    """
    started_at = time.monotonic()
    now = _ensure_utc(now) if now is not None else datetime.now(UTC)
    cap_reached = False
    if tenant_ids is None:
        tenant_ids, cap_reached = _iter_all_tenant_ids(factory)

    errors: list[str] = []
    audit_event_ids: list[str] = []
    per_tenant: dict[str, dict] = {}
    tenants_scanned = 0
    total_findings = 0
    total_sessions_revoked = 0

    for tenant_id in tenant_ids:
        try:
            detail, event_id = _reconcile_one_tenant(
                factory, tenant_id, settings=settings, now=now
            )
        except Exception as exc:  # noqa: BLE001 - fail closed, record and continue
            errors.append(f"{tenant_id}:{exc.__class__.__name__}")
            per_tenant[tenant_id] = {"status": "error", "error": exc.__class__.__name__}
            tenants_scanned += 1
            continue
        if detail.get("status") == "missing":
            continue
        tenants_scanned += 1
        per_tenant[tenant_id] = detail
        total_findings += len(detail["findings"])
        total_sessions_revoked += detail["sessions_revoked"]
        if event_id is not None:
            audit_event_ids.append(event_id)

    if cap_reached:
        errors.append(f"jobs_tenant_cap_reached:{tenants_scanned}")

    audit_event_ids.append(
        _append_summary_event(
            factory,
            tenant_id="platform",
            event_type=TENANT_RECONCILIATION_JOB_EVENT_TYPE,
            payload={
                "category": "scheduled_job",
                "job": "tenant_state_reconciliation",
                "status": _sweep_status(errors),
                "tenants_scanned": tenants_scanned,
                "finding_count": total_findings,
                "sessions_revoked": total_sessions_revoked,
                "error_count": len(errors),
                "tenant_cap_reached": cap_reached,
                "raw_payload_exported": False,
            },
        )
    )

    return JobRunResult(
        job="tenant_state_reconciliation",
        status=_sweep_status(errors),
        tenants_scanned=tenants_scanned,
        items_scanned=tenants_scanned,
        items_affected=total_findings + total_sessions_revoked,
        duration_ms=_elapsed_ms(started_at),
        audit_event_ids=audit_event_ids,
        details={
            "tenants": per_tenant,
            "sessions_revoked": total_sessions_revoked,
            "tenant_cap_reached": cap_reached,
        },
        errors=errors,
    )
