from datetime import UTC, datetime
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.manufacturing_operations import (
    ManufacturingNotificationAcknowledgementRequest,
    ManufacturingNotificationQuery,
    ManufacturingOperationQuery,
    ManufacturingOperationsSnapshotQuery,
    build_manufacturing_notification_center,
    build_manufacturing_operations_snapshot,
    query_manufacturing_operations_dataset,
    record_manufacturing_notification_acknowledgement,
)
from axis_api.models import Base
from axis_api.persistence import (
    ApprovalRecordCreate,
    AxisPersistenceRepository,
    ManufacturingDailyBriefCreate,
    ManufacturingOperationRecordCreate,
    ManufacturingRiskScenarioCreate,
    WorkflowRunCreate,
)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def seed_operation_records(repository: AxisPersistenceRepository) -> None:
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="order_rush_4812",
            domain="Production",
            record_type="production_order",
            source_system="ERP",
            status="action_required",
            owner_role="plant-operations-owner",
            related_asset="asset_line_2_packaging",
            workflow_id="wf_supplier_delay_review",
            risk_level="high",
            occurred_at=datetime(2026, 6, 21, 13, 45, tzinfo=UTC),
            payload={
                "order_number": "PO-4812",
                "planned_line": "Line 2 Packaging",
                "blocked_by": ["material_lot_motors_7741"],
            },
            evidence_refs=["erp:orders:PO-4812"],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="batch_q_1842_quality",
            domain="Quality",
            record_type="quality_batch",
            source_system="QMS",
            status="watch",
            owner_role="quality-owner",
            related_asset="asset_batch_q_1842",
            workflow_id="wf_quality_hold_review",
            risk_level="high",
            occurred_at=datetime(2026, 6, 21, 13, 35, tzinfo=UTC),
            payload={
                "batch": "Q-1842",
                "inspection_variance_ppm": 37,
                "deviation_waiver": "not_released",
            },
            evidence_refs=["qms:inspection:Q-1842"],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_other",
            record_id="other_order",
            domain="Production",
            record_type="production_order",
            source_system="ERP",
            status="ready",
            owner_role="other-owner",
            occurred_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            payload={"order_number": "OTHER"},
            evidence_refs=["erp:orders:OTHER"],
        )
    )


