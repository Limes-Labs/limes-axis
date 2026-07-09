"""Tenant lifecycle and per-tenant quota foundation for the platform surface.

This module provides platform-operator provisioning, suspension, reactivation
and quota administration for tenants, plus the in-process tenant state cache
consulted by the enforcement points (suspended-tenant rejection, per-tenant API
rate limits, concurrent-session caps and live-sync row caps).
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from axis_api.audit import AuditEventCreate
from axis_api.db import session_scope
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import (
    ActorCreate,
    AxisPersistenceRepository,
    TenantCreate,
    TenantLifecycleTransition,
    TenantQuotaUpsert,
)


class TenantLifecycleStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING_DELETION = "pending_deletion"


class TenantQuotaKey(StrEnum):
    API_REQUESTS_PER_WINDOW = "api_requests_per_window"
    MAX_CONCURRENT_SESSIONS = "max_concurrent_sessions"
    MAX_CONNECTOR_SYNC_ROWS_PER_RUN = "max_connector_sync_rows_per_run"


class TenantLifecycleValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class TenantPermissionDenied(PermissionError):
    def __init__(self, required_permission: str, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.required_permission = required_permission
        self.decision = decision


class TenantProvisionConflict(ValueError):
    def __init__(self, tenant_id: str, reason: str) -> None:
        super().__init__("The tenant provisioning request conflicts with persisted state")
        self.tenant_id = tenant_id
        self.reason = reason


class TenantLifecycleConflict(ValueError):
    def __init__(self, tenant_id: str, reason: str) -> None:
        super().__init__("The tenant lifecycle transition conflicts with the current status")
        self.tenant_id = tenant_id
        self.reason = reason


class TenantNotFound(LookupError):
    pass


class TenantListCursorError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


REQUIRED_OPERATOR_SCOPE = "platform:tenant:operator"
REQUIRED_PROVISION_SCOPE = "platform:tenant:provision"
REQUIRED_SUSPEND_SCOPE = "platform:tenant:suspend"
REQUIRED_READ_SCOPE = "platform:tenant:read"
REQUIRED_QUOTA_SCOPE = "platform:tenant:quota"
PROVISIONED_AUDIT_EVENT_TYPE = "platform.tenant.provisioned"
SUSPENDED_AUDIT_EVENT_TYPE = "platform.tenant.suspended"
REACTIVATED_AUDIT_EVENT_TYPE = "platform.tenant.reactivated"
QUOTA_UPDATED_AUDIT_EVENT_TYPE = "platform.tenant.quota.updated"
SUSPENDED_REQUEST_DENIED_AUDIT_EVENT_TYPE = "platform.tenant.suspended_request.denied"
_BLOCKED_STATUS_REASONS = {
    TenantLifecycleStatus.SUSPENDED.value: "tenant_suspended",
    TenantLifecycleStatus.PENDING_DELETION.value: "tenant_pending_deletion",
}


class TenantBootstrapAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(default_factory=list)


class TenantProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=600)
    requested_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1, max_length=200)
    bootstrap_admin: TenantBootstrapAdmin | None = None
    notes: list[str] = Field(default_factory=list)


class TenantSuspendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=600)
    notes: list[str] = Field(default_factory=list)


class TenantReactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=600)
    notes: list[str] = Field(default_factory=list)


class TenantQuotaValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_requests_per_window: int | None = Field(default=None, ge=1, le=1_000_000)
    max_concurrent_sessions: int | None = Field(default=None, ge=0, le=10_000)
    max_connector_sync_rows_per_run: int | None = Field(default=None, ge=1, le=1_000_000)

    def as_mapping(self) -> dict[str, int | None]:
        return {
            TenantQuotaKey.API_REQUESTS_PER_WINDOW.value: self.api_requests_per_window,
            TenantQuotaKey.MAX_CONCURRENT_SESSIONS.value: self.max_concurrent_sessions,
            TenantQuotaKey.MAX_CONNECTOR_SYNC_ROWS_PER_RUN.value: (
                self.max_connector_sync_rows_per_run
            ),
        }


class TenantQuotaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    quotas: TenantQuotaValues
    notes: list[str] = Field(default_factory=list)


class TenantRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = ""
    status: TenantLifecycleStatus
    created_by: str = Field(min_length=1)
    bootstrap_admin_actor_id: str | None = None
    provision_idempotency_key: str | None = None
    suspended_at: datetime | None = None
    suspended_by: str | None = None
    suspension_reason: str | None = None
    reactivated_at: datetime | None = None
    reactivated_by: str | None = None
    permission_decision: PermissionDecision | None = None
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    idempotent_replay: bool = False
    notes: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TenantRegistry(BaseModel):
    tenant_count: int = Field(ge=0)
    active_tenant_count: int = Field(ge=0)
    tenants: list[TenantRecord] = Field(default_factory=list)
    has_more: bool = False
    next_cursor: str | None = None
    tenant_notes: list[str] = Field(default_factory=list)


class TenantQuotaChange(BaseModel):
    quota_key: str = Field(min_length=1)
    previous_value: int | None = None
    new_value: int | None = None
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)


class TenantQuotaSet(BaseModel):
    tenant_id: str = Field(min_length=1)
    quotas: dict[str, int] = Field(default_factory=dict)
    changes: list[TenantQuotaChange] = Field(default_factory=list)
    quota_notes: list[str] = Field(default_factory=list)


_QUOTA_NOTES = [
    "Tenant quotas override the global configuration for this tenant only.",
    "api_requests_per_window overrides the global API rate limit on protected paths.",
    "max_concurrent_sessions overrides the global concurrent browser-session cap.",
    "max_connector_sync_rows_per_run caps governed live-sync row limits per run.",
    "Every quota change appends platform.tenant.quota.updated audit evidence.",
]


def blocked_tenant_reason(status: str | None) -> str | None:
    """Return the fail-closed rejection reason for a non-active tenant status.

    Unknown tenants (no persisted row) return ``None``: only tenants explicitly
    moved out of the active status are blocked, so environments without seeded
    tenant rows keep their existing behavior.
    """
    if status is None:
        return None
    return _BLOCKED_STATUS_REASONS.get(status)


def provision_tenant(
    repository: AxisPersistenceRepository,
    request: TenantProvisionRequest,
) -> TenantRecord:
    existing_replay = repository.get_tenant_by_provision_idempotency_key(
        request.idempotency_key
    )
    if existing_replay is not None:
        if not _provision_matches_request(existing_replay, request):
            raise TenantProvisionConflict(
                request.tenant_id, "provision_idempotency_conflict"
            )
        return _tenant_from_record(existing_replay, idempotent_replay=True)

    existing = repository.get_tenant(request.tenant_id)
    if existing is not None:
        raise TenantProvisionConflict(request.tenant_id, "tenant_already_exists")

    permission_decision = _evaluate_operator_permission(
        tenant_id=request.tenant_id,
        actor_id=request.requested_by,
        actor_scopes=request.actor_scopes,
        action_scope=REQUIRED_PROVISION_SCOPE,
        attributes={
            "operation": "provision_tenant",
            "idempotency_key": request.idempotency_key,
        },
    )
    bootstrap_admin = request.bootstrap_admin
    if bootstrap_admin is not None and repository.get_actor(bootstrap_admin.actor_id):
        raise TenantProvisionConflict(request.tenant_id, "bootstrap_admin_actor_exists")

    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type=PROVISIONED_AUDIT_EVENT_TYPE,
            payload={
                "tenant_id": request.tenant_id,
                "display_name": request.display_name,
                "status": TenantLifecycleStatus.ACTIVE.value,
                "idempotency_key": request.idempotency_key,
                "bootstrap_admin_actor_id": (
                    bootstrap_admin.actor_id if bootstrap_admin else None
                ),
                # Scope grants stay IdP-owned; the requested bootstrap scopes are
                # recorded as audit evidence only, never as a live grant.
                "bootstrap_admin_requested_scopes": (
                    bootstrap_admin.scopes if bootstrap_admin else []
                ),
                "required_operator_scope": REQUIRED_OPERATOR_SCOPE,
                "required_provision_scope": REQUIRED_PROVISION_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    if bootstrap_admin is not None:
        repository.create_actor(
            ActorCreate(
                actor_id=bootstrap_admin.actor_id,
                tenant_id=request.tenant_id,
                display_name=bootstrap_admin.display_name,
                actor_type="human",
            )
        )
    tenant = repository.create_tenant(
        TenantCreate(
            tenant_id=request.tenant_id,
            display_name=request.display_name,
            description=request.description,
            status=TenantLifecycleStatus.ACTIVE.value,
            created_by=request.requested_by,
            bootstrap_admin_actor_id=(
                bootstrap_admin.actor_id if bootstrap_admin else None
            ),
            provision_idempotency_key=request.idempotency_key,
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=request.notes,
        )
    )
    return _tenant_from_record(tenant, permission_decision=permission_decision)


def get_tenant_detail(
    repository: AxisPersistenceRepository,
    tenant_id: str,
) -> TenantRecord:
    """Return a single tenant record, raising ``TenantNotFound`` when absent."""
    tenant = repository.get_tenant(tenant_id)
    if tenant is None:
        raise TenantNotFound()
    return _tenant_from_record(tenant)


def encode_tenant_cursor(record) -> str:
    """Keyset cursor for the tenant listing, ordered by ``tenant_id`` ascending.

    The tenant id is the primary key, so a single-column keyset is a total
    order and needs no tiebreaker, unlike the ``/identity/sessions`` keyset.
    """
    payload = {"tenant_id": record.id}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_tenant_cursor(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        tenant_id = str(payload["tenant_id"])
    except (
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise TenantListCursorError("invalid_tenant_cursor") from exc
    if not tenant_id:
        raise TenantListCursorError("invalid_tenant_cursor")
    return tenant_id


def build_tenant_registry(
    repository: AxisPersistenceRepository,
    status: TenantLifecycleStatus | None = None,
    limit: int = 100,
    cursor_tenant_id: str | None = None,
) -> TenantRegistry:
    # Over-fetch by one to detect a further page without a second count query,
    # matching the keyset precedent used by /identity/sessions.
    records = repository.list_tenants(
        status=status.value if status is not None else None,
        limit=limit + 1,
        cursor_tenant_id=cursor_tenant_id,
    )
    has_more = len(records) > limit
    page_records = records[:limit]
    tenants = [_tenant_from_record(record) for record in page_records]
    active_count = sum(
        1 for tenant in tenants if tenant.status == TenantLifecycleStatus.ACTIVE
    )
    next_cursor = (
        encode_tenant_cursor(page_records[-1]) if has_more and page_records else None
    )
    return TenantRegistry(
        tenant_count=len(tenants),
        active_tenant_count=active_count,
        tenants=tenants,
        has_more=has_more,
        next_cursor=next_cursor,
        tenant_notes=[
            "Tenant lifecycle is a platform-operator surface, not a tenant surface.",
            "Suspended and pending-deletion tenants are rejected fail-closed at the "
            "OIDC principal boundary.",
            "Lifecycle mutations append audit evidence in the target tenant's ledger "
            "with the operator recorded as actor.",
        ],
    )


def suspend_tenant(
    repository: AxisPersistenceRepository,
    tenant_id: str,
    request: TenantSuspendRequest,
) -> TenantRecord:
    tenant = repository.get_tenant(tenant_id)
    if tenant is None:
        raise TenantNotFound()
    if tenant.status != TenantLifecycleStatus.ACTIVE.value:
        raise TenantLifecycleConflict(tenant_id, "tenant_not_active")

    permission_decision = _evaluate_operator_permission(
        tenant_id=tenant_id,
        actor_id=request.requested_by,
        actor_scopes=request.actor_scopes,
        action_scope=REQUIRED_SUSPEND_SCOPE,
        attributes={"operation": "suspend_tenant", "reason": request.reason},
    )
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=tenant_id,
            actor_id=request.requested_by,
            event_type=SUSPENDED_AUDIT_EVENT_TYPE,
            payload={
                "tenant_id": tenant_id,
                "previous_status": tenant.status,
                "status": TenantLifecycleStatus.SUSPENDED.value,
                "reason": request.reason,
                "required_operator_scope": REQUIRED_OPERATOR_SCOPE,
                "required_suspend_scope": REQUIRED_SUSPEND_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    updated = repository.update_tenant_lifecycle(
        TenantLifecycleTransition(
            tenant_id=tenant_id,
            status=TenantLifecycleStatus.SUSPENDED.value,
            actor_id=request.requested_by,
            reason=request.reason,
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=request.notes,
        )
    )
    return _tenant_from_record(updated, permission_decision=permission_decision)


def reactivate_tenant(
    repository: AxisPersistenceRepository,
    tenant_id: str,
    request: TenantReactivateRequest,
) -> TenantRecord:
    tenant = repository.get_tenant(tenant_id)
    if tenant is None:
        raise TenantNotFound()
    if tenant.status == TenantLifecycleStatus.ACTIVE.value:
        raise TenantLifecycleConflict(tenant_id, "tenant_already_active")

    permission_decision = _evaluate_operator_permission(
        tenant_id=tenant_id,
        actor_id=request.requested_by,
        actor_scopes=request.actor_scopes,
        action_scope=REQUIRED_SUSPEND_SCOPE,
        attributes={"operation": "reactivate_tenant", "reason": request.reason},
    )
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=tenant_id,
            actor_id=request.requested_by,
            event_type=REACTIVATED_AUDIT_EVENT_TYPE,
            payload={
                "tenant_id": tenant_id,
                "previous_status": tenant.status,
                "status": TenantLifecycleStatus.ACTIVE.value,
                "reason": request.reason,
                "required_operator_scope": REQUIRED_OPERATOR_SCOPE,
                "required_suspend_scope": REQUIRED_SUSPEND_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    updated = repository.update_tenant_lifecycle(
        TenantLifecycleTransition(
            tenant_id=tenant_id,
            status=TenantLifecycleStatus.ACTIVE.value,
            actor_id=request.requested_by,
            reason=request.reason or None,
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=request.notes,
        )
    )
    return _tenant_from_record(updated, permission_decision=permission_decision)


def get_tenant_quota_set(
    repository: AxisPersistenceRepository,
    tenant_id: str,
) -> TenantQuotaSet:
    if repository.get_tenant(tenant_id) is None:
        raise TenantNotFound()
    quotas = {
        quota.quota_key: quota.quota_value
        for quota in repository.list_tenant_quotas(tenant_id)
    }
    return TenantQuotaSet(tenant_id=tenant_id, quotas=quotas, quota_notes=_QUOTA_NOTES)


def update_tenant_quotas(
    repository: AxisPersistenceRepository,
    tenant_id: str,
    request: TenantQuotaUpdateRequest,
) -> TenantQuotaSet:
    """Replace the tenant quota set with the requested typed values.

    ``PUT`` semantics are full replacement over the typed quota keys: a key set
    to a value is upserted in place, a key left ``None`` is cleared. Quota rows
    are update-in-place; the append-only history lives in the
    ``platform.tenant.quota.updated`` audit trail written for every change.
    """
    tenant = repository.get_tenant(tenant_id)
    if tenant is None:
        raise TenantNotFound()

    permission_decision = _evaluate_operator_permission(
        tenant_id=tenant_id,
        actor_id=request.requested_by,
        actor_scopes=request.actor_scopes,
        action_scope=REQUIRED_QUOTA_SCOPE,
        attributes={"operation": "update_tenant_quotas"},
    )
    changes: list[TenantQuotaChange] = []
    for quota_key, new_value in request.quotas.as_mapping().items():
        existing = repository.get_tenant_quota(tenant_id, quota_key)
        previous_value = existing.quota_value if existing is not None else None
        if new_value == previous_value:
            continue
        audit_event = repository.append_audit_event(
            AuditEventCreate(
                tenant_id=tenant_id,
                actor_id=request.requested_by,
                event_type=QUOTA_UPDATED_AUDIT_EVENT_TYPE,
                payload={
                    "tenant_id": tenant_id,
                    "quota_key": quota_key,
                    "previous_value": previous_value,
                    "new_value": new_value,
                    "required_operator_scope": REQUIRED_OPERATOR_SCOPE,
                    "required_quota_scope": REQUIRED_QUOTA_SCOPE,
                    "permission_decision": permission_decision.model_dump(),
                },
            )
        )
        if new_value is None:
            repository.delete_tenant_quota(tenant_id, quota_key)
        else:
            repository.upsert_tenant_quota(
                TenantQuotaUpsert(
                    tenant_id=tenant_id,
                    quota_key=quota_key,
                    quota_value=new_value,
                    updated_by=request.requested_by,
                    audit_event_id=audit_event.id,
                    audit_event_type=audit_event.event_type,
                    notes=request.notes,
                )
            )
        changes.append(
            TenantQuotaChange(
                quota_key=quota_key,
                previous_value=previous_value,
                new_value=new_value,
                audit_event_id=audit_event.id,
                audit_event_type=audit_event.event_type,
            )
        )
    quotas = {
        quota.quota_key: quota.quota_value
        for quota in repository.list_tenant_quotas(tenant_id)
    }
    return TenantQuotaSet(
        tenant_id=tenant_id,
        quotas=quotas,
        changes=changes,
        quota_notes=_QUOTA_NOTES,
    )


@dataclass(frozen=True)
class TenantStateSnapshot:
    status: str | None
    quotas: dict[str, int]


@dataclass
class _TenantStateCacheEntry:
    snapshot: TenantStateSnapshot
    expires_at: float


class TenantStateCache:
    """Bounded in-process cache for tenant status and quota lookups.

    The suspension check and the per-tenant rate limit run on the hot request
    path, so lookups are cached for a short TTL. The staleness window equals the
    TTL: a suspension or quota change on another replica (or another process)
    takes effect here within at most ``ttl_seconds``. Lifecycle and quota routes
    invalidate the local entry immediately, so single-process deployments see
    changes at once. A TTL of 0 disables caching and reads fresh state on every
    request.
    """

    def __init__(self, *, ttl_seconds: float, max_entries: int = 1024) -> None:
        self.ttl_seconds = max(0.0, ttl_seconds)
        self.max_entries = max(1, max_entries)
        self._entries: dict[str, _TenantStateCacheEntry] = {}

    def snapshot(
        self,
        session_factory: sessionmaker[Session],
        tenant_id: str,
        *,
        now: float | None = None,
    ) -> TenantStateSnapshot:
        observed_at = now if now is not None else time.monotonic()
        entry = self._entries.get(tenant_id)
        if entry is not None and observed_at < entry.expires_at:
            return entry.snapshot

        with session_scope(session_factory) as session:
            repository = AxisPersistenceRepository(session)
            tenant = repository.get_tenant(tenant_id)
            quotas = {
                quota.quota_key: quota.quota_value
                for quota in repository.list_tenant_quotas(tenant_id)
            }
            snapshot = TenantStateSnapshot(
                status=tenant.status if tenant is not None else None,
                quotas=quotas,
            )
        if self.ttl_seconds > 0:
            while len(self._entries) >= self.max_entries:
                self._entries.pop(next(iter(self._entries)))
            self._entries[tenant_id] = _TenantStateCacheEntry(
                snapshot=snapshot,
                expires_at=observed_at + self.ttl_seconds,
            )
        return snapshot

    def invalidate(self, tenant_id: str) -> None:
        self._entries.pop(tenant_id, None)


def _provision_matches_request(record, request: TenantProvisionRequest) -> bool:
    bootstrap_actor_id = (
        request.bootstrap_admin.actor_id if request.bootstrap_admin else None
    )
    return (
        record.id == request.tenant_id
        and record.name == request.display_name
        and record.description == request.description
        and record.bootstrap_admin_actor_id == bootstrap_actor_id
        and record.created_by == request.requested_by
    )


def _evaluate_operator_permission(
    *,
    tenant_id: str,
    actor_id: str,
    actor_scopes: list[str],
    action_scope: str,
    attributes: dict,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_scopes=actor_scopes,
            required_scopes=[REQUIRED_OPERATOR_SCOPE, action_scope],
            attributes={
                "surface": "platform_tenants",
                **attributes,
            },
        )
    )
    if not decision.allowed:
        required_permission = decision.reason.removeprefix("missing_scope:")
        if required_permission == decision.reason:
            required_permission = action_scope
        raise TenantPermissionDenied(required_permission, decision)
    return decision


def _tenant_from_record(
    record,
    *,
    permission_decision: PermissionDecision | None = None,
    idempotent_replay: bool = False,
) -> TenantRecord:
    return TenantRecord(
        tenant_id=record.id,
        display_name=record.name,
        description=record.description,
        status=TenantLifecycleStatus(record.status),
        created_by=record.created_by,
        bootstrap_admin_actor_id=record.bootstrap_admin_actor_id,
        provision_idempotency_key=record.provision_idempotency_key,
        suspended_at=record.suspended_at,
        suspended_by=record.suspended_by,
        suspension_reason=record.suspension_reason,
        reactivated_at=record.reactivated_at,
        reactivated_by=record.reactivated_by,
        permission_decision=permission_decision,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        idempotent_replay=idempotent_replay,
        notes=list(record.notes),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
