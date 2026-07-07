"""Reusable business logic for scheduled/periodic maintenance jobs.

These functions are the single source of truth for the maintenance work that the
Temporal worker runs on a schedule (see ``services/worker``). They deliberately
operate on an :class:`AxisPersistenceRepository` bound to a caller-provided
SQLAlchemy session so they can be:

* driven by the worker against a real Postgres session in production, and
* unit-tested directly against an in-memory SQLite session with no live
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
items scanned/affected and a duration). Jobs fail closed: a per-item failure is
recorded in ``errors`` and surfaced via ``status="partial_failure"`` instead of
being silently swallowed.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from axis_api.audit import AuditEventCreate
from axis_api.audit_queries import (
    RETENTION_DELETION_REQUIRED_SCOPE,
    AuditRetentionDeletionRequest,
    AuditRetentionDeletionResult,
    execute_audit_retention_deletion,
)
from axis_api.config import Settings
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
    repository: AxisPersistenceRepository,
    *,
    settings: Settings,
    tenant_ids: list[str] | None = None,
) -> JobRunResult:
    """Sweep audit retention deletion across tenants on a schedule.

    Reuses :func:`execute_audit_retention_deletion` per tenant with the scheduled
    actor holding the retention-deletion scope. Legal holds and dry-run behavior
    are honored by the reused function. Idempotent: once eligible rows are deleted,
    the next run finds no further candidates.
    """
    started_at = time.monotonic()
    if tenant_ids is None:
        tenant_ids = [tenant.id for tenant in repository.list_tenants(limit=1000)]

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

    summary_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="platform",
            actor_id=SCHEDULED_JOBS_ACTOR,
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
                "raw_payload_exported": False,
            },
        )
    )
    audit_event_ids.append(str(summary_event.id))

    return JobRunResult(
        job="audit_retention_deletion",
        status=_sweep_status(errors),
        tenants_scanned=tenants_scanned,
        items_scanned=total_candidates,
        items_affected=total_deleted,
        duration_ms=_elapsed_ms(started_at),
        audit_event_ids=audit_event_ids,
        details={"dry_run": dry_run, "retention_days": retention_days, "tenants": per_tenant},
        errors=errors,
    )


def run_orphaned_session_sweep_job(
    repository: AxisPersistenceRepository,
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
    Idempotent: revoked rows leave the candidate set, so a re-run is a no-op.
    """
    started_at = time.monotonic()
    now = _ensure_utc(now) if now is not None else datetime.now(UTC)
    claim_deadline = now - timedelta(seconds=settings.oidc_refresh_claim_staleness_seconds)
    idle_deadline: datetime | None = None
    if settings.oidc_session_idle_timeout_seconds > 0:
        idle_deadline = now - timedelta(seconds=settings.oidc_session_idle_timeout_seconds)

    limit = settings.scheduled_session_sweep_batch_limit
    errors: list[str] = []
    orphaned_revoked = 0
    expired_revoked = 0

    orphaned = repository.list_orphaned_refreshing_oidc_browser_sessions(
        claim_deadline=claim_deadline,
        tenant_id=tenant_id,
        limit=limit,
    )
    for session in orphaned:
        try:
            _revoke_session_via_sweep(
                repository,
                session,
                revocation_reason=SESSION_SWEEP_ORPHANED_REASON,
            )
            orphaned_revoked += 1
        except Exception as exc:  # noqa: BLE001 - fail closed, record and continue
            errors.append(f"orphaned:{session.session_id_hash[:12]}:{exc.__class__.__name__}")

    expired = repository.list_expired_active_oidc_browser_sessions(
        now=now,
        idle_deadline=idle_deadline,
        tenant_id=tenant_id,
        limit=limit,
    )
    for session in expired:
        try:
            _revoke_session_via_sweep(
                repository,
                session,
                revocation_reason=SESSION_SWEEP_EXPIRED_REASON,
            )
            expired_revoked += 1
        except Exception as exc:  # noqa: BLE001 - fail closed, record and continue
            errors.append(f"expired:{session.session_id_hash[:12]}:{exc.__class__.__name__}")

    scanned = len(orphaned) + len(expired)
    affected = orphaned_revoked + expired_revoked
    summary_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=tenant_id or "platform",
            actor_id=SCHEDULED_JOBS_ACTOR,
            event_type=SESSION_SWEEP_JOB_EVENT_TYPE,
            payload={
                "category": "scheduled_job",
                "job": "orphaned_session_sweep",
                "status": _sweep_status(errors),
                "tenant_scope": tenant_id or "all_tenants",
                "orphaned_scanned": len(orphaned),
                "orphaned_revoked": orphaned_revoked,
                "expired_scanned": len(expired),
                "expired_revoked": expired_revoked,
                "error_count": len(errors),
                "raw_payload_exported": False,
            },
        )
    )

    return JobRunResult(
        job="orphaned_session_sweep",
        status=_sweep_status(errors),
        tenants_scanned=1 if tenant_id is not None else 0,
        items_scanned=scanned,
        items_affected=affected,
        duration_ms=_elapsed_ms(started_at),
        audit_event_ids=[str(summary_event.id)],
        details={
            "tenant_scope": tenant_id or "all_tenants",
            "orphaned_revoked": orphaned_revoked,
            "expired_revoked": expired_revoked,
        },
        errors=errors,
    )


