import type { PlatformStatus } from "./platform-overview";

export type OntologyNodeType =
  | "organization"
  | "asset"
  | "process"
  | "workflow"
  | "risk"
  | "approval"
  | "agent"
  | "system"
  | "policy"
  | "audit_event";

export type OntologyNode = {
  node_id: string;
  label: string;
  node_type: OntologyNodeType;
  domain: string;
  status: PlatformStatus;
  source_system: string;
  summary: string;
};

export type OntologyRelationship = {
  relationship_id: string;
  source_id: string;
  target_id: string;
  relation_type: string;
  summary: string;
  permission_scope: string;
};

export type OntologyGraphQueryMetadata = {
  adapter: string;
  source: string;
  query_mode: string;
  tenant_id: string;
  actor_id: string;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  requested_scopes: string[];
  applied_relationship_scopes: string[];
  denied_relationship_count: number;
  returned_node_count: number;
  returned_relationship_count: number;
  typeql: string | null;
  notes: string[];
};

export type ManufacturingOntology = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  nodes: OntologyNode[];
  relationships: OntologyRelationship[];
  source_systems: string[];
  permission_notes: string[];
  graph_query: OntologyGraphQueryMetadata;
};

export type OntologyEntityRelationship = {
  direction: "inbound" | "outbound";
  relationship: OntologyRelationship;
  peer_node: OntologyNode;
};

export type ManufacturingOntologyEntityDetail = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  node: OntologyNode;
  connected_relationships: OntologyEntityRelationship[];
  inbound_count: number;
  outbound_count: number;
  required_permissions: string[];
  evidence_refs: string[];
  data_access: string[];
  governed_by: string[];
  related_workflows: string[];
  related_approvals: string[];
  related_agents: string[];
  detail_notes: string[];
};