def test_repository_lists_manufacturing_operations_tenant_scoped(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_operation_records(repository)
        records = repository.list_manufacturing_operation_records(
            tenant_id="tenant_demo_manufacturing"
        )

    assert [record.record_id for record in records] == [
        "order_rush_4812",
        "batch_q_1842_quality",
    ]
    assert all(record.tenant_id == "tenant_demo_manufacturing" for record in records)


def test_query_manufacturing_operations_dataset_filters_by_domain(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_operation_records(repository)
        dataset = query_manufacturing_operations_dataset(
            repository,
            ManufacturingOperationQuery(
                tenant_id="tenant_demo_manufacturing",
                domain="Quality",
            ),
        )

    assert dataset.tenant_id == "tenant_demo_manufacturing"
    assert dataset.domains == ["Quality"]
    assert dataset.source_systems == ["QMS"]
    assert dataset.metrics[0].label == "Operational Records"
    assert dataset.metrics[0].value == "1"
    assert dataset.records[0].record_id == "batch_q_1842_quality"
    assert dataset.records[0].payload["deviation_waiver"] == "not_released"
    assert "tenant_other" not in dataset.model_dump_json()
    assert "password" not in dataset.model_dump_json().lower()
    assert "secret" not in dataset.model_dump_json().lower()


def test_manufacturing_operations_endpoint_returns_persisted_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_operation_records(repository)

    client = TestClient(app)
    response = client.get("/demo/manufacturing/operations?status=action_required")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][1]["label"] == "Action Required"
    assert body["metrics"][1]["value"] == "1"
    assert [record["record_id"] for record in body["records"]] == ["order_rush_4812"]
    assert body["records"][0]["source_system"] == "ERP"


def seed_snapshot_records(repository: AxisPersistenceRepository) -> None:
    seed_operation_records(repository)
    workflow = WorkflowRunCreate(
        tenant_id="tenant_demo_manufacturing",
        workflow_id="wf_supplier_delay_review",
        name="Supplier delay review",
        domain="Supply",
        state="awaiting_approval",
        status="action_required",
        owner_role="supply-planning-owner",
        runtime="temporal",
        adapter="axis-temporal-adapter",
        autonomy_level="L2",
        started_at=datetime(2026, 6, 21, 14, 10, tzinfo=UTC),
        eta="2026-06-21T18:00:00Z",
        blocker="Owner approval required before expedite.",
        objective="Review supplier delay before production impact.",
        current_step="Waiting for expedite approval",
        related_risk="risk_supplier_delay",
        related_assets=["asset_line_2_packaging"],
        inputs=["order_rush_4812"],
        proposed_outputs=["request_supplier_expedite"],
        pending_signals=[
            {
                "signal": "approval.decision",
                "approval_id": "appr_supplier_expedite",
                "required_role": "supply-planning-owner",
                "status": "pending",
            }
        ],
        controls=["human_approval_required"],
        audit_scope="workflow:wf_supplier_delay_review",
        replay_ready=True,
    )
    repository.create_workflow_run(workflow)
    repository.create_approval_record(
        ApprovalRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            approval_id="appr_supplier_expedite",
            workflow_id="wf_supplier_delay_review",
            action_id="request_supplier_expedite",
            requested_by="agent_supplier_delay",
            owner_role="supply-planning-owner",
            risk_level="high",
            payload={"record_ids": ["order_rush_4812"]},
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="agent_supplier_delay",
            event_type="manufacturing.risk_scenario.generated",
            payload={
                "scenario_id": "supplier_delay_demo",
                "domain": "Supply",
                "risk_level": "high",
            },
        )
    )
    repository.create_manufacturing_daily_brief(
        ManufacturingDailyBriefCreate(
            tenant_id="tenant_demo_manufacturing",
            brief_id="brief_20260621_demo",
            idempotency_key="brief-demo-key",
            brief_date="2026-06-21",
            requested_by="agent_daily_brief",
            required_scopes=["briefs:generate", "audit:read", "workflows:read"],
            source_record_ids=["order_rush_4812", "batch_q_1842_quality"],
            summary_payload={
                "summary": {
                    "record_count": 2,
                    "action_required_count": 1,
                    "watch_count": 1,
                },
                "generation_boundary": "deterministic_persisted_records",
            },
            permission_decision={"allowed": True, "reason": "all_required_scopes_present"},
        )
    )
    repository.create_manufacturing_risk_scenario(
        ManufacturingRiskScenarioCreate(
            tenant_id="tenant_demo_manufacturing",
            scenario_id="supplier_delay_demo",
            idempotency_key="supplier-delay-demo-key",
            domain="Supply",
            risk_level="high",
            requested_by="agent_supplier_delay",
            owner_role="supply-planning-owner",
            workflow_ids=["wf_supplier_delay_review"],
            source_record_ids=["order_rush_4812"],
            scenario_payload={
                "headline": "Supplier delay risk is high.",
                "generation_boundary": "deterministic_persisted_supply_records",
            },
            permission_decision={"allowed": True, "reason": "all_required_scopes_present"},
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_other",
            record_id="other_snapshot_record",
            domain="Supply",
            record_type="material_lot",
            source_system="Supplier Portal",
            status="action_required",
            owner_role="other-owner",
            occurred_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            payload={"supplier": "Other"},
            evidence_refs=["supplier_portal:shipment:OTHER"],
        )
    )


