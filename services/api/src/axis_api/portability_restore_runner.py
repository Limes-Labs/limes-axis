"""Resumable restore runner: plan execution into an isolated suspended tenant.

Slice 3/4 of [#878](https://github.com/Limes-Labs/limes-axis/issues/878)
(parent #476), stacked on the #876 manifest contract and the #877 offline
validator. The runner executes a validated plan through **versioned component
restore ports** — never SQL or scripts supplied by the archive — and persists
a complete per-component outcome before any application access is possible:

* Runs and steps are persisted with dependency-ordered sequencing and exact
  digest evidence; a crash leaves resumable or quarantined state, never a
  partially activated tenant.
* Execution is fenced: one worker owns a run's current step via a row lock
  plus explicit fencing flag; two workers cannot claim the same generation.
* Every step is idempotent by construction (deterministic handler writes);
  retries re-run the handler and record a new attempt, completed steps are
  never re-executed.
* Authorization binds the run to the exact bundle/plan/target digests and
  the acknowledgement; operator rights are re-checked through an injected
  callback at start and at every resume, failing closed.
* Writes land only inside the newly admitted suspended target tenant and a
  dedicated object prefix derived from the bundle digest; object-store
  writes and SQL step records are not one distributed transaction, so
  handlers must be idempotent and step boundaries are the reconciliation
  points.
* Missing handlers block their steps as ``blocked`` — never fabricated
  ``completed`` states; imported operational work stays inert and activation
  of the target tenant is out of scope (#879 verifies, operators enable).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from axis_sdk.connector_authoring.contracts import Digest
from sqlalchemy import select
from sqlalchemy.orm import Session

from axis_api.models import PortabilityRestoreRunRecord, PortabilityRestoreStepRecord
from axis_api.portability_validator import PlanAcknowledgement, RestorePlan

RUN_STATE_PENDING = "pending"
RUN_STATE_RUNNING = "running"
RUN_STATE_QUARANTINED = "suspended_quarantined"
RUN_STATE_COMPLETED = "completed"

STEP_STATE_PENDING = "pending"
STEP_STATE_IN_PROGRESS = "in_progress"
STEP_STATE_COMPLETED = "completed"
STEP_STATE_FAILED = "failed"
STEP_STATE_BLOCKED = "blocked"


class PortabilityRestoreError(ValueError):
    """Fixed safe codes; never echoes bundle contents."""

    FENCED = "restore_run_fenced_by_other_worker"
    PLAN_MISMATCH = "plan_acknowledgement_mismatch"
    NOT_RESUMABLE = "restore_run_not_resumable"
    OPERATOR_UNAUTHORIZED = "restore_operator_not_authorized"
    TARGET_NOT_SUSPENDED = "restore_target_not_suspended"
    UNSUPPORTED_HANDLER = "restore_handler_unsupported"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class StepContext:
    """Everything a handler may touch; nothing else exists for it."""

    run_id: str
    component_id: str
    target_tenant_id: str
    object_prefix: str
    payload_digest: Digest | None
    records: tuple[dict[str, object], ...]


class RestoreHandler(Protocol):
    """A versioned component restore port; must be idempotent."""

    def __call__(self, context: StepContext) -> Digest: ...


def configuration_fixture_handler(context: StepContext) -> Digest:
    """Reference handler: the minimal configuration/policy fixture.

    Accepts only the declared minimal fixture shape (string-keyed records
    with scalar values); writes nothing outside the declared context.
    """

    import hashlib
    import json

    for record in context.records:
        if not isinstance(record, dict) or not record:
            raise PortabilityRestoreError(PortabilityRestoreError.UNSUPPORTED_HANDLER)
        for key, value in record.items():
            if not isinstance(key, str) or not isinstance(value, (str, int, float, bool)):
                raise PortabilityRestoreError(PortabilityRestoreError.UNSUPPORTED_HANDLER)
    canonical = json.dumps(
        sorted(context.records, key=lambda item: json.dumps(item, sort_keys=True)),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(
        f"{context.target_tenant_id}:{context.component_id}:{canonical}".encode()
    ).hexdigest()


class ObjectArtifactsPort(Protocol):
    """The only outward write surface a reference handler may use."""

    def write_object(self, prefix: str, name: str, data: bytes) -> Digest: ...


def object_artifacts_handler(port: ObjectArtifactsPort) -> RestoreHandler:
    """Reference handler: object artifacts under the run's dedicated prefix."""

    import hashlib
    import json

    def handler(context: StepContext) -> Digest:
        digests: list[str] = []
        for index, record in enumerate(context.records):
            name = f"{context.component_id}/{index:08d}.json"
            data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
            digests.append(port.write_object(context.object_prefix, name, data))
        return hashlib.sha256(":".join(digests).encode()).hexdigest()

    return handler


@dataclass(frozen=True)
class HandlerRegistry:
    """Handlers bound to exact component ids; absent ids block their steps."""

    handlers: dict[str, RestoreHandler]

    def for_component(self, component_id: str) -> RestoreHandler | None:
        return self.handlers.get(component_id)


