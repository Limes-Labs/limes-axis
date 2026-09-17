"""Contract tests for the #878 resumable restore runner."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from test_portability_validator import (  # repo test-reuse convention
    _AXIS_VERSION,
    _TRUSTED_KEY,
    _bundle,
    _manifest,
)

from axis_api.models import Base, PortabilityRestoreStepRecord
from axis_api.portability_restore_runner import (
    RUN_STATE_COMPLETED,
    RUN_STATE_QUARANTINED,
    RUN_STATE_RUNNING,
    HandlerRegistry,
    PortabilityRestoreError,
    activation_blockers,
    block_unsupported_steps,
    claim_step,
    complete_step,
    configuration_fixture_handler,
    fail_step,
    resume_run_plan,
    start_restore_run,
)
from axis_api.portability_validator import (
    acknowledge_restore_plan,
    validate_bundle,
)

_TARGET = "tenant-restore-beta"
_AUTHORIZE = lambda _subject: True  # noqa: E731


def _plan():
    return validate_bundle(
        _bundle(_manifest()),
        trusted_signer_key_ids=frozenset({_TRUSTED_KEY}),
        supported_axis_versions=(_AXIS_VERSION,),
    )


def _components(manifest=None):
    manifest = manifest or _manifest()
    return manifest.components


def _acknowledgement(plan):
    return acknowledge_restore_plan(
        plan,
        acknowledged_exclusions=plan.exclusions(),
        acknowledged_by="operator:restore",
        acknowledged_at="2026-09-16T08:00:00Z",
    )


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    database = tmp_path_factory.mktemp("restore-runner") / "runner.sqlite"
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        yield db


@pytest.fixture
def plan():
    return _plan()


@pytest.fixture
def components():
    return _components()


def _start(session: Session, plan, components, **overrides: object):
    values: dict[str, object] = {
        "plan": plan,
        "acknowledgement": _acknowledgement(plan),
        "target_tenant_id": f"tenant-restore-{uuid4().hex[:12]}",
        "target_tenant_status": "suspended",
        "manifest_components": components,
        "acknowledged_by": "operator:restore",
        "authorized_by": "operator:restore",
        "authorize": _AUTHORIZE,
    }
    values.update(overrides)
    return start_restore_run(session, **values)  # type: ignore[arg-type]


def _step(session: Session, run_id, component_id: str) -> PortabilityRestoreStepRecord:
    return session.scalar(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run_id,
            PortabilityRestoreStepRecord.component_id == component_id,
        )
    )


def _evidence(component_id: str = "ontology") -> str:
    return configuration_fixture_handler(
        type(
            "Ctx",
            (),
            {
                "run_id": str(uuid4()),
                "component_id": component_id,
                "target_tenant_id": _TARGET,
                "object_prefix": "prefix",
                "payload_digest": None,
                "records": ({"key": "value"},),
            },
        )()
    )


# --- AC: minimal-fixture restore into an isolated suspended target -------------


def test_run_starts_with_restore_only_steps(session, plan, components) -> None:
    run = _start(session, plan, components)
    assert run.state == "pending"
    assert run.generation == 1
    assert {step.component_id for step in session.scalars(
        select(PortabilityRestoreStepRecord).where(
            PortabilityRestoreStepRecord.run_id == run.id
        )
    )} == {"ontology", "audit-ledger", "object-store"}


def test_non_suspended_target_is_refused(session, plan, components) -> None:
    with pytest.raises(PortabilityRestoreError) as blocked:
        _start(session, plan, components, target_tenant_status="active")
    assert blocked.value.code == PortabilityRestoreError.TARGET_NOT_SUSPENDED


def test_revoked_operator_rights_fail_closed(session, plan, components) -> None:
    with pytest.raises(PortabilityRestoreError) as blocked:
        _start(session, plan, components, authorize=lambda _subject: False)
    assert blocked.value.code == PortabilityRestoreError.OPERATOR_UNAUTHORIZED


def test_mismatched_acknowledgement_is_refused(session, plan, components) -> None:
    other_plan = validate_bundle(
        _bundle(_manifest(decisions={"object-store": "exclude"})),
        trusted_signer_key_ids=frozenset({_TRUSTED_KEY}),
        supported_axis_versions=(_AXIS_VERSION,),
    )
    other = acknowledge_restore_plan(
        other_plan,
        acknowledged_exclusions=other_plan.exclusions(),
        acknowledged_by="operator:restore",
        acknowledged_at="2026-09-16T08:00:00Z",
    )
    with pytest.raises(PortabilityRestoreError) as blocked:
        _start(session, plan, components, acknowledgement=other)
    assert blocked.value.code == PortabilityRestoreError.PLAN_MISMATCH


# --- AC: fenced execution; one worker owns the run -----------------------------


def test_two_workers_cannot_claim_the_same_run(session, plan, components) -> None:
    run = _start(session, plan, components)
    claim_step(
        session, run_id=run.id, component_id="ontology",
        worker_id="worker:a", authorize=_AUTHORIZE,
    )
    with pytest.raises(PortabilityRestoreError) as blocked:
        claim_step(
            session, run_id=run.id, component_id="audit-ledger",
            worker_id="worker:b", authorize=_AUTHORIZE,
        )
    assert blocked.value.code == PortabilityRestoreError.FENCED


def test_completed_step_cannot_be_reclaimed(session, plan, components) -> None:
    run = _start(session, plan, components)
    claim_step(
        session, run_id=run.id, component_id="ontology",
        worker_id="worker:a", authorize=_AUTHORIZE,
    )
    complete_step(
        session, run_id=run.id, component_id="ontology",
        evidence_digest=_evidence("ontology"),
    )
    with pytest.raises(PortabilityRestoreError) as blocked:
        claim_step(
            session, run_id=run.id, component_id="ontology",
            worker_id="worker:a", authorize=_AUTHORIZE,
        )
    assert blocked.value.code == PortabilityRestoreError.NOT_RESUMABLE


def test_revoked_rights_block_step_claim(session, plan, components) -> None:
    run = _start(session, plan, components)
    with pytest.raises(PortabilityRestoreError) as blocked:
        claim_step(
            session, run_id=run.id, component_id="ontology",
            worker_id="worker:b", authorize=lambda _subject: False,
        )
    assert blocked.value.code == PortabilityRestoreError.OPERATOR_UNAUTHORIZED


# --- AC: idempotent retries; failures quarantine and resume --------------------


def test_completion_is_idempotent_on_retry(session, plan, components) -> None:
    run = _start(session, plan, components)
    claim_step(
        session, run_id=run.id, component_id="ontology",
        worker_id="worker:a", authorize=_AUTHORIZE,
    )
    digest = _evidence("ontology")
    complete_step(session, run_id=run.id, component_id="ontology", evidence_digest=digest)
    complete_step(session, run_id=run.id, component_id="ontology", evidence_digest=digest)
    step = _step(session, run.id, "ontology")
    assert step.state == "completed"
    assert step.evidence_digest == digest


def test_failure_quarantines_and_resume_reuses_the_run(session, plan, components) -> None:
    target = f"tenant-restore-{uuid4().hex[:12]}"
    run = _start(session, plan, components, target_tenant_id=target)
    claim_step(
        session, run_id=run.id, component_id="ontology",
        worker_id="worker:a", authorize=_AUTHORIZE,
    )
    fail_step(
        session, run_id=run.id, component_id="ontology",
        failure_code="object_write_conflict",
    )
    session.refresh(run)
    assert run.state == RUN_STATE_QUARANTINED
    resumed = _start(session, plan, components, target_tenant_id=target)
    assert resumed.id == run.id
    assert resumed.state == RUN_STATE_QUARANTINED
    assert _step(session, resumed.id, "ontology").state == "pending"
    remaining = resume_run_plan(components, resumed)
    assert remaining[0] == "ontology"


def test_missing_handler_blocks_step_and_never_completes_the_run(
    session, plan, components
) -> None:
    run = _start(session, plan, components, target_tenant_id=f"tenant-restore-{uuid4().hex[:12]}")
    block_unsupported_steps(
        session, run_id=run.id,
        registry=HandlerRegistry(handlers={}),
        manifest_components=components,
    )
    blocked = _step(session, run.id, "ontology")
    assert blocked.state == "blocked"
    assert blocked.failure_code == "missing_handler"
    session.refresh(run)
    assert run.state == RUN_STATE_QUARANTINED


def test_blocked_run_has_activation_blockers(session, plan, components) -> None:
    run = _start(session, plan, components, target_tenant_id=f"tenant-restore-{uuid4().hex[:12]}")
    block_unsupported_steps(
        session, run_id=run.id,
        registry=HandlerRegistry(handlers={}),
        manifest_components=components,
    )
    blockers = activation_blockers(session, run_id=run.id)
    assert "missing_handler:ontology" in blockers
    assert f"run_state:{RUN_STATE_QUARANTINED}" in blockers


def test_incomplete_run_has_activation_blockers(session, plan, components) -> None:
    run = _start(session, plan, components)
    claim_step(
        session, run_id=run.id, component_id="ontology",
        worker_id="worker:a", authorize=_AUTHORIZE,
    )
    fail_step(session, run_id=run.id, component_id="ontology", failure_code="checksum")
    blockers = activation_blockers(session, run_id=run.id)
    assert "step_incomplete:ontology" in blockers


def test_completed_run_clears_activation_blockers(session, plan, components) -> None:
    run = _start(session, plan, components)
    for component_id in ("ontology", "audit-ledger", "object-store"):
        claim_step(
            session, run_id=run.id, component_id=component_id,
            worker_id="worker:a", authorize=_AUTHORIZE,
        )
        complete_step(
            session, run_id=run.id, component_id=component_id,
            evidence_digest=_evidence(component_id),
        )
    session.refresh(run)
    assert run.state == RUN_STATE_COMPLETED
    assert activation_blockers(session, run_id=run.id) == ()
    assert resume_run_plan(components, run) == []


# --- AC: only identical digests resume; changed bundles take a new generation ---


def test_changed_plan_starts_a_new_generation(session, plan, components) -> None:
    run = _start(session, plan, components)
    other = validate_bundle(
        _bundle(_manifest(decisions={"object-store": "exclude"})),
        trusted_signer_key_ids=frozenset({_TRUSTED_KEY}),
        supported_axis_versions=(_AXIS_VERSION,),
    )
    changed = _start(session, other, _components(_manifest(decisions={"object-store": "exclude"})))
    assert changed.id != run.id
    assert changed.generation == 1
    assert changed.plan_digest != run.plan_digest


def test_running_run_with_same_digest_is_reused(session, plan, components) -> None:
    target = f"tenant-restore-{uuid4().hex[:12]}"
    run = _start(session, plan, components, target_tenant_id=target)
    claim_step(
        session, run_id=run.id, component_id="ontology",
        worker_id="worker:a", authorize=_AUTHORIZE,
    )
    again = _start(session, plan, components, target_tenant_id=target)
    assert again.id == run.id
    assert again.state == RUN_STATE_RUNNING
    assert _step(session, again.id, "ontology").state == "in_progress"


def test_missing_handler_block_survives_resume(session, plan, components) -> None:
    target = f"tenant-restore-{uuid4().hex[:12]}"
    run = _start(session, plan, components, target_tenant_id=target)
    block_unsupported_steps(
        session, run_id=run.id,
        registry=HandlerRegistry(handlers={}),
        manifest_components=components,
    )
    again = _start(session, plan, components, target_tenant_id=target)
    assert again.id == run.id
    assert _step(session, again.id, "ontology").state == "blocked"
