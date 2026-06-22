"""ontology reference record

Revision ID: 0030_ontology_reference
Revises: 0029_model_routing_reference
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_ontology_reference"
down_revision: str | None = "0029_model_routing_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ONTOLOGY_PAYLOAD = {
    "tenant_id": "tenant_demo_manufacturing",
    "plant_name": "Ravenna Works",
    "scenario": "Plant Operations Cockpit",
    "as_of": "2026-06-21T16:30:00+02:00",
    "nodes": [
        {
            "node_id": "org_ravenna_operations",
            "label": "Ravenna Operations",
            "node_type": "organization",
            "domain": "Operations",
            "status": "ready",
            "source_system": "Axis",
            "summary": "Demo tenant operating unit for the manufacturing reference scenario.",
        },
        {
            "node_id": "asset_ravenna_works",
            "label": "Ravenna Works",
            "node_type": "asset",
            "domain": "Plant",
            "status": "ready",
            "source_system": "MES",
            "summary": "Fictional plant used by the public Platform demo seed.",
        },
        {
            "node_id": "asset_line_2_packaging",
            "label": "Line 2 Packaging",
            "node_type": "asset",
            "domain": "Production",
            "status": "action_required",
            "source_system": "MES",
            "summary": "Packaging line exposed to supplier delay risk.",
        },
        {
            "node_id": "asset_press_4",
            "label": "Press 4",
            "node_type": "asset",
            "domain": "Maintenance",
            "status": "watch",
            "source_system": "CMMS",
            "summary": "Press with a maintenance window that may need rescheduling.",
        },
        {
            "node_id": "asset_batch_q_1842",
            "label": "Batch Q-1842",
            "node_type": "asset",
            "domain": "Quality",
            "status": "watch",
            "source_system": "QMS",
            "summary": "Batch with inspection variance above the watch threshold.",
        },
        {
            "node_id": "asset_motors_batch",
            "label": "Inbound Motors Batch",
            "node_type": "asset",
            "domain": "Supply",
            "status": "action_required",
            "source_system": "Supplier Portal",
            "summary": "Inbound component batch delayed against the production window.",
        },
        {
            "node_id": "risk_supplier_delay",
            "label": "Supplier Delay Risk",
            "node_type": "risk",
            "domain": "Supply",
            "status": "action_required",
            "source_system": "Axis",
            "summary": "Risk signal that may block Line 2 packaging.",
        },
        {
            "node_id": "risk_quality_drift",
            "label": "Quality Drift Risk",
            "node_type": "risk",
            "domain": "Quality",
            "status": "watch",
            "source_system": "Axis",
            "summary": "Risk signal generated from QMS inspection variance.",
        },
        {
            "node_id": "risk_maintenance_window",
            "label": "Maintenance Window Risk",
            "node_type": "risk",
            "domain": "Maintenance",
            "status": "watch",
            "source_system": "Axis",
            "summary": "Risk that planned downtime overlaps a rush order.",
        },
        {
            "node_id": "wf_supplier_delay_review",
            "label": "Supplier Delay Review",
            "node_type": "workflow",
            "domain": "Supply",
            "status": "action_required",
            "source_system": "Temporal",
            "summary": "Workflow waiting for a human decision on expedite or reschedule.",
        },
        {
            "node_id": "wf_quality_hold_review",
            "label": "Quality Hold Review",
            "node_type": "workflow",
            "domain": "Quality",
            "status": "watch",
            "source_system": "Temporal",
            "summary": "Workflow investigating whether the batch should be held.",
        },
        {
            "node_id": "wf_maintenance_reschedule",
            "label": "Maintenance Reschedule",
            "node_type": "workflow",
            "domain": "Maintenance",
            "status": "watch",
            "source_system": "Temporal",
            "summary": "Workflow preparing a schedule change for Press 4.",
        },
        {
            "node_id": "appr_expedite_supplier_batch",
            "label": "Expedite Supplier Batch",
            "node_type": "approval",
            "domain": "Supply",
            "status": "action_required",
            "source_system": "Axis",
            "summary": "High-risk approval gate for supplier expedite action.",
        },
        {
            "node_id": "appr_quality_hold_batch",
            "label": "Place Batch Q-1842 On Hold",
            "node_type": "approval",
            "domain": "Quality",
            "status": "action_required",
            "source_system": "Axis",
            "summary": "High-risk approval gate for quality hold action.",
        },
        {
            "node_id": "agent_supply_risk",
            "label": "Supply Risk Agent",
            "node_type": "agent",
            "domain": "Supply",
            "status": "action_required",
            "source_system": "Axis",
            "summary": "L2 agent that drafts supplier risk actions.",
        },
        {
            "node_id": "agent_quality_risk",
            "label": "Quality Risk Agent",
            "node_type": "agent",
            "domain": "Quality",
            "status": "watch",
            "source_system": "Axis",
            "summary": "L2 agent that drafts quality hold recommendations.",
        },
        {
            "node_id": "policy_external_egress",
            "label": "External Model Egress Policy",
            "node_type": "policy",
            "domain": "Security",
            "status": "ready",
            "source_system": "Axis",
            "summary": "Policy that blocks external model egress by default.",
        },
        {
            "node_id": "audit_policy_egress_blocked",
            "label": "Egress Blocked Audit Event",
            "node_type": "audit_event",
            "domain": "Security",
            "status": "ready",
            "source_system": "Axis Audit",
            "summary": "Evidence that the model router blocked external egress.",
        },
    ],
    "relationships": [
        {
            "relationship_id": "rel_org_owns_plant",
            "source_id": "org_ravenna_operations",
            "target_id": "asset_ravenna_works",
            "relation_type": "owns",
            "summary": "Operating unit owns the demo plant context.",
            "permission_scope": "operations:read",
        },
        {
            "relationship_id": "rel_plant_contains_line",
            "source_id": "asset_ravenna_works",
            "target_id": "asset_line_2_packaging",
            "relation_type": "contains",
            "summary": "Plant contains Line 2 packaging operations.",
            "permission_scope": "operations:read",
        },
        {
            "relationship_id": "rel_plant_contains_press",
            "source_id": "asset_ravenna_works",
            "target_id": "asset_press_4",
            "relation_type": "contains",
            "summary": "Plant contains Press 4 maintenance context.",
            "permission_scope": "maintenance:read",
        },
        {
            "relationship_id": "rel_supplier_batch_impacts_line",
            "source_id": "asset_motors_batch",
            "target_id": "asset_line_2_packaging",
            "relation_type": "impacts",
            "summary": "Delayed inbound batch may block the packaging line.",
            "permission_scope": "supply:read",
        },
        {
            "relationship_id": "rel_quality_batch_impacts_risk",
            "source_id": "asset_batch_q_1842",
            "target_id": "risk_quality_drift",
            "relation_type": "raises",
            "summary": "Inspection variance raises the quality drift risk.",
            "permission_scope": "quality:read",
        },
        {
            "relationship_id": "rel_supplier_risk_blocks_workflow",
            "source_id": "risk_supplier_delay",
            "target_id": "wf_supplier_delay_review",
            "relation_type": "drives",
            "summary": "Supplier delay risk drives the review workflow.",
            "permission_scope": "supply:read",
        },
        {
            "relationship_id": "rel_quality_risk_drives_workflow",
            "source_id": "risk_quality_drift",
            "target_id": "wf_quality_hold_review",
            "relation_type": "drives",
            "summary": "Quality drift risk drives the quality hold workflow.",
            "permission_scope": "quality:read",
        },
        {
            "relationship_id": "rel_maintenance_risk_drives_workflow",
            "source_id": "risk_maintenance_window",
            "target_id": "wf_maintenance_reschedule",
            "relation_type": "drives",
            "summary": "Maintenance risk drives the reschedule workflow.",
            "permission_scope": "maintenance:read",
        },
        {
            "relationship_id": "rel_supplier_workflow_requires_approval",
            "source_id": "wf_supplier_delay_review",
            "target_id": "appr_expedite_supplier_batch",
            "relation_type": "requires_approval",
            "summary": "Workflow cannot execute expedite action without approval.",
            "permission_scope": "approvals:read",
        },
        {
            "relationship_id": "rel_quality_workflow_requires_approval",
            "source_id": "wf_quality_hold_review",
            "target_id": "appr_quality_hold_batch",
            "relation_type": "requires_approval",
            "summary": "Workflow cannot place the batch on hold without approval.",
            "permission_scope": "approvals:read",
        },
        {
            "relationship_id": "rel_supply_agent_proposes_approval",
            "source_id": "agent_supply_risk",
            "target_id": "appr_expedite_supplier_batch",
            "relation_type": "proposes",
            "summary": "Supply Risk Agent drafts the expedite approval payload.",
            "permission_scope": "agents:read",
        },
        {
            "relationship_id": "rel_quality_agent_proposes_approval",
            "source_id": "agent_quality_risk",
            "target_id": "appr_quality_hold_batch",
            "relation_type": "proposes",
            "summary": "Quality Risk Agent drafts the quality hold payload.",
            "permission_scope": "agents:read",
        },
        {
            "relationship_id": "rel_policy_governs_agent",
            "source_id": "policy_external_egress",
            "target_id": "agent_quality_risk",
            "relation_type": "governs",
            "summary": "Model egress policy governs quality agent model calls.",
            "permission_scope": "security:read",
        },
        {
            "relationship_id": "rel_policy_records_audit",
            "source_id": "policy_external_egress",
            "target_id": "audit_policy_egress_blocked",
            "relation_type": "records",
            "summary": "Policy decision is recorded in the append-only audit trail.",
            "permission_scope": "audit:read",
        },
    ],
    "source_systems": ["ERP", "MES", "QMS", "CMMS", "Supplier Portal", "Axis Audit"],
    "permission_notes": [
        "Operations roles can inspect plant, line, workflow and approval nodes.",
        "Quality roles can inspect quality risks, batches and quality approvals.",
        "Agents can only read nodes inside their declared domain and tenant scope.",
        "External model egress remains blocked unless policy explicitly enables it.",
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
                "surface": "ontology",
                "reference_id": "manufacturing-ontology",
                "status": "active",
                "source": "bootstrap",
                "version": "2026-06-22",
                "payload": ONTOLOGY_PAYLOAD,
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
            "AND surface = 'ontology' "
            "AND reference_id = 'manufacturing-ontology'"
        )
    )
