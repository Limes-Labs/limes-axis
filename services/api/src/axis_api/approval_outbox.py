"""Durable, at-least-once delivery of approval decisions to Temporal."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session, sessionmaker

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.persistence import AxisPersistenceRepository
from axis_api.workflow_runtime import (
    APPROVAL_DECISION_SCHEMA_VERSION,
    APPROVAL_DECISION_SIGNAL_NAME,
    WorkflowSignalError,
    WorkflowSignalRequest,
    WorkflowSignalRuntime,
)

OUTBOX_ACTOR = "axis-approval-outbox"
OUTBOX_DELIVERED_EVENT = "approval.decision.delivery.delivered"
OUTBOX_DEAD_LETTER_EVENT = "approval.decision.delivery.dead_lettered"
_MAX_CONCURRENCY = 100
_SAFE_WORKFLOW_ERROR_CODES = frozenset(
    {
        "OSError",
        "RPCError",
        "RuntimeError",
        "TemporalError",
        "WorkflowFailureError",
    }
)


@dataclass(frozen=True)
class _ClaimedDecision:
    id: UUID
    tenant_id: str
    approval_id: str
    workflow_id: str
    signal_name: str
    schema_version: str
    decision: str
    decision_actor_id: str
    payload: dict
    attempt_count: int
    claim_token: UUID


class ApprovalDecisionOutboxRunResult(BaseModel):
    claimed: int = Field(ge=0)
    delivered: int = Field(ge=0)
    retried: int = Field(ge=0)
    dead_lettered: int = Field(ge=0)
    fenced: int = Field(ge=0)


class ApprovalDecisionDeliveryStatus(BaseModel):
    tenant_id: str
    approval_id: str
    decision_event_id: UUID
    workflow_id: str
    status: str
    attempt_count: int = Field(ge=0)
    available_at: datetime
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    dead_lettered_at: datetime | None = None
    last_error_code: str | None = None


def get_approval_decision_delivery_status(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    approval_id: str,
) -> ApprovalDecisionDeliveryStatus | None:
    row = repository.get_approval_decision_outbox(tenant_id, approval_id)
    if row is None:
        return None
    return ApprovalDecisionDeliveryStatus(
        tenant_id=row.tenant_id,
        approval_id=row.approval_id,
        decision_event_id=row.id,
        workflow_id=row.workflow_id,
        status=row.status,
        attempt_count=row.attempt_count,
        available_at=row.available_at,
        last_attempt_at=row.last_attempt_at,
        delivered_at=row.delivered_at,
        dead_lettered_at=row.dead_lettered_at,
        last_error_code=row.last_error,
    )


class _DeliveryOutcome(BaseModel):
    status: str


class ApprovalDecisionOutboxDispatcher:
    """Claim due rows, signal Temporal, and finalize through fenced leases."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        workflow_runtime: WorkflowSignalRuntime,
        clock: Callable[[], datetime] | None = None,
        random_uniform: Callable[[float, float], float] | None = None,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory
        self._workflow_runtime = workflow_runtime
        self._clock = clock or (lambda: datetime.now(UTC))
        self._random_uniform = random_uniform or random.uniform

    async def run_once(self) -> ApprovalDecisionOutboxRunResult:
        claimed = await asyncio.to_thread(self._claim)
        if not claimed:
            return ApprovalDecisionOutboxRunResult(
                claimed=0, delivered=0, retried=0, dead_lettered=0, fenced=0
            )
        semaphore = asyncio.Semaphore(min(_MAX_CONCURRENCY, len(claimed)))

        async def deliver(row: _ClaimedDecision) -> _DeliveryOutcome:
            async with semaphore:
                return await self._deliver(row)

        outcomes = await asyncio.gather(*(deliver(row) for row in claimed))
        counts = {status: 0 for status in ("delivered", "retried", "dead_lettered", "fenced")}
        for outcome in outcomes:
            counts[outcome.status] += 1
        return ApprovalDecisionOutboxRunResult(claimed=len(claimed), **counts)

    def _claim(self) -> list[_ClaimedDecision]:
        now = self._clock()
        lease_expires_at = now + timedelta(
            seconds=self.settings.approval_decision_outbox_claim_timeout_seconds
        )
        with session_scope(self._session_factory) as session:
            rows = AxisPersistenceRepository(session).claim_approval_decision_outbox(
                now=now,
                lease_expires_at=lease_expires_at,
                limit=self.settings.approval_decision_outbox_batch_size,
            )
            return [
                _ClaimedDecision(
                    id=row.id,
                    tenant_id=row.tenant_id,
                    approval_id=row.approval_id,
                    workflow_id=row.workflow_id,
                    signal_name=row.signal_name,
                    schema_version=row.schema_version,
                    decision=row.decision,
                    decision_actor_id=row.decision_actor_id,
                    payload=dict(row.payload),
                    attempt_count=row.attempt_count,
                    claim_token=row.claim_token,
                )
                for row in rows
                if row.claim_token is not None
            ]

    def _request(self, row: _ClaimedDecision) -> WorkflowSignalRequest:
        if (
            row.signal_name != APPROVAL_DECISION_SIGNAL_NAME
            or row.schema_version != APPROVAL_DECISION_SCHEMA_VERSION
        ):
            raise ValueError("unsupported_contract")
        request = WorkflowSignalRequest.model_validate(
            {**row.payload, "signal_name": row.signal_name}
        )
        if (
            request.decision_event_id != row.id
            or request.tenant_id != row.tenant_id
            or request.workflow_id != row.workflow_id
            or request.approval_id != row.approval_id
            or request.decision.value != row.decision
            or request.actor_id != row.decision_actor_id
        ):
            raise ValueError("payload_row_mismatch")
        return request

    async def _deliver(self, row: _ClaimedDecision) -> _DeliveryOutcome:
        try:
            request = self._request(row)
        except (ValidationError, ValueError) as exc:
            return await self._finalize_failure(row, self._error_code(exc), permanent=True)
        try:
            await self._workflow_runtime.signal_approval_decision(request)
        except WorkflowSignalError as exc:
            if exc.may_be_closed:
                reconciliation = await self._reconcile(row)
                if reconciliation == "matching":
                    return await self._finalize_success(row)
                if reconciliation == "conflicting":
                    return await self._finalize_failure(
                        row, "completed_workflow_conflict", permanent=True
                    )
            return await self._finalize_failure(row, self._error_code(exc), permanent=False)
        return await self._finalize_success(row)

    async def _reconcile(self, row: _ClaimedDecision) -> str:
        reader = getattr(self._workflow_runtime, "get_approval_decision_result", None)
        if reader is None:
            return "unknown"
        try:
            result = await reader(row.workflow_id)
        except WorkflowSignalError:
            return "unknown"
        if result is None:
            return "unknown"
        decision = result.get("decision")
        if not isinstance(decision, dict):
            return "conflicting"
        return "matching" if decision == self._request(row).runtime_payload else "conflicting"

    async def _finalize_success(self, row: _ClaimedDecision) -> _DeliveryOutcome:
        return await asyncio.to_thread(self._finalize_success_sync, row)

    def _finalize_success_sync(self, row: _ClaimedDecision) -> _DeliveryOutcome:
        now = self._clock()
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            changed = repository.complete_approval_decision_outbox(
                row.id, row.claim_token, delivered_at=now
            )
            if changed:
                repository.append_audit_event(
                    AuditEventCreate(
                        tenant_id=row.tenant_id,
                        actor_id=OUTBOX_ACTOR,
                        event_type=OUTBOX_DELIVERED_EVENT,
                        payload={
                            "decision_event_id": str(row.id),
                            "approval_id": row.approval_id,
                            "workflow_id": row.workflow_id,
                            "attempt_count": row.attempt_count,
                        },
                    )
                )
        return _DeliveryOutcome(status="delivered" if changed else "fenced")

    async def _finalize_failure(
        self, row: _ClaimedDecision, error_code: str, *, permanent: bool
    ) -> _DeliveryOutcome:
        return await asyncio.to_thread(
            self._finalize_failure_sync,
            row,
            error_code,
            permanent,
        )

    def _finalize_failure_sync(
        self, row: _ClaimedDecision, error_code: str, permanent: bool
    ) -> _DeliveryOutcome:
        now = self._clock()
        exhausted = row.attempt_count >= self.settings.approval_decision_outbox_max_attempts
        dead_letter = permanent or exhausted
        available_at = now if dead_letter else now + self._retry_delay(row.attempt_count)
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            changed = repository.retry_approval_decision_outbox(
                row.id,
                row.claim_token,
                available_at=available_at,
                updated_at=now,
                error=error_code,
                dead_letter=dead_letter,
            )
            if changed and dead_letter:
                repository.append_audit_event(
                    AuditEventCreate(
                        tenant_id=row.tenant_id,
                        actor_id=OUTBOX_ACTOR,
                        event_type=OUTBOX_DEAD_LETTER_EVENT,
                        payload={
                            "decision_event_id": str(row.id),
                            "approval_id": row.approval_id,
                            "workflow_id": row.workflow_id,
                            "attempt_count": row.attempt_count,
                            "error_code": error_code,
                        },
                    )
                )
        if not changed:
            return _DeliveryOutcome(status="fenced")
        return _DeliveryOutcome(status="dead_lettered" if dead_letter else "retried")

    def _retry_delay(self, attempt_count: int) -> timedelta:
        maximum = min(
            self.settings.approval_decision_outbox_retry_max_seconds,
            self.settings.approval_decision_outbox_retry_base_seconds
            * (2 ** max(0, attempt_count - 1)),
        )
        return timedelta(seconds=self._random_uniform(0.0, maximum))

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if isinstance(exc, WorkflowSignalError):
            return (
                exc.reason
                if exc.reason in _SAFE_WORKFLOW_ERROR_CODES
                else "workflow_signal_error"
            )
        elif isinstance(exc, ValueError) and str(exc):
            value = str(exc)
        else:
            value = exc.__class__.__name__
        sanitized = "".join(
            character for character in value if character.isalnum() or character in "._-"
        )
        return sanitized[:80] or "delivery_error"
