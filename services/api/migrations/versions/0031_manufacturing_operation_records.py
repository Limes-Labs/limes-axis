"""manufacturing operation records

Revision ID: 0031_manufacturing_operation_records
Revises: 0030_ontology_reference
Create Date: 2026-06-23
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_manufacturing_operation_records"
down_revision: str | None = "0030_ontology_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MANUFACTURING_OPERATION_RECORDS = [
    {
        "record_id": "order_rush_4812",
        "domain": "Production",
        "record_type": "production_order",
        "source_system": "ERP",
        "status": "action_required",
        "owner_role": "plant-operations-owner",
        "related_asset": "asset_line_2_packaging",
        "workflow_id": "wf_supplier_delay_review",
        "risk_level": "high",
        "occurred_at": datetime(2026, 6, 21, 13, 45, tzinfo=UTC),
        "payload": {
            "order_number": "PO-4812",
            "customer_priority": "rush",
            "due_at": "2026-06-22T18:00:00+02:00",
            "planned_line": "Line 2 Packaging",
            "required_materials": ["inbound_motors_batch"],
            "blocked_by": ["material_lot_motors_7741"],
        },
        "evidence_refs": [
            "erp:orders:PO-4812",
            "mes:line_schedule:line-2-packaging",
        ],
    },
    {
        "record_id": "material_lot_motors_7741",
        "domain": "Supply",
        "record_type": "material_lot",
        "source_system": "Supplier Portal",
        "status": "action_required",
        "owner_role": "supply-planning-owner",
        "related_asset": "asset_motors_batch",
        "workflow_id": "wf_supplier_delay_review",
        "risk_level": "high",
        "occurred_at": datetime(2026, 6, 21, 14, 5, tzinfo=UTC),
        "payload": {
            "supplier": "Adriatic Motors",
            "material": "Servo motor assembly",
            "quantity": 420,
            "delay_hours": 18,
            "expedite_slot": "2026-06-21T20:30:00+02:00",
            "line_impact": "Line 2 Packaging cannot complete PO-4812 on schedule.",
        },
        "evidence_refs": [
            "supplier_portal:shipment:AM-7741",
            "axis:audit:agent_supply_risk:proposal",
        ],
    },
    {
        "record_id": "supplier_adriatic_motors",
        "domain": "Supply",
        "record_type": "supplier_status",
        "source_system": "Supplier Portal",
        "status": "watch",
        "owner_role": "supply-planning-owner",
        "related_asset": "asset_motors_batch",
        "workflow_id": "wf_supplier_delay_review",
        "risk_level": "medium",
        "occurred_at": datetime(2026, 6, 21, 12, 30, tzinfo=UTC),
        "payload": {
            "supplier": "Adriatic Motors",
            "service_level": "at_risk",
            "open_shipments": 2,
            "confirmed_expedite_capacity": True,
            "contractual_penalty_exposure_eur": 4800,
        },
        "evidence_refs": [
            "supplier_portal:supplier:adriatic-motors",
            "erp:supplier_scorecard:adriatic-motors",
        ],
    },
    {
        "record_id": "batch_q_1842_quality",
        "domain": "Quality",
        "record_type": "quality_batch",
        "source_system": "QMS",
        "status": "watch",
        "owner_role": "quality-owner",
        "related_asset": "asset_batch_q_1842",
        "workflow_id": "wf_quality_hold_review",
        "risk_level": "high",
        "occurred_at": datetime(2026, 6, 21, 13, 35, tzinfo=UTC),
        "payload": {
            "batch": "Q-1842",
            "inspection_variance_ppm": 37,
            "watch_threshold_ppm": 25,
            "samples_above_threshold": 2,
            "deviation_waiver": "not_released",
            "containment_recommendation": "quality_owner_review",
        },
        "evidence_refs": [
            "qms:inspection:Q-1842",
            "mes:batch_genealogy:Q-1842",
        ],
    },
    {
        "record_id": "press_4_machine_status",
        "domain": "Maintenance",
        "record_type": "machine_status",
        "source_system": "CMMS",
        "status": "watch",
        "owner_role": "maintenance-owner",
        "related_asset": "asset_press_4",
        "workflow_id": "wf_maintenance_reschedule",
        "risk_level": "medium",
        "occurred_at": datetime(2026, 6, 21, 11, 55, tzinfo=UTC),
        "payload": {
            "machine": "Press 4",
            "service_interval_hours_remaining": 16,
            "planned_downtime": "2026-06-22T07:30:00+02:00",
            "overlap_minutes_with_rush_order": 90,
            "reschedule_window": "2026-06-22T10:30:00+02:00",
        },
        "evidence_refs": [
            "cmms:asset:press-4",
            "mes:schedule:press-4",
        ],
    },
    {
        "record_id": "maintenance_window_press_4",
        "domain": "Maintenance",
        "record_type": "maintenance_window",
        "source_system": "CMMS",
        "status": "watch",
        "owner_role": "maintenance-owner",
        "related_asset": "asset_press_4",
        "workflow_id": "wf_maintenance_reschedule",
        "risk_level": "medium",
        "occurred_at": datetime(2026, 6, 21, 12, 10, tzinfo=UTC),
        "payload": {
            "window_id": "MW-PRESS-4-20260622",
            "current_start": "2026-06-22T07:30:00+02:00",
            "proposed_start": "2026-06-22T10:30:00+02:00",
            "policy": "service interval remains inside tolerance",
            "approval_required": True,
        },
        "evidence_refs": [
            "cmms:maintenance_window:MW-PRESS-4-20260622",
            "axis:audit:maintenance-planner-agent:proposal",
        ],
    },
]


def upgrade() -> None:
    table_name = "manufacturing_operation_records"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("record_id", sa.String(length=180), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("record_type", sa.String(length=80), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("owner_role", sa.String(length=160), nullable=False),
        sa.Column("related_asset", sa.String(length=180), nullable=True),
        sa.Column("workflow_id", sa.String(length=160), nullable=True),
        sa.Column("risk_level", sa.String(length=40), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "record_id",
            name="uq_manufacturing_operation_records_tenant_record",
        ),
    )
    for column_name in (
        "tenant_id",
        "record_id",
        "domain",
        "record_type",
        "source_system",
        "status",
        "owner_role",
        "related_asset",
        "workflow_id",
        "risk_level",
    ):
        op.create_index(
            f"ix_manufacturing_operation_records_{column_name}",
            table_name,
            [column_name],
        )

    operation_table = sa.table(
        table_name,
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("tenant_id", sa.String(length=80)),
        sa.column("record_id", sa.String(length=180)),
        sa.column("domain", sa.String(length=80)),
        sa.column("record_type", sa.String(length=80)),
        sa.column("source_system", sa.String(length=120)),
        sa.column("status", sa.String(length=80)),
        sa.column("owner_role", sa.String(length=160)),
        sa.column("related_asset", sa.String(length=180)),
        sa.column("workflow_id", sa.String(length=160)),
        sa.column("risk_level", sa.String(length=40)),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
        sa.column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("evidence_refs", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime(2026, 6, 23, 0, 0, tzinfo=UTC)
    op.bulk_insert(
        operation_table,
        [
            {
                "id": uuid4(),
                "tenant_id": "tenant_demo_manufacturing",
                "created_at": now,
                "updated_at": now,
                **record,
            }
            for record in MANUFACTURING_OPERATION_RECORDS
        ],
    )


def downgrade() -> None:
    op.drop_table("manufacturing_operation_records")
