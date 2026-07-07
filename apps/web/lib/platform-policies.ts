import { AxisApiError, axisFetch, axisFetchJson, type AxisFetchOptions } from "./axis-api";

export type PlatformPolicyScope = "action_execution" | "approval_requirement";

export type PlatformPolicyEffect = "deny" | "require_approval" | "allow_with_evidence";

export type PlatformPolicyRuleConditions = {
  action_domains?: string[];
  risk_levels?: string[];
  autonomy_levels?: string[];
  requested_amount_at_least?: number | null;
};

export type PlatformPolicyRecord = {
  tenant_id: string;
  policy_id: string;
  revision_number: number;
  policy_version: string;
  display_name: string;
  description: string;
  scope: PlatformPolicyScope;
  effect: PlatformPolicyEffect;
  conditions: PlatformPolicyRuleConditions;
  status: string;
  notes?: string[];
  created_by: string;
  created_at: string;
  required_authoring_scope: string;
  revises_revision_number?: number | null;
  replaced_by_revision_number?: number | null;
  revision_idempotency_key?: string | null;
  idempotent_replay?: boolean;
  audit_event_type: string;
  audit_event_id?: string | null;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
};

export type PlatformPolicyRegistry = {
  tenant_id: string;
  policy_count: number;
  active_policy_count: number;
  policies?: PlatformPolicyRecord[];
  policy_notes?: string[];
};

export type PlatformPolicyDetail = {
  tenant_id: string;
  policy_id: string;
  current_revision: PlatformPolicyRecord;
  revisions: PlatformPolicyRecord[];
};

export type PlatformPolicyMatch = {
  policy_id: string;
  revision_number: number;
  policy_version: string;
  effect: PlatformPolicyEffect;
  matched_constraints: Record<string, unknown>;
};

export type PlatformPolicyDecision = {
  tenant_id: string;
  scope: PlatformPolicyScope;
  effect: string;
  matched: boolean;
  matched_policy_id?: string | null;
  matched_policy_version?: string | null;
  matched_revision_number?: number | null;
  matched_policies?: PlatformPolicyMatch[];
  evaluated_policy_count: number;
  precedence_rule?: string;
  evidence?: Record<string, unknown>;
};

export type PlatformPolicyEvaluationContextPayload = {
  action_domain?: string;
  risk_level?: string;
  autonomy_level?: string;
  requested_amount?: number;
};

export type PlatformPolicyEvaluationRequestPayload = {
  tenant_id: string;
  actor_id: string;
  actor_scopes: string[];
  scope: PlatformPolicyScope;
  context: PlatformPolicyEvaluationContextPayload;
};

export type PlatformPolicyRegistryFilters = {
  scope: PlatformPolicyScope | typeof allPolicyFilter;
  status: string;
};

export const allPolicyFilter = "all";

export const platformPolicyScopes: PlatformPolicyScope[] = [
  "action_execution",
  "approval_requirement",
];

export const platformPolicyStatuses = ["active", "superseded"];

export const platformPolicyRiskLevels = ["low", "medium", "high", "critical"];

export const platformPolicyAutonomyLevels = ["L0", "L1", "L2", "L3", "L4"];

export const platformPolicyEvaluateScope = "platform:policy:evaluate";

export const platformPolicyEvaluateActorId = "platform-policy-reviewer-role";

export const platformPoliciesPath = "/platform/policies";

export const platformPolicyEvaluatePath = "/platform/policies/evaluate";

export const platformPolicyPrecedenceSteps = [
  "deny beats require_approval, which beats allow_with_evidence.",
  "Ties on effect are broken by the lexicographically smallest policy id.",
  "When no active policy matches the context, the decision is default allow.",
];

export function buildPlatformPoliciesPath(filters: PlatformPolicyRegistryFilters): string {
  const params = new URLSearchParams();

  if (filters.scope !== allPolicyFilter) {
    params.set("scope", filters.scope);
  }

  if (filters.status !== allPolicyFilter) {
    params.set("status", filters.status);
  }

  const query = params.toString();
  return query ? `${platformPoliciesPath}?${query}` : platformPoliciesPath;
}

export function buildPlatformPolicyDetailPath(policyId: string): string {
  return `${platformPoliciesPath}/${encodeURIComponent(policyId)}`;
}

