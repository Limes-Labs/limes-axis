"""agent registry reference record

Revision ID: 0024_agent_registry_reference
Revises: 0023_connector_registry_reference
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_agent_registry_reference"
down_revision: str | None = "0023_connector_registry_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_REGISTRY_PAYLOAD = {
    "tenant_id": "tenant_demo_manufacturing",
    "plant_name": "Ravenna Works",
    "scenario": "Plant Operations Cockpit",
    "as_of": "2026-06-21T16:30:00+02:00",
    "registry_status": "watch",
    "metrics": [
        {
            "label": "Registered Agents",
            "value": "4",
            "detail": "Governed L1-L2 agents in the manufacturing demo tenant",
            "status": "ready",
        },
        {
            "label": "Pending Proposals",
            "value": "4",
            "detail": "One brief proposal and three action proposals under owner review",
            "status": "watch",
        },
        {
            "label": "Approval Gates",
            "value": "3",
            "detail": "High and medium risk agent proposals require human owners",
            "status": "action_required",
        },
        {
            "label": "External Egress",
            "value": "0 allowed",
            "detail": "All demo agents remain inside the tenant boundary",
            "status": "ready",
        },
    ],
    "filter_options": {
        "domains": ["Maintenance", "Operations", "Quality", "Supply"],
        "autonomy_levels": ["L1", "L2"],
        "statuses": [
            "drafting_actions",
            "proposal_ready",
            "recommending",
            "waiting_for_approval",
        ],
        "model_policies": ["local-or-approved-provider", "no-external-egress"],
    },
    "agents": [
        {
            "agent_id": "agent_daily_brief",
            "name": "Daily Brief Agent",
            "domain": "Operations",
            "status": "recommending",
            "owner_role": "plant-operations-owner",
            "purpose": (
                "Summarize plant risks, pending workflow gates and audit evidence for owners."
            ),
            "policy_boundary": {
                "autonomy_level": "L1",
                "model_policy": "local-or-approved-provider",
                "external_egress_allowed": False,
                "max_action_level": "L1",
                "required_permissions": ["agents:read", "audit:read", "workflows:read"],
                "guardrails": [
                    "Summaries only; no action payload execution.",
                    "No external model egress unless tenant policy explicitly allows it.",
                    "Must cite workflow, approval or audit evidence for operational claims.",
                ],
            },
            "connected_systems": ["Axis Audit", "Temporal", "TypeDB Boundary"],
            "data_access": [
                "workflow summaries",
                "approval queue summaries",
                "audit event summaries",
                "ontology relationship summaries",
            ],
            "allowed_actions": [
                "Generate daily plant brief",
                "Rank open governance gates",
                "Prepare owner-facing evidence summary",
            ],
            "blocked_actions": [
                "Execute workflow signal",
                "Approve action payload",
                "Read unrestricted source-system records",
            ],
            "proposals": [
                {
                    "proposal_id": "proposal_daily_brief_20260621",
                    "action": "Generate daily plant brief",
                    "risk_level": "low",
                    "status": "ready_for_owner_review",
                    "approval_required": False,
                    "related_workflow_id": "wf_supplier_delay_review",
                    "related_approval_id": None,
                }
            ],
            "active_workflows": [
                "wf_supplier_delay_review",
                "wf_quality_hold_review",
            ],
            "pending_approvals": [],
            "last_audit_event": "audit_20260621_154000_ontology_read",
            "evidence_refs": [
                "wf_supplier_delay_review",
                "audit_20260621_154000_ontology_read",
            ],
        },
        {
            "agent_id": "agent_supply_risk",
            "name": "Supply Risk Agent",
            "domain": "Supply",
            "status": "waiting_for_approval",
            "owner_role": "plant-operations-owner",
            "purpose": "Detect supplier delay risk and draft governed supply actions.",
            "policy_boundary": {
                "autonomy_level": "L2",
                "model_policy": "no-external-egress",
                "external_egress_allowed": False,
                "max_action_level": "L2",
                "required_permissions": [
                    "agents:read",
                    "supply:read",
                    "approvals:supply:request",
                ],
                "guardrails": [
                    "Can draft action payloads, but cannot execute supplier changes.",
                    "High-risk supply actions require plant operations owner approval.",
                    "Must keep supplier and production context inside tenant boundary.",
                ],
            },
            "connected_systems": ["Supplier Portal", "MES", "ERP", "Axis Audit"],
            "data_access": [
                "inbound shipment status",
                "Line 2 packaging schedule",
                "rush order priority flag",
                "supply approval history",
            ],
            "allowed_actions": [
                "Draft expedite supplier batch action",
                "Prepare supplier delay evidence",
                "Request supply owner approval",
            ],
            "blocked_actions": [
                "Book priority freight",
                "Mutate supplier order",
                "Signal workflow completion",
            ],
            "proposals": [
                {
                    "proposal_id": "proposal_expedite_supplier_batch",
                    "action": "Expedite supplier batch",
                    "risk_level": "high",
                    "status": "approval_required",
                    "approval_required": True,
                    "related_workflow_id": "wf_supplier_delay_review",
                    "related_approval_id": "appr_expedite_supplier_batch",
                }
            ],
            "active_workflows": ["wf_supplier_delay_review"],
            "pending_approvals": ["appr_expedite_supplier_batch"],
            "last_audit_event": "audit_20260621_141200_agent_proposal",
            "evidence_refs": [
                "risk_supplier_delay",
                "asset_motors_batch",
                "audit_20260621_141200_agent_proposal",
            ],
        },
        {
            "agent_id": "agent_quality_risk",
            "name": "Quality Risk Agent",
            "domain": "Quality",
            "status": "drafting_actions",
            "owner_role": "quality-owner",
            "purpose": ("Review quality drift evidence and draft quality hold recommendations."),
            "policy_boundary": {
                "autonomy_level": "L2",
                "model_policy": "no-external-egress",
                "external_egress_allowed": False,
                "max_action_level": "L2",
                "required_permissions": [
                    "agents:read",
                    "quality:read",
                    "approvals:quality:request",
                ],
                "guardrails": [
                    "Can draft quality hold recommendations, but cannot release or hold batches.",
                    "Quality evidence must stay inside approved tenant systems.",
                    "External model egress is blocked by default for quality evidence.",
                ],
            },
            "connected_systems": ["QMS", "MES", "ERP", "Axis Audit"],
            "data_access": [
                "sample inspection variance",
                "batch genealogy",
                "customer order priority",
                "quality proposal audit trail",
            ],
            "allowed_actions": [
                "Draft quality hold proposal",
                "Prepare evidence for quality owner",
                "Request quality owner review",
            ],
            "blocked_actions": [
                "Release batch",
                "Place batch on hold without approval",
                "Use external model provider for quality data",
            ],
            "proposals": [
                {
                    "proposal_id": "proposal_quality_hold_batch_q_1842",
                    "action": "Place Batch Q-1842 on quality hold",
                    "risk_level": "high",
                    "status": "review_required",
                    "approval_required": True,
                    "related_workflow_id": "wf_quality_hold_review",
                    "related_approval_id": "appr_quality_hold_batch",
                }
            ],
            "active_workflows": ["wf_quality_hold_review"],
            "pending_approvals": ["appr_quality_hold_batch"],
            "last_audit_event": "audit_20260621_134400_quality_proposal",
            "evidence_refs": [
                "risk_quality_drift",
                "asset_batch_q_1842",
                "audit_20260621_133900_egress_blocked",
            ],
        },
        {
            "agent_id": "agent_maintenance_planner",
            "name": "Maintenance Planner Agent",
            "domain": "Maintenance",
            "status": "proposal_ready",
            "owner_role": "maintenance-owner",
            "purpose": (
                "Draft maintenance schedule changes while preserving service-window policy."
            ),
            "policy_boundary": {
                "autonomy_level": "L2",
                "model_policy": "local-or-approved-provider",
                "external_egress_allowed": False,
                "max_action_level": "L2",
                "required_permissions": [
                    "agents:read",
                    "maintenance:read",
                    "approvals:maintenance:request",
                ],
                "guardrails": [
                    "Can draft schedule shifts, but cannot mutate CMMS state.",
                    "Service-window policy must be checked before owner review.",
                    "Schedule changes require maintenance owner approval.",
                ],
            },
            "connected_systems": ["CMMS", "MES", "ERP", "Axis Audit"],
            "data_access": [
                "Press 4 maintenance window",
                "rush order schedule",
                "service interval tolerance",
                "maintenance proposal audit trail",
            ],
            "allowed_actions": [
                "Draft maintenance reschedule proposal",
                "Prepare service-window evidence",
                "Request maintenance owner review",
            ],
            "blocked_actions": [
                "Mutate CMMS schedule",
                "Delay maintenance beyond policy",
                "Close workflow without owner signal",
            ],
            "proposals": [
                {
                    "proposal_id": "proposal_shift_press_4_maintenance",
                    "action": "Shift Press 4 maintenance window",
                    "risk_level": "medium",
                    "status": "proposal_ready",
                    "approval_required": True,
                    "related_workflow_id": "wf_maintenance_reschedule",
                    "related_approval_id": "appr_shift_maintenance_window",
                }
            ],
            "active_workflows": ["wf_maintenance_reschedule"],
            "pending_approvals": ["appr_shift_maintenance_window"],
            "last_audit_event": "audit_20260621_151800_maintenance_proposal",
            "evidence_refs": [
                "risk_maintenance_window",
                "asset_press_4",
                "audit_20260621_151800_maintenance_proposal",
            ],
        },
    ],
    "registry_notes": [
        "This public agent registry seed is read-only and synthetic.",
        "Agents can draft or recommend inside their autonomy level, but cannot mutate systems.",
        "External model egress is disabled unless tenant policy explicitly enables it.",
        (
            "A production action registry, runtime execution and persisted agent state "
            "remain Platform work."
        ),
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
                "surface": "agents",
                "reference_id": "manufacturing-agent-registry",
                "status": "active",
                "source": "bootstrap",
                "version": "2026-06-22",
                "payload": AGENT_REGISTRY_PAYLOAD,
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
            "AND surface = 'agents' "
            "AND reference_id = 'manufacturing-agent-registry'"
        )
    )
