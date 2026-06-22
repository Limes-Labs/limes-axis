"""demo reference records

Revision ID: 0022_demo_reference_records
Revises: 0021_connector_egress_policies
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_demo_reference_records"
down_revision: str | None = "0021_connector_egress_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MANUFACTURING_OVERVIEW_PAYLOAD = {
    "tenant_id": "tenant_demo_manufacturing",
    "plant_name": "Ravenna Works",
    "scenario": "Plant Operations Cockpit",
    "as_of": "2026-06-21T16:30:00+02:00",
    "metrics": [
        {
            "label": "Workflow Load",
            "value": "7 active",
            "detail": "3 production, 2 quality, 1 maintenance, 1 supplier flow",
            "status": "watch",
        },
        {
            "label": "Approvals",
            "value": "3 pending",
            "detail": "2 high-risk actions require human approval today",
            "status": "action_required",
        },
        {
            "label": "Agents",
            "value": "4 governed",
            "detail": "All agents remain within L0-L2 autonomy for the demo tenant",
            "status": "ready",
        },
        {
            "label": "Audit",
            "value": "128 events",
            "detail": "Reads, proposals, workflow signals and decisions are recorded",
            "status": "ready",
        },
    ],
    "risk_signals": [
        {
            "title": "Supplier delay may block Line 2 packaging",
            "domain": "Supply",
            "severity": "action_required",
            "owner_role": "supply-planning-owner",
            "evidence": "Inbound motors batch is 18 hours late against the production window.",
            "related_asset": "line-2-packaging",
        },
        {
            "title": "Quality drift detected on Batch Q-1842",
            "domain": "Quality",
            "severity": "watch",
            "owner_role": "quality-owner",
            "evidence": "Inspection variance crossed the watch threshold for two samples.",
            "related_asset": "batch-q-1842",
        },
        {
            "title": "Press 4 maintenance window is at risk",
            "domain": "Maintenance",
            "severity": "watch",
            "owner_role": "maintenance-owner",
            "evidence": "Planned downtime overlaps with a rush order unless rescheduled.",
            "related_asset": "press-4",
        },
    ],
    "workflows": [
        {
            "workflow_id": "wf_supplier_delay_review",
            "name": "Supplier Delay Review",
            "state": "waiting_for_approval",
            "owner_role": "plant-operations-owner",
            "blocker": "Approve expedite action or adjust production schedule",
            "eta": "Today 18:00",
        },
        {
            "workflow_id": "wf_quality_hold_review",
            "name": "Quality Hold Review",
            "state": "investigating",
            "owner_role": "quality-owner",
            "blocker": None,
            "eta": "Today 16:45",
        },
        {
            "workflow_id": "wf_maintenance_reschedule",
            "name": "Maintenance Reschedule",
            "state": "proposal_ready",
            "owner_role": "maintenance-owner",
            "blocker": "Human review required before schedule mutation",
            "eta": "Tomorrow 09:00",
        },
    ],
    "approvals": [
        {
            "approval_id": "appr_expedite_supplier_batch",
            "action": "Expedite supplier batch",
            "risk_level": "high",
            "requested_by": "supply-risk-agent",
            "owner_role": "plant-operations-owner",
            "due": "Today 17:30",
        },
        {
            "approval_id": "appr_quality_hold_batch",
            "action": "Place Batch Q-1842 on quality hold",
            "risk_level": "high",
            "requested_by": "quality-risk-agent",
            "owner_role": "quality-owner",
            "due": "Today 16:45",
        },
        {
            "approval_id": "appr_shift_maintenance_window",
            "action": "Shift Press 4 maintenance window",
            "risk_level": "medium",
            "requested_by": "maintenance-planner-agent",
            "owner_role": "maintenance-owner",
            "due": "Tomorrow 08:30",
        },
    ],
    "agents": [
        {
            "agent_id": "agent_daily_brief",
            "name": "Daily Brief Agent",
            "autonomy_level": "L1",
            "status": "recommending",
            "proposals_pending": 1,
            "model_policy": "local-or-approved-provider",
        },
        {
            "agent_id": "agent_quality_risk",
            "name": "Quality Risk Agent",
            "autonomy_level": "L2",
            "status": "drafting_actions",
            "proposals_pending": 1,
            "model_policy": "no-external-egress",
        },
        {
            "agent_id": "agent_supply_risk",
            "name": "Supply Risk Agent",
            "autonomy_level": "L2",
            "status": "waiting_for_approval",
            "proposals_pending": 1,
            "model_policy": "no-external-egress",
        },
        {
            "agent_id": "agent_maintenance_planner",
            "name": "Maintenance Planner Agent",
            "autonomy_level": "L2",
            "status": "proposal_ready",
            "proposals_pending": 1,
            "model_policy": "local-or-approved-provider",
        },
    ],
    "audit_events": [
        {
            "event": "agent.proposal.created",
            "actor": "supply-risk-agent",
            "scope": "wf_supplier_delay_review",
            "result": "approval_required",
        },
        {
            "event": "policy.egress.blocked",
            "actor": "model-router",
            "scope": "quality-risk-agent",
            "result": "blocked_by_default",
        },
        {
            "event": "workflow.signal.requested",
            "actor": "plant-operations-owner-role",
            "scope": "wf_quality_hold_review",
            "result": "recorded",
        },
    ],
}


def upgrade() -> None:
    table_name = "demo_reference_records"
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("surface", sa.String(length=120), nullable=False),
        sa.Column("reference_id", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "surface",
            "reference_id",
            name="uq_demo_reference_records_tenant_surface_reference",
        ),
    )
    for column_name in ("tenant_id", "surface", "reference_id", "status", "source"):
        op.create_index(f"ix_demo_reference_records_{column_name}", table_name, [column_name])

    reference_table = sa.table(
        table_name,
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("tenant_id", sa.String(length=80)),
        sa.column("surface", sa.String(length=120)),
        sa.column("reference_id", sa.String(length=180)),
        sa.column("status", sa.String(length=80)),
        sa.column("source", sa.String(length=120)),
        sa.column("version", sa.String(length=80)),
        sa.column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)
    op.bulk_insert(
        reference_table,
        [
            {
                "id": uuid4(),
                "tenant_id": "tenant_demo_manufacturing",
                "surface": "overview",
                "reference_id": "manufacturing-overview",
                "status": "active",
                "source": "bootstrap",
                "version": "2026-06-22",
                "payload": MANUFACTURING_OVERVIEW_PAYLOAD,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    table_name = "demo_reference_records"
    for column_name in ("source", "status", "reference_id", "surface", "tenant_id"):
        op.drop_index(f"ix_demo_reference_records_{column_name}", table_name=table_name)
    op.drop_table(table_name)
