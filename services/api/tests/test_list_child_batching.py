"""Child-row reads on list projections are batched (issue #942).

``GET /operations/workflows/runs`` issued one timeline query per run and kept
the 100 oldest timeline events, dropping the newest. The credential-handle
registry issued one rotation query per handle.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.connector_credential_handles import (
    ConnectorCredentialHandleQuery,
    build_connector_credential_handle_registry,
)
from axis_api.db import session_scope
from axis_api.models import Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialRotationCreate,
    TenantCreate,
    WorkflowRunCreate,
    WorkflowTimelineEventCreate,
)
from axis_api.workflow_queries import WorkflowRunQuery, query_persisted_workflow_runs

TENANT = "tenant-batching"
OTHER_TENANT = "tenant-other"
T0 = datetime(2026, 10, 19, tzinfo=UTC)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with session_scope(sessionmaker(bind=engine)) as session:
        for tenant in (TENANT, OTHER_TENANT):
            AxisPersistenceRepository(session).create_tenant(
                TenantCreate(tenant_id=tenant, display_name="Plant", created_by="test")
            )
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


def _count_selects(session: Session, table: str) -> list[str]:
    statements: list[str] = []

    @event.listens_for(session.get_bind(), "before_cursor_execute")
    def record(_conn, _cursor, statement, _params, _context, _executemany):
        is_read = statement.lstrip().upper().startswith(("SELECT", "WITH"))
        if is_read and f"FROM {table}" in statement:
            statements.append(statement)

    return statements


def _seed_workflows(
    factory: sessionmaker[Session], *, runs: int, events_per_run: int, tenant: str = TENANT
) -> None:
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        for index in range(runs):
            workflow_id = f"wf-{index}"
            repository.create_workflow_run(
                WorkflowRunCreate(
                    tenant_id=tenant,
                    workflow_id=workflow_id,
                    name=f"Workflow {index}",
                    domain="supply",
                    state="running",
                    status="ready",
                    owner_role="planner",
                    runtime="temporal",
                    adapter="axis",
                    autonomy_level="L1",
                    started_at=T0 + timedelta(minutes=index),
                    eta="1h",
                    objective="Keep the line running",
                    current_step="review",
                    related_risk="risk-1",
                    related_assets=["asset-1"],
                    inputs=["input-1"],
                    proposed_outputs=["output-1"],
                    pending_signals=[
                        {
                            "signal": "approval.decision",
                            "required_role": "planner",
                            "status": "waiting",
                            "approval_id": f"appr-{index}",
                        }
                    ],
                    controls=["control-1"],
                    audit_scope="workflow",
                )
            )
            for sequence in range(1, events_per_run + 1):
                repository.append_workflow_timeline_event(
                    WorkflowTimelineEventCreate(
                        tenant_id=tenant,
                        workflow_id=workflow_id,
                        sequence=sequence,
                        event=f"event-{sequence}",
                        occurred_at=T0 + timedelta(seconds=sequence),
                        actor="worker",
                        result="ok",
                        summary=f"step {sequence}",
                    )
                )


def test_workflow_run_list_reads_timelines_in_one_query(factory) -> None:
    _seed_workflows(factory, runs=12, events_per_run=3)
    _seed_workflows(factory, runs=2, events_per_run=2, tenant=OTHER_TENANT)

    with session_scope(factory) as session:
        statements = _count_selects(session, "workflow_timeline_events")
        console = query_persisted_workflow_runs(
            AxisPersistenceRepository(session), WorkflowRunQuery(tenant_id=TENANT)
        )

    assert len(console.workflow_runs) == 12
    assert len(statements) == 1
    for run in console.workflow_runs:
        assert [step.event for step in run.timeline] == ["event-1", "event-2", "event-3"]


def test_workflow_timeline_keeps_the_newest_events_in_order(factory) -> None:
    _seed_workflows(factory, runs=1, events_per_run=130)

    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        single = repository.list_workflow_timeline_events(TENANT, "wf-0")
        console = query_persisted_workflow_runs(repository, WorkflowRunQuery(tenant_id=TENANT))

    expected = [f"event-{sequence}" for sequence in range(31, 131)]
    assert [record.event for record in single] == expected
    assert [step.event for step in console.workflow_runs[0].timeline] == expected


def _seed_handles(factory: sessionmaker[Session], *, handles: int, rotations: int) -> None:
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        for index in range(handles):
            handle_id = f"handle-{index}"
            repository.create_connector_credential_handle(
                ConnectorCredentialHandleCreate(
                    tenant_id=TENANT,
                    connector_id="connector-a",
                    handle_id=handle_id,
                    display_name=f"Handle {index}",
                    secret_provider="vault",
                    secret_ref=f"vault://axis/{handle_id}",
                    purpose="source_ingestion",
                    rotation_interval_days=30,
                    created_by="test",
                )
            )
            for rotation in range(rotations):
                repository.record_connector_credential_rotation(
                    ConnectorCredentialRotationCreate(
                        tenant_id=TENANT,
                        handle_id=handle_id,
                        rotated_by="operator",
                        rotated_at=T0 + timedelta(days=rotation),
                        evidence_ref=f"evidence-{index}-{rotation}",
                    )
                )


def test_credential_handle_registry_reads_rotations_in_one_query(factory) -> None:
    _seed_handles(factory, handles=10, rotations=3)

    with session_scope(factory) as session:
        statements = _count_selects(session, "connector_credential_rotations")
        registry = build_connector_credential_handle_registry(
            AxisPersistenceRepository(session),
            ConnectorCredentialHandleQuery(tenant_id=TENANT),
        )

    assert len(registry.handles) == 10
    assert len(statements) == 1


def test_credential_rotation_batch_matches_the_per_handle_read(factory) -> None:
    _seed_handles(factory, handles=3, rotations=30)

    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        batched = repository.list_connector_credential_rotations_for_handles(
            TENANT, ["handle-0", "handle-1", "handle-2", "handle-missing"], limit=25
        )
        for handle_id in ("handle-0", "handle-1", "handle-2"):
            single = repository.list_connector_credential_rotations(TENANT, handle_id, limit=25)
            assert [row.id for row in batched[handle_id]] == [row.id for row in single]
        assert batched.get("handle-missing", []) == []
        assert repository.list_connector_credential_rotations_for_handles(
            OTHER_TENANT, ["handle-0"], limit=25
        ) == {}