export function policyScopeLabel(scope: PlatformPolicyScope): string {
  return scope === "action_execution" ? "Action execution" : "Approval requirement";
}

export function policyEffectLabel(effect: string): string {
  if (effect === "deny") {
    return "Deny";
  }

  if (effect === "require_approval") {
    return "Require approval";
  }

  if (effect === "allow_with_evidence") {
    return "Allow with evidence";
  }

  return effect === "allow" ? "Allow (default)" : effect;
}

export function policyEffectClass(effect: string): string {
  if (effect === "deny") {
    return "signal-action-required";
  }

  return effect === "require_approval" ? "signal-watch" : "signal-ready";
}

export function policyStatusLabel(status: string): string {
  return status === "active" ? "Active" : status === "superseded" ? "Superseded" : status;
}

export function policyStatusClass(status: string): string {
  return status === "active" ? "signal-ready" : "status-checking";
}

export function summarizePolicyConditions(conditions: PlatformPolicyRuleConditions): string {
  const parts: string[] = [];
  const actionDomains = conditions.action_domains ?? [];
  const riskLevels = conditions.risk_levels ?? [];
  const autonomyLevels = conditions.autonomy_levels ?? [];

  if (actionDomains.length > 0) {
    parts.push(`domains ${actionDomains.join(", ")}`);
  }

  if (riskLevels.length > 0) {
    parts.push(`risk ${riskLevels.join(", ")}`);
  }

  if (autonomyLevels.length > 0) {
    parts.push(`autonomy ${autonomyLevels.join(", ")}`);
  }

  if (conditions.requested_amount_at_least != null) {
    parts.push(`amount >= ${conditions.requested_amount_at_least}`);
  }

  return parts.length > 0 ? parts.join(" / ") : "Any evaluation context";
}

export function countPoliciesByEffect(
  policies: PlatformPolicyRecord[],
  effect: PlatformPolicyEffect,
): number {
  return policies.filter((policy) => policy.effect === effect).length;
}

export type RequestedAmountParseResult =
  | { ok: true; amount: number | null }
  | { ok: false; message: string };

export function parseRequestedAmount(value: string): RequestedAmountParseResult {
  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return { ok: true, amount: null };
  }

  const amount = Number(trimmed);

  if (!Number.isFinite(amount) || amount < 0) {
    return { ok: false, message: "Requested amount must be a non-negative number." };
  }

  return { ok: true, amount };
}

export type PolicyEvaluationFormState = {
  scope: PlatformPolicyScope;
  actionDomain: string;
  riskLevel: string;
  autonomyLevel: string;
  requestedAmount: number | null;
};

export function buildPolicyEvaluationPayload(
  tenantId: string,
  form: PolicyEvaluationFormState,
): PlatformPolicyEvaluationRequestPayload {
  const context: PlatformPolicyEvaluationContextPayload = {};
  const actionDomain = form.actionDomain.trim();

  if (actionDomain.length > 0) {
    context.action_domain = actionDomain;
  }

  if (form.riskLevel.length > 0) {
    context.risk_level = form.riskLevel;
  }

  if (form.autonomyLevel.length > 0) {
    context.autonomy_level = form.autonomyLevel;
  }

  if (form.requestedAmount !== null) {
    context.requested_amount = form.requestedAmount;
  }

  return {
    tenant_id: tenantId,
    actor_id: platformPolicyEvaluateActorId,
    actor_scopes: [platformPolicyEvaluateScope],
    scope: form.scope,
    context,
  };
}

export async function fetchPlatformPolicyDetail(
  policyId: string,
  options: AxisFetchOptions = {},
): Promise<PlatformPolicyDetail | null> {
  const path = buildPlatformPolicyDetailPath(policyId);
  const response = await axisFetch(path, options);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new AxisApiError(path, response.status);
  }

  return (await response.json()) as PlatformPolicyDetail;
}

export async function evaluatePlatformPolicy(
  payload: PlatformPolicyEvaluationRequestPayload,
  options: AxisFetchOptions = {},
): Promise<PlatformPolicyDecision> {
  return axisFetchJson<PlatformPolicyDecision>(platformPolicyEvaluatePath, {
    ...options,
    method: "POST",
    body: payload,
  });
}