def test_build_manufacturing_operations_snapshot_aggregates_persisted_paths(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_snapshot_records(repository)
        snapshot = build_manufacturing_operations_snapshot(
            repository,
            ManufacturingOperationsSnapshotQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert snapshot.tenant_id == "tenant_demo_manufacturing"
    assert snapshot.metrics[0].label == "Operation Records"
    assert snapshot.metrics[0].value == "2"
    assert snapshot.metrics[1].label == "Open Workflows"
    assert snapshot.metrics[1].value == "1"
    assert snapshot.domain_snapshots[0].domain == "Production"
    assert snapshot.domain_snapshots[0].action_required_count == 1
    assert snapshot.domain_snapshots[1].domain == "Quality"
    assert snapshot.latest_daily_briefs[0].brief_id == "brief_20260621_demo"
    assert snapshot.risk_scenarios[0].scenario_id == "supplier_delay_demo"
    assert snapshot.active_workflows[0].workflow_id == "wf_supplier_delay_review"
    assert snapshot.pending_approvals[0].approval_id == "appr_supplier_expedite"
    assert snapshot.recent_audit_events[0].event_type == (
        "manufacturing.risk_scenario.generated"
    )
    serialized = snapshot.model_dump_json().lower()
    assert "tenant_other" not in serialized
    assert "password" not in serialized
    assert "secret" not in serialized


def test_manufacturing_operations_snapshot_endpoint_returns_persisted_composition(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_snapshot_records(AxisPersistenceRepository(session))

    client = TestClient(app)
    response = client.get("/demo/manufacturing/operations/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "2"
    assert body["latest_daily_briefs"][0]["brief_id"] == "brief_20260621_demo"
    assert body["risk_scenarios"][0]["domain"] == "Supply"
    assert body["active_workflows"][0]["state"] == "awaiting_approval"
    assert body["pending_approvals"][0]["status"] == "pending"


def test_build_manufacturing_notification_center_derives_from_persisted_snapshot(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_snapshot_records(repository)
        center = build_manufacturing_notification_center(
            repository,
            ManufacturingNotificationQuery(
                tenant_id="tenant_demo_manufacturing",
                notification_limit=4,
            ),
        )

    assert center.tenant_id == "tenant_demo_manufacturing"
    assert center.generation_boundary == "derived_from_persisted_operations_snapshot"
    assert center.unread_count == 4
    assert center.action_required_count >= 1
    assert center.watch_count >= 1
    assert [notification.severity for notification in center.notifications][:2] == [
        "action_required",
        "action_required",
    ]

    categories = {notification.category for notification in center.notifications}
    assert {"operations", "approval", "workflow"} <= categories
    approval = next(
        notification
        for notification in center.notifications
        if notification.category == "approval"
    )
    assert approval.related_approval_id == "appr_supplier_expedite"
    assert approval.route == "/approvals"
    assert approval.action_label == "Review approval"

    serialized = center.model_dump_json().lower()
    assert "tenant_other" not in serialized
    assert "password" not in serialized
    assert "secret" not in serialized


def test_platform_notification_acknowledgement_is_persisted_and_audited(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_snapshot_records(repository)
        center = build_manufacturing_notification_center(
            repository,
            ManufacturingNotificationQuery(
                tenant_id="tenant_demo_manufacturing",
                actor_id="plant-operations-owner-role",
                notification_limit=4,
            ),
        )
        notification = center.notifications[0]

        result = record_manufacturing_notification_acknowledgement(
            repository,
            notification.notification_id,
            ManufacturingNotificationAcknowledgementRequest(
                tenant_id="tenant_demo_manufacturing",
                actor_id="plant-operations-owner-role",
                actor_scopes=["notifications:acknowledge"],
                reason="Reviewed by operations lead during the morning control-room check.",
            ),
        )
        refreshed = build_manufacturing_notification_center(
            repository,
            ManufacturingNotificationQuery(
                tenant_id="tenant_demo_manufacturing",
                actor_id="plant-operations-owner-role",
                notification_limit=4,
            ),
        )

    acknowledged = next(
        item
        for item in refreshed.notifications
        if item.notification_id == notification.notification_id
    )
    assert result.notification_id == notification.notification_id
    assert result.state == "acknowledged"
    assert result.read_state == "acknowledged"
    assert result.audit_event_type == "platform.notification.acknowledged"
    assert result.audit_event_id is not None
    assert acknowledged.read_state == "acknowledged"
    assert acknowledged.acknowledged_by == "plant-operations-owner-role"
    assert acknowledged.acknowledgement_reason.startswith("Reviewed by operations")
    assert refreshed.unread_count == center.unread_count - 1
    assert "browser-local fallback" not in " ".join(refreshed.notes).lower()


def test_manufacturing_notifications_endpoint_returns_platform_read_model(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_snapshot_records(AxisPersistenceRepository(session))

    client = TestClient(app)
    response = client.get("/demo/manufacturing/notifications?notification_limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["unread_count"] == 3
    assert body["notifications"][0]["read_state"] == "unread"
    assert body["notifications"][0]["route"] in {"/", "/approvals", "/workflows"}
    assert body["generation_boundary"] == "derived_from_persisted_operations_snapshot"


def test_manufacturing_notification_acknowledgement_endpoint_requires_scope_and_persists(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_snapshot_records(repository)
        center = build_manufacturing_notification_center(
            repository,
            ManufacturingNotificationQuery(
                tenant_id="tenant_demo_manufacturing",
                actor_id="plant-operations-owner-role",
                notification_limit=3,
            ),
        )
        notification_id = center.notifications[0].notification_id

    client = TestClient(app)
    denied = client.post(
        f"/demo/manufacturing/notifications/{notification_id}/acknowledgement",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": ["audit:read"],
            "reason": "Operator reviewed the signal.",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PERMISSION_DENIED"

    response = client.post(
        f"/demo/manufacturing/notifications/{notification_id}/acknowledgement",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "actor_id": "plant-operations-owner-role",
            "actor_scopes": ["notifications:acknowledge"],
            "reason": "Operator reviewed the signal.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["notification_id"] == notification_id
    assert body["read_state"] == "acknowledged"
    assert body["audit_event_type"] == "platform.notification.acknowledged"

    refreshed = client.get(
        "/demo/manufacturing/notifications"
        "?notification_limit=3&actor_id=plant-operations-owner-role"
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    acknowledged = next(
        item
        for item in refreshed_body["notifications"]
        if item["notification_id"] == notification_id
    )
    assert acknowledged["read_state"] == "acknowledged"
    assert acknowledged["acknowledged_by"] == "plant-operations-owner-role"
    assert refreshed_body["unread_count"] == 2


def test_manufacturing_demo_readiness_endpoint_reports_demo_ready_evidence(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_snapshot_records(AxisPersistenceRepository(session))

    client = TestClient(app)
    response = client.get("/demo/manufacturing/demo-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["readiness_status"] == "watch"
    assert body["generation_boundary"] == "derived_from_persisted_demo_evidence"
    assert body["summary"] == (
        "Axis is ready for structured SME feedback and enterprise evaluation walkthroughs, "
        "with production-readiness limits made explicit."
    )
    assert [track["name"] for track in body["tracks"]] == [
        "SME feedback demo",
        "Enterprise evaluation walkthrough",
    ]
    assert body["tracks"][0]["status"] == "ready"
    assert body["tracks"][1]["status"] == "watch"

    checks_by_id = {check["check_id"]: check for check in body["checks"]}
    assert checks_by_id["operations_snapshot"]["status"] == "ready"
    assert checks_by_id["operations_snapshot"]["observed_count"] == 2
    assert checks_by_id["generated_artifacts"]["observed_count"] == 2
    assert checks_by_id["human_approval_gates"]["observed_count"] == 1
    assert checks_by_id["audit_evidence"]["observed_count"] >= 1
    assert checks_by_id["production_readiness_limits"]["status"] == "watch"

    assert "tenant_other" not in str(body)
    assert "password" not in str(body).lower()
    assert "secret" not in str(body).lower()


def test_openapi_exposes_manufacturing_operations_snapshot_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/operations/snapshot" in paths
    assert "/demo/manufacturing/notifications" in paths
    assert "/demo/manufacturing/demo-readiness" in paths
    assert "get" in paths["/demo/manufacturing/operations/snapshot"]
    assert "get" in paths["/demo/manufacturing/notifications"]
    assert "post" in paths["/demo/manufacturing/notifications/{notification_id}/acknowledgement"]
    assert "get" in paths["/demo/manufacturing/demo-readiness"]


def test_manufacturing_operation_bootstrap_records_cover_operational_domains() -> None:
    migration = run_path("migrations/versions/0031_manufacturing_operation_records.py")
    records = migration["MANUFACTURING_OPERATION_RECORDS"]

    assert {record["domain"] for record in records} == {
        "Maintenance",
        "Production",
        "Quality",
        "Supply",
    }
    assert {record["record_type"] for record in records} >= {
        "machine_status",
        "maintenance_window",
        "material_lot",
        "production_order",
        "quality_batch",
        "supplier_status",
    }
    assert all(record["evidence_refs"] for record in records)
    assert "password" not in str(records).lower()
    assert "secret" not in str(records).lower()