export const defaultManufacturingOntology: ManufacturingOntology = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  source_systems: ["ERP", "MES", "QMS", "CMMS", "Supplier Portal", "Axis Audit"],
  permission_notes: [
    "Operations roles can inspect plant, line, workflow and approval nodes.",
    "Quality roles can inspect quality risks, batches and quality approvals.",
    "Agents can only read nodes inside their declared domain and tenant scope.",
    "External model egress remains blocked unless policy explicitly enables it.",
  ],
  graph_query: {
    adapter: "axis-deferred-ontology-query-adapter",
    source: "demo-seed",
    query_mode: "unfiltered_public_seed",
    tenant_id: "tenant_demo_manufacturing",
    actor_id: "public-demo-reader",
    permission_decision: {
      allowed: true,
      reason: "public_seed",
    },
    requested_scopes: [],
    applied_relationship_scopes: [
      "agents:read",
      "approvals:read",
      "audit:read",
      "maintenance:read",
      "operations:read",
      "quality:read",
      "security:read",
      "supply:read",
    ],
    denied_relationship_count: 0,
    returned_node_count: 18,
    returned_relationship_count: 14,
    typeql: null,
    notes: [
      "Public ontology seed is served through the Axis graph query contract.",
      "Authenticated reads can be filtered by relationship-derived scopes.",
    ],
  },
  nodes: [
    {
      node_id: "org_ravenna_operations",
      label: "Ravenna Operations",
      node_type: "organization",
      domain: "Operations",
      status: "ready",
      source_system: "Axis",
      summary: "Demo tenant operating unit for the manufacturing reference scenario.",
    },
    {
      node_id: "asset_ravenna_works",
      label: "Ravenna Works",
      node_type: "asset",
      domain: "Plant",
      status: "ready",
      source_system: "MES",
      summary: "Fictional plant used by the public Platform demo seed.",
    },
    {
      node_id: "asset_line_2_packaging",
      label: "Line 2 Packaging",
      node_type: "asset",
      domain: "Production",
      status: "action_required",
      source_system: "MES",
      summary: "Packaging line exposed to supplier delay risk.",
    },
    {
      node_id: "asset_press_4",
      label: "Press 4",
      node_type: "asset",
      domain: "Maintenance",
      status: "watch",
      source_system: "CMMS",
      summary: "Press with a maintenance window that may need rescheduling.",
    },
    {
      node_id: "asset_batch_q_1842",
      label: "Batch Q-1842",
      node_type: "asset",
      domain: "Quality",
      status: "watch",
      source_system: "QMS",
      summary: "Batch with inspection variance above the watch threshold.",
    },
    {
      node_id: "asset_motors_batch",
      label: "Inbound Motors Batch",
      node_type: "asset",
      domain: "Supply",
      status: "action_required",
      source_system: "Supplier Portal",
      summary: "Inbound component batch delayed against the production window.",
    },
    {
      node_id: "risk_supplier_delay",
      label: "Supplier Delay Risk",
      node_type: "risk",
      domain: "Supply",
      status: "action_required",
      source_system: "Axis",
      summary: "Risk signal that may block Line 2 packaging.",
    },
    {
      node_id: "risk_quality_drift",
      label: "Quality Drift Risk",
      node_type: "risk",
      domain: "Quality",
      status: "watch",
      source_system: "Axis",
      summary: "Risk signal generated from QMS inspection variance.",
    },
    {
      node_id: "risk_maintenance_window",
      label: "Maintenance Window Risk",
      node_type: "risk",
      domain: "Maintenance",
      status: "watch",
      source_system: "Axis",
      summary: "Risk that planned downtime overlaps a rush order.",
    },
    {
      node_id: "wf_supplier_delay_review",
      label: "Supplier Delay Review",
      node_type: "workflow",
      domain: "Supply",
      status: "action_required",
      source_system: "Temporal",
      summary: "Workflow waiting for a human decision on expedite or reschedule.",
    },
    {
      node_id: "wf_quality_hold_review",
      label: "Quality Hold Review",
      node_type: "workflow",
      domain: "Quality",
      status: "watch",
      source_system: "Temporal",
      summary: "Workflow investigating whether the batch should be held.",
    },
    {
      node_id: "wf_maintenance_reschedule",
      label: "Maintenance Reschedule",
      node_type: "workflow",
      domain: "Maintenance",
      status: "watch",
      source_system: "Temporal",
      summary: "Workflow preparing a schedule change for Press 4.",
    },
    {
      node_id: "appr_expedite_supplier_batch",
      label: "Expedite Supplier Batch",
      node_type: "approval",
      domain: "Supply",
      status: "action_required",
      source_system: "Axis",
      summary: "High-risk approval gate for supplier expedite action.",
    },
    {
      node_id: "appr_quality_hold_batch",
      label: "Place Batch Q-1842 On Hold",
      node_type: "approval",
      domain: "Quality",
      status: "action_required",
      source_system: "Axis",
      summary: "High-risk approval gate for quality hold action.",
    },
    {
      node_id: "agent_supply_risk",
      label: "Supply Risk Agent",
      node_type: "agent",
      domain: "Supply",
      status: "action_required",
      source_system: "Axis",
      summary: "L2 agent that drafts supplier risk actions.",
    },
    {
      node_id: "agent_quality_risk",
      label: "Quality Risk Agent",
      node_type: "agent",
      domain: "Quality",
      status: "watch",
      source_system: "Axis",
      summary: "L2 agent that drafts quality hold recommendations.",
    },
    {
      node_id: "policy_external_egress",
      label: "External Model Egress Policy",
      node_type: "policy",
      domain: "Security",
      status: "ready",
      source_system: "Axis",
      summary: "Policy that blocks external model egress by default.",
    },
    {
      node_id: "audit_policy_egress_blocked",
      label: "Egress Blocked Audit Event",
      node_type: "audit_event",
      domain: "Security",
      status: "ready",
      source_system: "Axis Audit",
      summary: "Evidence that the model router blocked external egress.",
    },
  ],
  relationships: [
    {
      relationship_id: "rel_org_owns_plant",
      source_id: "org_ravenna_operations",
      target_id: "asset_ravenna_works",
      relation_type: "owns",
      summary: "Operating unit owns the demo plant context.",
      permission_scope: "operations:read",
    },
    {
      relationship_id: "rel_plant_contains_line",
      source_id: "asset_ravenna_works",
      target_id: "asset_line_2_packaging",
      relation_type: "contains",
      summary: "Plant contains Line 2 packaging operations.",
      permission_scope: "operations:read",
    },
    {
      relationship_id: "rel_supplier_batch_impacts_line",
      source_id: "asset_motors_batch",
      target_id: "asset_line_2_packaging",
      relation_type: "impacts",
      summary: "Delayed inbound batch may block the packaging line.",
      permission_scope: "supply:read",
    },
    {
      relationship_id: "rel_supplier_risk_blocks_workflow",
      source_id: "risk_supplier_delay",
      target_id: "wf_supplier_delay_review",
      relation_type: "drives",
      summary: "Supplier delay risk drives the review workflow.",
      permission_scope: "supply:read",
    },
    {
      relationship_id: "rel_supplier_workflow_requires_approval",
      source_id: "wf_supplier_delay_review",
      target_id: "appr_expedite_supplier_batch",
      relation_type: "requires_approval",
      summary: "Workflow cannot execute expedite action without approval.",
      permission_scope: "approvals:read",
    },
    {
      relationship_id: "rel_supply_agent_proposes_approval",
      source_id: "agent_supply_risk",
      target_id: "appr_expedite_supplier_batch",
      relation_type: "proposes",
      summary: "Supply Risk Agent drafts the expedite approval payload.",
      permission_scope: "agents:read",
    },
    {
      relationship_id: "rel_quality_batch_impacts_risk",
      source_id: "asset_batch_q_1842",
      target_id: "risk_quality_drift",
      relation_type: "raises",
      summary: "Inspection variance raises the quality drift risk.",
      permission_scope: "quality:read",
    },
    {
      relationship_id: "rel_quality_risk_drives_workflow",
      source_id: "risk_quality_drift",
      target_id: "wf_quality_hold_review",
      relation_type: "drives",
      summary: "Quality drift risk drives the quality hold workflow.",
      permission_scope: "quality:read",
    },
    {
      relationship_id: "rel_quality_workflow_requires_approval",
      source_id: "wf_quality_hold_review",
      target_id: "appr_quality_hold_batch",
      relation_type: "requires_approval",
      summary: "Workflow cannot place the batch on hold without approval.",
      permission_scope: "approvals:read",
    },
    {
      relationship_id: "rel_quality_agent_proposes_approval",
      source_id: "agent_quality_risk",
      target_id: "appr_quality_hold_batch",
      relation_type: "proposes",
      summary: "Quality Risk Agent drafts the quality hold payload.",
      permission_scope: "agents:read",
    },
    {
      relationship_id: "rel_plant_contains_press",
      source_id: "asset_ravenna_works",
      target_id: "asset_press_4",
      relation_type: "contains",
      summary: "Plant contains Press 4 maintenance context.",
      permission_scope: "maintenance:read",
    },
    {
      relationship_id: "rel_maintenance_risk_drives_workflow",
      source_id: "risk_maintenance_window",
      target_id: "wf_maintenance_reschedule",
      relation_type: "drives",
      summary: "Maintenance risk drives the reschedule workflow.",
      permission_scope: "maintenance:read",
    },
    {
      relationship_id: "rel_policy_governs_agent",
      source_id: "policy_external_egress",
      target_id: "agent_quality_risk",
      relation_type: "governs",
      summary: "Model egress policy governs quality agent model calls.",
      permission_scope: "security:read",
    },
    {
      relationship_id: "rel_policy_records_audit",
      source_id: "policy_external_egress",
      target_id: "audit_policy_egress_blocked",
      relation_type: "records",
      summary: "Policy decision is recorded in the append-only audit trail.",
      permission_scope: "audit:read",
    },
  ],
};