def run_tenant_state_reconciliation_job(
    repository: AxisPersistenceRepository,
    *,
    settings: Settings,
    tenant_ids: list[str] | None = None,
    now: datetime | None = None,
) -> JobRunResult:
    """Recompute and validate persisted tenant state, emitting audit evidence.

    Real consistency pass (not a no-op): for every tenant it validates the
    lifecycle status against the documented enum, validates every quota row's key
    and value, and — fail-closed — remediates lingering ``active`` browser sessions
    on a suspended/pending-deletion tenant by revoking them through the shared
    revoke path (a suspended tenant must not keep usable sessions at rest). Every
    reconciled tenant with a finding or remediation records per-tenant audit
    evidence; the job appends a summary event with counts. Idempotent: a clean
    tenant produces no findings and no session revocations on re-run.
    """
    started_at = time.monotonic()
    now = _ensure_utc(now) if now is not None else datetime.now(UTC)
    if tenant_ids is None:
        tenants = repository.list_tenants(limit=1000)
    else:
        tenants = [t for t in (repository.get_tenant(tid) for tid in tenant_ids) if t is not None]

    errors: list[str] = []
    audit_event_ids: list[str] = []
    per_tenant: dict[str, dict] = {}
    tenants_scanned = 0
    total_findings = 0
    total_sessions_revoked = 0

    for tenant in tenants:
        tenants_scanned += 1
        findings: list[str] = []
        sessions_revoked = 0
        try:
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
                for session in lingering:
                    _revoke_session_via_sweep(
                        repository,
                        session,
                        revocation_reason=SESSION_SWEEP_BLOCKED_TENANT_REASON,
                    )
                    sessions_revoked += 1
                if sessions_revoked:
                    findings.append(f"revoked_sessions_on_blocked_tenant:{sessions_revoked}")
        except Exception as exc:  # noqa: BLE001 - fail closed, record and continue
            errors.append(f"{tenant.id}:{exc.__class__.__name__}")
            per_tenant[tenant.id] = {"status": "error", "error": exc.__class__.__name__}
            continue

        total_findings += len(findings)
        total_sessions_revoked += sessions_revoked
        per_tenant[tenant.id] = {
            "lifecycle_status": tenant.status,
            "findings": findings,
            "sessions_revoked": sessions_revoked,
        }
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
            audit_event_ids.append(str(event.id))

    summary_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="platform",
            actor_id=SCHEDULED_JOBS_ACTOR,
            event_type=TENANT_RECONCILIATION_JOB_EVENT_TYPE,
            payload={
                "category": "scheduled_job",
                "job": "tenant_state_reconciliation",
                "status": _sweep_status(errors),
                "tenants_scanned": tenants_scanned,
                "finding_count": total_findings,
                "sessions_revoked": total_sessions_revoked,
                "error_count": len(errors),
                "raw_payload_exported": False,
            },
        )
    )
    audit_event_ids.append(str(summary_event.id))

    return JobRunResult(
        job="tenant_state_reconciliation",
        status=_sweep_status(errors),
        tenants_scanned=tenants_scanned,
        items_scanned=tenants_scanned,
        items_affected=total_findings + total_sessions_revoked,
        duration_ms=_elapsed_ms(started_at),
        audit_event_ids=audit_event_ids,
        details={"tenants": per_tenant, "sessions_revoked": total_sessions_revoked},
        errors=errors,
    )
