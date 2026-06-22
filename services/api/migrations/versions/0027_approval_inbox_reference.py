"""approval inbox reference record

Revision ID: 0027_approval_inbox_reference
Revises: 0026_workflow_console_reference
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_approval_inbox_reference"
down_revision: str | None = "0026_workflow_console_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPROVAL_INBOX_PAYLOAD = {
    "tenant_id": "tenant_demo_manufacturing",
    "plant_name": "Ravenna Works",
    "scenario": "Plant Operations Cockpit",
    "as_of": "2026-06-21T16:30:00+02:00",
    "queue_status": "action_required",
    "policy_notes": [
        "Critical operations require a human owner role before workflow mutation.",
        "External model egress remains blocked unless policy explicitly enables it.",
        "Approval decisions must become append-only audit events before execution.",
        "This public approval inbox reference is read-only until a decision is submitted.",
    ],
    "approvals": [
        {
            "approval_id": "appr_expedite_supplier_batch",
            "action": "Expedite supplier batch",
            "risk_level": "high",
            "status": "pending",
            "requested_by": "supply-risk-agent",
            "owner_role": "plant-operations-owner",
            "due": "Today 17:30",
            "workflow_id": "wf_supplier_delay_review",
            "domain": "Supply",
            "summary": (
                "Expedite the delayed inbound motors batch so Line 2 packaging can "
                "keep the rush order window."
            ),
            "evidence": [
                "Inbound motors batch is 18 hours late against the production window.",
                "Line 2 packaging has no equivalent substitute batch in the reference data.",
                "Supplier portal confirms an available priority freight slot.",
            ],
            "data_accessed": [
                "Supplier Portal: inbound shipment status",
                "MES: Line 2 packaging schedule",
                "ERP: rush order priority flag",
                "Axis Audit: supply-risk-agent proposal trail",
            ],
            "risks": [
                "Expedite fee may exceed standard logistics budget.",
                "Priority freight could still miss the production window.",
                "Approval without audit evidence would violate the action policy.",
            ],
            "alternatives": [
                "Hold the rush order and preserve standard freight.",
                "Shift Line 2 to a lower-priority packaging batch.",
                "Request supplier split shipment before approving expedite.",
            ],
            "estimated_cost": "EUR 4,800 priority freight exposure",
            "model_policy": "no-external-egress",
            "required_permission": "approvals:supply:decide",
            "audit_event_preview": {
                "event": "approval.decision.recorded",
                "actor_role": "plant-operations-owner",
                "scope": "wf_supplier_delay_review",
                "result": "workflow_signal_ready",
            },
            "decision_options": [
                {
                    "decision": "approve",
                    "label": "Approve",
                    "consequence": "Signal the workflow adapter that the action may proceed.",
                },
                {
                    "decision": "reject",
                    "label": "Reject",
                    "consequence": "Record a denial and keep the workflow blocked.",
                },
                {
                    "decision": "request_changes",
                    "label": "Request changes",
                    "consequence": "Return the proposal to the agent with required review notes.",
                },
            ],
        },
        {
            "approval_id": "appr_quality_hold_batch",
            "action": "Place Batch Q-1842 on quality hold",
            "risk_level": "high",
            "status": "pending",
            "requested_by": "quality-risk-agent",
            "owner_role": "quality-owner",
            "due": "Today 16:45",
            "workflow_id": "wf_quality_hold_review",
            "domain": "Quality",
            "summary": (
                "Hold Batch Q-1842 while the quality team reviews inspection "
                "variance and containment impact."
            ),
            "evidence": [
                "Two samples crossed the inspection variance watch threshold.",
                "QMS notes show no released deviation waiver for the batch.",
                "The batch is linked to a customer order with regulated documentation.",
            ],
            "data_accessed": [
                "QMS: sample inspection variance",
                "MES: batch genealogy",
                "ERP: customer order priority",
                "Axis Audit: quality-risk-agent proposal trail",
            ],
            "risks": [
                "Holding the batch may delay a customer shipment.",
                "Releasing the batch without review may create quality exposure.",
                "Escalation requires quality role approval, not autonomous execution.",
            ],
            "alternatives": [
                "Increase sampling without placing the full batch on hold.",
                "Release unaffected lots while holding only the suspect segment.",
                "Request manual quality engineer review before any hold signal.",
            ],
            "estimated_cost": "EUR 12,000 shipment delay exposure",
            "model_policy": "no-external-egress",
            "required_permission": "approvals:quality:decide",
            "audit_event_preview": {
                "event": "approval.decision.recorded",
                "actor_role": "quality-owner",
                "scope": "wf_quality_hold_review",
                "result": "quality_hold_signal_ready",
            },
            "decision_options": [
                {
                    "decision": "approve",
                    "label": "Approve",
                    "consequence": "Signal the workflow adapter that the action may proceed.",
                },
                {
                    "decision": "reject",
                    "label": "Reject",
                    "consequence": "Record a denial and keep the workflow blocked.",
                },
                {
                    "decision": "request_changes",
                    "label": "Request changes",
                    "consequence": "Return the proposal to the agent with required review notes.",
                },
            ],
        },
        {
            "approval_id": "appr_shift_maintenance_window",
            "action": "Shift Press 4 maintenance window",
            "risk_level": "medium",
            "status": "pending",
            "requested_by": "maintenance-planner-agent",
            "owner_role": "maintenance-owner",
            "due": "Tomorrow 08:30",
            "workflow_id": "wf_maintenance_reschedule",
            "domain": "Maintenance",
            "summary": (
                "Move the Press 4 maintenance slot to avoid overlap with a rush "
                "production order while keeping the service interval inside policy."
            ),
            "evidence": [
                "Planned downtime overlaps a rush order by 90 minutes.",
                "CMMS service interval remains within tolerance after the proposed shift.",
                "Production schedule has an alternate window tomorrow morning.",
            ],
            "data_accessed": [
                "CMMS: Press 4 maintenance plan",
                "MES: rush order schedule",
                "ERP: production priority",
                "Axis Audit: maintenance-planner-agent proposal trail",
            ],
            "risks": [
                "Delaying maintenance may increase equipment risk.",
                "Moving the slot could collide with the next shift handoff.",
                "Planner approval is required before mutating the schedule.",
            ],
            "alternatives": [
                "Keep the original maintenance slot and delay the rush order.",
                "Perform a shorter inspection-only maintenance window.",
                "Escalate to plant operations for joint production review.",
            ],
            "estimated_cost": "No direct spend; production disruption risk",
            "model_policy": "local-or-approved-provider",
            "required_permission": "approvals:maintenance:decide",
            "audit_event_preview": {
                "event": "approval.decision.recorded",
                "actor_role": "maintenance-owner",
                "scope": "wf_maintenance_reschedule",
                "result": "maintenance_signal_ready",
            },
            "decision_options": [
                {
                    "decision": "approve",
                    "label": "Approve",
                    "consequence": "Signal the workflow adapter that the action may proceed.",
                },
                {
                    "decision": "reject",
                    "label": "Reject",
                    "consequence": "Record a denial and keep the workflow blocked.",
                },
                {
                    "decision": "request_changes",
                    "label": "Request changes",
                    "consequence": "Return the proposal to the agent with required review notes.",
                },
            ],
        },
    ],
}


def upgrade() -> None:
    reference_table = sa.table(
        "demo_reference_records",
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
                "surface": "approvals",
                "reference_id": "manufacturing-approval-inbox",
                "status": "active",
                "source": "bootstrap",
                "version": "2026-06-22",
                "payload": APPROVAL_INBOX_PAYLOAD,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM demo_reference_records "
            "WHERE tenant_id = 'tenant_demo_manufacturing' "
            "AND surface = 'approvals' "
            "AND reference_id = 'manufacturing-approval-inbox'"
        )
    )