export function nodeLabelById(ontology: ManufacturingOntology): Map<string, string> {
  return new Map(ontology.nodes.map((node) => [node.node_id, node.label]));
}

export function countNodesByType(ontology: ManufacturingOntology): Map<OntologyNodeType, number> {
  return ontology.nodes.reduce((counts, node) => {
    counts.set(node.node_type, (counts.get(node.node_type) ?? 0) + 1);
    return counts;
  }, new Map<OntologyNodeType, number>());
}

export function formatNodeType(type: OntologyNodeType): string {
  return type
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

type DetailLists = {
  evidence_refs: string[];
  data_access: string[];
  detail_notes: string[];
};

const ontologyDetailOverrides: Record<string, DetailLists> = {
  asset_line_2_packaging: {
    evidence_refs: [
      "risk_supplier_delay",
      "wf_supplier_delay_review",
      "audit_20260621_154000_ontology_read",
    ],
    data_access: [
      "MES line status summary",
      "supplier delay risk relationship",
      "approval gate summary",
    ],
    detail_notes: [
      "This detail page is read-only and derived from the public ontology seed.",
      "Operations can inspect the line context, but cannot execute workflow signals here.",
      "The supplier delay risk is visible because the relationship scope allows it.",
    ],
  },
  risk_supplier_delay: {
    evidence_refs: [
      "asset_motors_batch",
      "asset_line_2_packaging",
      "wf_supplier_delay_review",
    ],
    data_access: [
      "supplier risk summary",
      "impacted production line",
      "workflow blocker summary",
    ],
    detail_notes: [
      "Risk detail is derived from TypeDB-shaped relationships in the demo seed.",
      "The risk can drive action proposals, but does not execute actions directly.",
    ],
  },
  wf_supplier_delay_review: {
    evidence_refs: [
      "risk_supplier_delay",
      "appr_expedite_supplier_batch",
      "audit_20260621_141800_signal_awaiting",
    ],
    data_access: [
      "workflow state summary",
      "pending signal metadata",
      "approval requirement relationship",
    ],
    detail_notes: [
      "Workflow detail is inspectable without exposing runtime mutation controls.",
      "Signal execution remains behind the Axis workflow runtime adapter.",
    ],
  },
  appr_expedite_supplier_batch: {
    evidence_refs: [
      "wf_supplier_delay_review",
      "agent_supply_risk",
      "audit_20260621_141200_agent_proposal",
    ],
    data_access: [
      "approval summary",
      "requesting agent relationship",
      "workflow requirement relationship",
    ],
    detail_notes: [
      "Approval detail links the proposed action to the owner review gate.",
      "Decisions are preview-only until persisted approval state is implemented.",
    ],
  },
  agent_supply_risk: {
    evidence_refs: [
      "appr_expedite_supplier_batch",
      "risk_supplier_delay",
      "audit_20260621_141200_agent_proposal",
    ],
    data_access: [
      "agent relationship summary",
      "proposal approval reference",
      "supply risk evidence",
    ],
    detail_notes: [
      "Agent detail is scoped to declared tenant and domain relationships.",
      "Agent runtime state remains outside this read-only ontology detail slice.",
    ],
  },
  policy_external_egress: {
    evidence_refs: [
      "agent_quality_risk",
      "audit_policy_egress_blocked",
      "audit_20260621_133900_egress_blocked",
    ],
    data_access: [
      "policy summary",
      "governed agent relationship",
      "audit evidence relationship",
    ],
    detail_notes: [
      "Policy detail shows governance relationships, not policy editing controls.",
      "External model egress remains blocked unless tenant policy explicitly allows it.",
    ],
  },
};

function defaultDetailLists(node: OntologyNode): DetailLists {
  return {
    evidence_refs: [node.node_id],
    data_access: [
      `${node.source_system} public-demo summary`,
      `${node.domain} relationship context`,
      `${node.node_type} metadata`,
    ],
    detail_notes: [
      "This entity detail is read-only and synthetic.",
      "Production entity details will require tenant-scoped graph query permissions.",
    ],
  };
}

export function buildOntologyEntityDetail(
  ontology: ManufacturingOntology,
  nodeId: string,
): ManufacturingOntologyEntityDetail | null {
  const nodeById = new Map(ontology.nodes.map((node) => [node.node_id, node]));
  const node = nodeById.get(nodeId);

  if (!node) {
    return null;
  }

  const connectedRelationships: OntologyEntityRelationship[] = [];

  for (const relationship of ontology.relationships) {
    if (relationship.source_id === nodeId) {
      const peerNode = nodeById.get(relationship.target_id);
      if (peerNode) {
        connectedRelationships.push({
          direction: "outbound",
          relationship,
          peer_node: peerNode,
        });
      }
    } else if (relationship.target_id === nodeId) {
      const peerNode = nodeById.get(relationship.source_id);
      if (peerNode) {
        connectedRelationships.push({
          direction: "inbound",
          relationship,
          peer_node: peerNode,
        });
      }
    }
  }

  const inboundCount = connectedRelationships.filter(
    (relationship) => relationship.direction === "inbound",
  ).length;
  const outboundCount = connectedRelationships.length - inboundCount;
  const permissions = Array.from(
    new Set(
      connectedRelationships.map((item) => item.relationship.permission_scope),
    ),
  ).sort();
  const detailLists = {
    ...defaultDetailLists(node),
    ...ontologyDetailOverrides[nodeId],
  };

  return {
    tenant_id: ontology.tenant_id,
    plant_name: ontology.plant_name,
    scenario: ontology.scenario,
    as_of: ontology.as_of,
    node,
    connected_relationships: connectedRelationships,
    inbound_count: inboundCount,
    outbound_count: outboundCount,
    required_permissions: permissions.length > 0 ? permissions : [`${node.domain.toLowerCase()}:read`],
    evidence_refs: detailLists.evidence_refs,
    data_access: detailLists.data_access,
    governed_by: connectedRelationships
      .filter((item) => item.relationship.relation_type === "governs")
      .map((item) => item.peer_node.node_id)
      .sort(),
    related_workflows: Array.from(
      new Set([
        ...connectedRelationships
          .filter((item) => item.peer_node.node_type === "workflow")
          .map((item) => item.peer_node.node_id),
        ...(node.node_type === "workflow" ? [node.node_id] : []),
      ]),
    ).sort(),
    related_approvals: Array.from(
      new Set([
        ...connectedRelationships
          .filter((item) => item.peer_node.node_type === "approval")
          .map((item) => item.peer_node.node_id),
        ...(node.node_type === "approval" ? [node.node_id] : []),
      ]),
    ).sort(),
    related_agents: Array.from(
      new Set([
        ...connectedRelationships
          .filter((item) => item.peer_node.node_type === "agent")
          .map((item) => item.peer_node.node_id),
        ...(node.node_type === "agent" ? [node.node_id] : []),
      ]),
    ).sort(),
    detail_notes: detailLists.detail_notes,
  };
}