def _dependency_order(manifest_components) -> list[str]:
    """Topological order over depends_on; unknown dependencies first."""

    by_id = {component.component_id: component for component in manifest_components}
    order: list[str] = []
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visited:
            return
        visited.add(component_id)
        component = by_id.get(component_id)
        if component is not None:
            for dependency in component.depends_on:
                visit(dependency)
        order.append(component_id)

    for component in manifest_components:
        visit(component.component_id)
    return [component_id for component_id in order if component_id in by_id]


def start_restore_run(
    session: Session,
    *,
    plan: RestorePlan,
    acknowledgement: PlanAcknowledgement,
    target_tenant_id: str,
    target_tenant_status: str,
    manifest_components,
    acknowledged_by: str,
    authorized_by: str,
    authorize: Callable[[str], bool],
) -> PortabilityRestoreRunRecord:
    """Persist a new run (or resume an identical interrupted generation)."""

    if acknowledgement.plan_digest != plan.plan_digest:
        raise PortabilityRestoreError(PortabilityRestoreError.PLAN_MISMATCH)
    if acknowledgement.acknowledged_by != acknowledged_by:
        raise PortabilityRestoreError(PortabilityRestoreError.PLAN_MISMATCH)
    if not authorize(authorized_by):
        raise PortabilityRestoreError(PortabilityRestoreError.OPERATOR_UNAUTHORIZED)
    if target_tenant_status != "suspended":
        raise PortabilityRestoreError(PortabilityRestoreError.TARGET_NOT_SUSPENDED)

    existing = session.scalar(
        select(PortabilityRestoreRunRecord)
        .where(
            PortabilityRestoreRunRecord.target_tenant_id == target_tenant_id,
            PortabilityRestoreRunRecord.bundle_digest == plan.bundle_digest,
            PortabilityRestoreRunRecord.plan_digest == plan.plan_digest,
        )
        .order_by(PortabilityRestoreRunRecord.generation.desc())
        .limit(1)
        .with_for_update()
    )
    if existing is not None and existing.state in {
        RUN_STATE_PENDING,
        RUN_STATE_RUNNING,
        RUN_STATE_QUARANTINED,
    }:
        # Resume: only interrupted work (failed for a retryable reason) goes
        # back to pending; missing-handler blocks stay blocked until an
        # operator registers the handler.
        for step in session.scalars(
            select(PortabilityRestoreStepRecord).where(
                PortabilityRestoreStepRecord.run_id == existing.id,
                PortabilityRestoreStepRecord.state == STEP_STATE_FAILED,
            )
        ):
            if existing.steps_failed.get(step.component_id) != "missing_handler":
                step.state = STEP_STATE_PENDING
                existing.steps_failed.pop(step.component_id, None)
        return existing

    from datetime import UTC, datetime

    now = datetime.now(UTC)
    generation = (existing.generation + 1) if existing is not None else 1
    run = PortabilityRestoreRunRecord(
        target_tenant_id=target_tenant_id,
        bundle_digest=plan.bundle_digest,
        plan_digest=plan.plan_digest,
        generation=generation,
        state=RUN_STATE_PENDING,
        acknowledged_by=acknowledgement.acknowledged_by,
        acknowledged_at=now,
        authorized_by=authorized_by,
        authorized_at=now,
        steps_completed=[],
        steps_failed={},
        fenced=False,
    )
    session.add(run)
    session.flush()
    by_id = {component.component_id: component for component in manifest_components}
    for sequence, component_id in enumerate(
        _dependency_order(manifest_components)
    ):
        if by_id[component_id].decision != "restore":
            continue
        session.add(
            PortabilityRestoreStepRecord(
                run_id=run.id,
                component_id=component_id,
                sequence=sequence,
                state=STEP_STATE_PENDING,
            )
        )
    session.flush()
    return run


def claim_step(
    session: Session,
    *,
    run_id: str,
    component_id: str,
    worker_id: str,
    authorize: Callable[[str], bool],
) -> PortabilityRestoreStepRecord:
    """Fence and claim one step; a second worker on the run is refused."""

    run = session.get(PortabilityRestoreRunRecord, run_id, with_for_update=True)
    if run is None:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    if run.fenced and run.current_step != component_id:
        raise PortabilityRestoreError(PortabilityRestoreError.FENCED)
    if not authorize(worker_id):
        raise PortabilityRestoreError(PortabilityRestoreError.OPERATOR_UNAUTHORIZED)
    if run.state not in {RUN_STATE_PENDING, RUN_STATE_RUNNING, RUN_STATE_QUARANTINED}:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    step = session.scalar(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run.id,
            PortabilityRestoreStepRecord.component_id == component_id,
        )
    )
    if step is None or step.state in {STEP_STATE_COMPLETED, STEP_STATE_BLOCKED}:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    run.fenced = True
    run.current_step = component_id
    run.state = RUN_STATE_RUNNING
    step.state = STEP_STATE_IN_PROGRESS
    step.attempts += 1
    session.flush()
    return step


