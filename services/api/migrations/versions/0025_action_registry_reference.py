"""action registry reference record

Revision ID: 0025_action_registry_reference
Revises: 0024_agent_registry_reference
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_action_registry_reference"
down_revision: str | None = "0024_agent_registry_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTION_REGISTRY_PAYLOAD = {
    "tenant_id": "tenant_demo_manufacturing",
    "plant_name": "Ravenna Works",
    "scenario": "Plant Operations Cockpit",
    "as_of": "2026-06-21T16:30:00+02:00",
    "registry_status": "watch",
    "schema_version": "2026-06-21",
    "metrics": [
        {
            "label": "Registered Actions",
            "value": "4",
            "detail": "Typed action definitions for the manufacturing demo tenant",
            "status": "ready",
        },
        {
            "label": "Approval Required",
            "value": "3",
            "detail": "High and conditional actions are routed to owner review",
            "status": "action_required",
        },
        {
            "label": "Runtime Execution",
            "value": "0 live",
            "detail": "Public demo remains preview and dry-run only",
            "status": "watch",
        },
        {
            "label": "External Egress",
            "value": "0 allowed",
            "detail": "Action payloads stay inside the tenant boundary",
            "status": "ready",
        },
    ],
    "filter_options": {
        "domains": ["Maintenance", "Operations", "Quality", "Supply"],
        "risk_levels": ["high", "low", "medium"],
        "approval_modes": ["conditional", "not_required", "required"],
        "statuses": [
            "approval_required",
            "available_for_preview",
            "conditional_approval_required",
            "review_required",
        ],
    },
    "actions": [
        {
            "definition": {
                "action_id": "generate_daily_plant_brief",
                "display_name": "Generate daily plant brief",
                "domain": "Operations",
                "risk_level": "low",
                "approval_mode": "not_required",
                "input_schema": {
                    "type": "object",
                    "required": ["tenant_id", "scope", "evidence_refs"],
                    "properties": {
                        "tenant_id": {"type": "string"},
                        "scope": {"type": "string"},
                        "evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "output_schema": {
                    "type": "object",
                    "required": ["brief_id", "summary", "cited_evidence"],
                    "properties": {
                        "brief_id": {"type": "string"},
                        "summary": {"type": "string"},
                        "cited_evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "required_permissions": ["briefs:generate", "audit:read", "workflows:read"],
            },
            "description": (
                "Build a read-only daily plant brief from workflow, approval and audit evidence."
            ),
            "owner_role": "plant-operations-owner",
            "status": "available_for_preview",
            "side_effects": "No external mutation; produces owner-facing summary only.",
            "policy": {
                "approval_role": "plant-operations-owner",
                "autonomy_ceiling": "L1",
                "execution_mode": "preview_only",
                "runtime_adapter": "axis-action-preview",
                "audit_event_type": "action.preview.generated",
                "model_egress_policy": "local-or-approved-provider",
                "idempotency_required": False,
                "dry_run_supported": True,
            },
            "connected_agents": ["agent_daily_brief"],
            "workflow_bindings": [
                "wf_supplier_delay_review",
                "wf_quality_hold_review",
            ],
            "approval_refs": [],
            "guardrails": [
                "Must cite existing workflow, approval or audit evidence.",
                "Cannot approve or signal workflow state.",
                "External model egress remains blocked unless tenant policy allows it.",
            ],
            "validation_checks": [
                "tenant_id matches request context",
                "evidence_refs exist in accessible audit scope",
                "scope is limited to plant operations cockpit",
            ],
            "blocked_conditions": [
                "missing evidence references",
                "cross-tenant evidence requested",
                "unapproved external model route",
            ],
            "sample_input": {
                "tenant_id": "tenant_demo_manufacturing",
                "scope": "daily_operations",
                "evidence_refs": "wf_supplier_delay_review,audit_20260621_154000_ontology_read",
            },
            "sample_output": {
                "brief_id": "brief_20260621_demo",
                "summary": "Three governed operational risks require owner review.",
                "cited_evidence": "wf_supplier_delay_review,audit_20260621_154000_ontology_read",
            },
        },
        {
            "definition": {
                "action_id": "request_supplier_expedite",
                "display_name": "Request supplier expedite",
                "domain": "Supply",
                "risk_level": "high",
                "approval_mode": "required",
                "input_schema": {
                    "type": "object",
                    "required": [
                        "supplier_batch_id",
                        "target_arrival",
                        "reason",
                        "cost_ceiling_eur",
                    ],
                    "properties": {
                        "supplier_batch_id": {
                            "type": "string",
                            "x-axis-ontology-ref": True,
                        },
                        "target_arrival": {"type": "string"},
                        "reason": {"type": "string"},
                        "cost_ceiling_eur": {"type": "string"},
                    },
                },
                "output_schema": {
                    "type": "object",
                    "required": ["request_id", "approval_id", "audit_event_id"],
                    "properties": {
                        "request_id": {"type": "string"},
                        "approval_id": {"type": "string"},
                        "audit_event_id": {"type": "string"},
                    },
                },
                "required_permissions": ["supply:read", "approvals:supply:request"],
            },
            "description": "Prepare an expedite request for delayed inbound material.",
            "owner_role": "plant-operations-owner",
            "status": "approval_required",
            "side_effects": (
                "Would request supplier action after owner approval; demo is dry-run only."
            ),
            "policy": {
                "approval_role": "plant-operations-owner",
                "autonomy_ceiling": "L2",
                "execution_mode": "approval_gated_dry_run",
                "runtime_adapter": "axis-temporal-adapter",
                "audit_event_type": "action.proposal.created",
                "model_egress_policy": "no-external-egress",
                "idempotency_required": True,
                "dry_run_supported": True,
            },
            "connected_agents": ["agent_supply_risk"],
            "workflow_bindings": ["wf_supplier_delay_review"],
            "approval_refs": ["appr_expedite_supplier_batch"],
            "guardrails": [
                "High-risk supply action must enter approval inbox before execution.",
                "Agent can draft payload but cannot book priority freight.",
                "Cost ceiling and target arrival must be visible to the owner.",
            ],
            "validation_checks": [
                "supplier_batch_id maps to accessible supplier risk evidence",
                "cost_ceiling_eur is present",
                "approval role matches plant operations owner",
                "idempotency key exists before runtime signal",
            ],
            "blocked_conditions": [
                "missing approval",
                "external freight booking requested directly",
                "supplier batch outside tenant scope",
            ],
            "sample_input": {
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
            "sample_output": {
                "request_id": "act_supplier_expedite_preview",
                "approval_id": "appr_expedite_supplier_batch",
                "audit_event_id": "audit_20260621_141200_agent_proposal",
            },
        },
        {
            "definition": {
                "action_id": "place_quality_hold",
                "display_name": "Place quality hold",
                "domain": "Quality",
                "risk_level": "high",
                "approval_mode": "required",
                "input_schema": {
                    "type": "object",
                    "required": ["batch_id", "hold_reason", "evidence_refs"],
                    "properties": {
                        "batch_id": {"type": "string", "x-axis-ontology-ref": True},
                        "hold_reason": {"type": "string"},
                        "evidence_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "output_schema": {
                    "type": "object",
                    "required": ["hold_request_id", "approval_id", "audit_event_id"],
                    "properties": {
                        "hold_request_id": {"type": "string"},
                        "approval_id": {"type": "string"},
                        "audit_event_id": {"type": "string"},
                    },
                },
                "required_permissions": ["quality:read", "approvals:quality:request"],
            },
            "description": "Draft a quality hold proposal for owner review.",
            "owner_role": "quality-owner",
            "status": "review_required",
            "side_effects": ("Would hold a production batch only after quality owner approval."),
            "policy": {
                "approval_role": "quality-owner",
                "autonomy_ceiling": "L2",
                "execution_mode": "approval_gated_dry_run",
                "runtime_adapter": "axis-temporal-adapter",
                "audit_event_type": "action.proposal.created",
                "model_egress_policy": "no-external-egress",
                "idempotency_required": True,
                "dry_run_supported": True,
            },
            "connected_agents": ["agent_quality_risk"],
            "workflow_bindings": ["wf_quality_hold_review"],
            "approval_refs": ["appr_quality_hold_batch"],
            "guardrails": [
                "Quality evidence must remain inside tenant systems.",
                "Agent cannot release or hold a batch without owner decision.",
                "Proposal must include batch genealogy evidence.",
            ],
            "validation_checks": [
                "batch_id maps to accessible quality risk evidence",
                "evidence_refs include audit event and risk node",
                "approval role matches quality owner",
            ],
            "blocked_conditions": [
                "missing batch genealogy",
                "owner approval absent",
                "external model route requested for quality data",
            ],
            "sample_input": {
                "batch_id": "asset_batch_q_1842",
                "hold_reason": "Inspection variance crossed watch threshold",
                "evidence_refs": "risk_quality_drift,audit_20260621_134400_quality_proposal",
            },
            "sample_output": {
                "hold_request_id": "act_quality_hold_preview",
                "approval_id": "appr_quality_hold_batch",
                "audit_event_id": "audit_20260621_134400_quality_proposal",
            },
        },
        {
            "definition": {
                "action_id": "shift_maintenance_window",
                "display_name": "Shift maintenance window",
                "domain": "Maintenance",
                "risk_level": "medium",
                "approval_mode": "conditional",
                "input_schema": {
                    "type": "object",
                    "required": [
                        "asset_id",
                        "current_window",
                        "proposed_window",
                        "policy_check_id",
                    ],
                    "properties": {
                        "asset_id": {"type": "string", "x-axis-ontology-ref": True},
                        "current_window": {"type": "string"},
                        "proposed_window": {"type": "string"},
                        "policy_check_id": {"type": "string"},
                    },
                },
                "output_schema": {
                    "type": "object",
                    "required": ["proposal_id", "approval_id", "audit_event_id"],
                    "properties": {
                        "proposal_id": {"type": "string"},
                        "approval_id": {"type": "string"},
                        "audit_event_id": {"type": "string"},
                    },
                },
                "required_permissions": [
                    "maintenance:read",
                    "approvals:maintenance:request",
                ],
            },
            "description": "Draft a service-window-safe maintenance reschedule proposal.",
            "owner_role": "maintenance-owner",
            "status": "conditional_approval_required",
            "side_effects": ("Would update CMMS schedule only after policy and owner gates."),
            "policy": {
                "approval_role": "maintenance-owner",
                "autonomy_ceiling": "L2",
                "execution_mode": "conditional_approval_dry_run",
                "runtime_adapter": "axis-temporal-adapter",
                "audit_event_type": "action.proposal.created",
                "model_egress_policy": "local-or-approved-provider",
                "idempotency_required": True,
                "dry_run_supported": True,
            },
            "connected_agents": ["agent_maintenance_planner"],
            "workflow_bindings": ["wf_maintenance_reschedule"],
            "approval_refs": ["appr_shift_maintenance_window"],
            "guardrails": [
                "Service-window policy must pass before owner review.",
                "Agent cannot mutate CMMS schedule directly.",
                "Schedule shift must preserve maintenance interval tolerance.",
            ],
            "validation_checks": [
                "asset_id maps to accessible maintenance risk evidence",
                "policy_check_id is present",
                "proposed_window stays inside allowed service tolerance",
            ],
            "blocked_conditions": [
                "service-window policy failed",
                "maintenance owner approval absent",
                "CMMS mutation requested before workflow signal",
            ],
            "sample_input": {
                "asset_id": "asset_press_4",
                "current_window": "2026-06-22T09:00:00+02:00",
                "proposed_window": "2026-06-22T13:00:00+02:00",
                "policy_check_id": "service-window-policy",
            },
            "sample_output": {
                "proposal_id": "act_maintenance_shift_preview",
                "approval_id": "appr_shift_maintenance_window",
                "audit_event_id": "audit_20260621_151800_maintenance_proposal",
            },
        },
    ],
    "registry_notes": [
        "This public action registry reference record is safe for dry-run requests.",
        "Actions are typed and policy-gated, but live runtime execution is not enabled.",
        "High-risk actions require owner approval before any production signal.",
        "Action run requests can be persisted with idempotency and append-only audit.",
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
                "surface": "actions",
                "reference_id": "manufacturing-action-registry",
                "status": "active",
                "source": "bootstrap",
                "version": "2026-06-22",
                "payload": ACTION_REGISTRY_PAYLOAD,
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
            "AND surface = 'actions' "
            "AND reference_id = 'manufacturing-action-registry'"
        )
    )
