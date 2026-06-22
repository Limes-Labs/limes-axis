import type { PlatformStatus } from "./platform-overview";

export type ApprovalDecision = "approve" | "reject" | "request_changes";

export type ApprovalDecisionOption = {
  decision: ApprovalDecision;
  label: string;
  consequence: string;
};

export type ApprovalAuditPreview = {
  event: string;
  actor_role: string;
  scope: string;
  result: string;
};

export type ApprovalInboxItem = {
  approval_id: string;
  action: string;
  risk_level: "high" | "medium" | "low";
  status: string;
  requested_by: string;
  owner_role: string;
  due: string;
  workflow_id: string;
  domain: string;
  summary: string;
  evidence: string[];
  data_accessed: string[];
  risks: string[];
  alternatives: string[];
  estimated_cost: string;
  model_policy: string;
  required_permission: string;
  audit_event_preview: ApprovalAuditPreview;
  decision_options: ApprovalDecisionOption[];
};

export type ManufacturingApprovalInbox = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  queue_status: PlatformStatus;
  policy_notes: string[];
  approvals: ApprovalInboxItem[];
};

export type ApprovalDecisionPersistenceResult = {
  tenant_id: string;
  approval_id: string;
  workflow_id: string;
  action_id: string;
  decision: ApprovalDecision;
  status: string;
  actor_id: string;
  audit_event_id: string;
  audit_event_type: string;
  persisted: boolean;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  workflow_signal: {
    workflow_id: string;
    status: string;
    adapter: string;
    signal_name: string;
    payload: {
      approval_id?: string;
      approved?: boolean;
      decision?: ApprovalDecision;
      reason?: string;
    };
  };
  workflow_signal_status: string;
};

export type ApprovalDecisionRequestPayload = {
  decision: ApprovalDecision;
  actor_id: string;
  actor_scopes: string[];
  note?: string;
};

export function approvalRiskClass(riskLevel: ApprovalInboxItem["risk_level"]): string {
  if (riskLevel === "high") {
    return "signal-action-required";
  }

  return riskLevel === "medium" ? "signal-watch" : "signal-ready";
}

export function approvalDecisionLabel(decision: ApprovalDecision): string {
  if (decision === "request_changes") {
    return "Changes Requested";
  }

  return decision === "approve" ? "Approved" : "Rejected";
}

export function approvalDecisionActorId(approval: ApprovalInboxItem): string {
  return `${approval.owner_role}-role`;
}

export function approvalDecisionActorScopes(approval: ApprovalInboxItem): string[] {
  return [approval.required_permission];
}

export function buildApprovalDecisionPayload(
  approval: ApprovalInboxItem,
  decision: ApprovalDecision,
): ApprovalDecisionRequestPayload {
  return {
    decision,
    actor_id: approvalDecisionActorId(approval),
    actor_scopes: approvalDecisionActorScopes(approval),
    note: `Console decision recorded for ${approval.approval_id}.`,
  };
}

export function findApprovalById(
  inbox: ManufacturingApprovalInbox,
  approvalId: string,
): ApprovalInboxItem {
  return (
    inbox.approvals.find((approval) => approval.approval_id === approvalId) ?? inbox.approvals[0]
  );
}