def complete_step(
    session: Session,
    *,
    run_id: str,
    component_id: str,
    evidence_digest: Digest,
) -> PortabilityRestoreRunRecord:
    """Record step evidence and release the fence; idempotent on retry."""

    run = session.get(PortabilityRestoreRunRecord, run_id, with_for_update=True)
    if run is None:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    step = session.scalar(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run.id,
            PortabilityRestoreStepRecord.component_id == component_id,
        )
    )
    if step is None:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    if step.state == STEP_STATE_COMPLETED:
        return run
    step.state = STEP_STATE_COMPLETED
    step.evidence_digest = evidence_digest
    if component_id not in run.steps_completed:
        run.steps_completed = [*run.steps_completed, component_id]
    run.steps_failed.pop(component_id, None)
    # Reconciliation queries must observe this step's new state even under
    # autoflush=False sessions.
    session.flush()
    remaining = session.scalars(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run.id,
            PortabilityRestoreStepRecord.state.in_(
                [STEP_STATE_PENDING, STEP_STATE_IN_PROGRESS, STEP_STATE_FAILED, STEP_STATE_BLOCKED]
            ),
        )
    ).all()
    if not remaining:
        run.state = RUN_STATE_COMPLETED
        run.current_step = None
        run.fenced = False
    else:
        run.current_step = None
        run.fenced = False
    session.flush()
    return run


def fail_step(
    session: Session,
    *,
    run_id: str,
    component_id: str,
    failure_code: str,
) -> PortabilityRestoreRunRecord:
    """Quarantine the run on failure; crash-safe and resumable."""

    run = session.get(PortabilityRestoreRunRecord, run_id, with_for_update=True)
    if run is None:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    step = session.scalar(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run.id,
            PortabilityRestoreStepRecord.component_id == component_id,
        )
    )
    if step is None:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    step.state = STEP_STATE_FAILED
    step.failure_code = failure_code
    run.state = RUN_STATE_QUARANTINED
    run.steps_failed = {**run.steps_failed, component_id: failure_code}
    run.current_step = None
    run.fenced = False
    session.flush()
    return run


def block_unsupported_steps(
    session: Session,
    *,
    run_id: str,
    registry: HandlerRegistry,
    manifest_components,
) -> PortabilityRestoreRunRecord:
    """Mark steps without a registered handler as blocked, never restored."""

    run = session.get(PortabilityRestoreRunRecord, run_id, with_for_update=True)
    if run is None:
        raise PortabilityRestoreError(PortabilityRestoreError.NOT_RESUMABLE)
    by_id = {component.component_id: component for component in manifest_components}
    for component in manifest_components:
        if component.decision != "restore":
            continue
        if registry.for_component(component.component_id) is None:
            step = session.scalar(
                select(PortabilityRestoreStepRecord).where(
                    PortabilityRestoreStepRecord.run_id == run.id,
                    PortabilityRestoreStepRecord.component_id == component.component_id,
                )
            )
            if step is not None and step.state == STEP_STATE_PENDING:
                step.state = STEP_STATE_BLOCKED
                step.failure_code = "missing_handler"
                run.state = RUN_STATE_QUARANTINED
                run.steps_failed = {
                    **run.steps_failed,
                    component.component_id: "missing_handler",
                }
    session.flush()
    blocked = [
        component_id
        for component_id, component in by_id.items()
        if component.decision == "restore"
        and registry.for_component(component_id) is None
    ]
    if blocked and all(
        step.state in {STEP_STATE_BLOCKED, STEP_STATE_COMPLETED}
        for step in session.scalars(
            select(PortabilityRestoreStepRecord).where(
                PortabilityRestoreStepRecord.run_id == run.id
            )
        )
    ):
        run.state = RUN_STATE_QUARANTINED
    session.flush()
    return run


def activation_blockers(
    session: Session,
    *,
    run_id: str,
) -> tuple[str, ...]:
    """Exact reasons the restored tenant may not be enabled yet."""

    run = session.get(PortabilityRestoreRunRecord, run_id)
    if run is None:
        return ("run_not_found",)
    blockers: list[str] = []
    if run.state != RUN_STATE_COMPLETED:
        blockers.append(f"run_state:{run.state}")
    steps = session.scalars(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run.id
        )
    ).all()
    for step in steps:
        if step.state == STEP_STATE_BLOCKED:
            blockers.append(f"missing_handler:{step.component_id}")
        elif step.state in {STEP_STATE_FAILED, STEP_STATE_PENDING, STEP_STATE_IN_PROGRESS}:
            blockers.append(f"step_incomplete:{step.component_id}")
        elif step.state == STEP_STATE_COMPLETED and step.evidence_digest is None:
            blockers.append(f"missing_evidence:{step.component_id}")
    return tuple(blockers)


def resume_run_plan(
    manifest_components, run: PortabilityRestoreRunRecord
) -> list[str]:
    """The dependency-ordered list of components still to execute."""

    completed = set(run.steps_completed)
    blocked = {
        component_id
        for component_id, code in run.steps_failed.items()
        if code == "missing_handler"
    }
    return [
        component_id
        for component_id in _dependency_order(manifest_components)
        if component_id not in completed | blocked
    ]
