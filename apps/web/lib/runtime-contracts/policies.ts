import { z } from "zod";

import type {
  PlatformPolicyDecision,
  PlatformPolicyDetail,
  PlatformPolicyRecord,
  PlatformPolicyRegistry,
} from "../platform-policies";
import {
  nullableStringSchema,
  parseContract,
  permissionDecisionSchema,
  stringArraySchema,
} from "./shared";

const unknownRecord = z.record(z.string(), z.unknown());
const policyScope = z.enum(["action_execution", "approval_requirement"]);
const policyEffect = z.enum(["deny", "require_approval", "allow_with_evidence"]);
const policyRecord = z.object({
  tenant_id: z.string(),
  policy_id: z.string(),
  revision_number: z.number(),
  policy_version: z.string(),
  display_name: z.string(),
  description: z.string(),
  scope: policyScope,
  effect: policyEffect,
  conditions: z.object({
    action_domains: stringArraySchema.optional(),
    risk_levels: stringArraySchema.optional(),
    autonomy_levels: stringArraySchema.optional(),
    requested_amount_at_least: z.number().nullable().optional(),
  }),
  status: z.string(),
  notes: stringArraySchema.optional(),
  created_by: z.string(),
  created_at: z.string(),
  required_authoring_scope: z.string(),
  revises_revision_number: z.number().nullable().optional(),
  replaced_by_revision_number: z.number().nullable().optional(),
  revision_idempotency_key: nullableStringSchema.optional(),
  idempotent_replay: z.boolean().optional(),
  audit_event_type: z.string(),
  audit_event_id: nullableStringSchema.optional(),
  permission_decision: permissionDecisionSchema,
});
const policyRegistry = z.object({
  tenant_id: z.string(),
  policy_count: z.number(),
  active_policy_count: z.number(),
  policies: z.array(policyRecord).optional(),
  policy_notes: stringArraySchema.optional(),
});
const policyDetail = z.object({
  tenant_id: z.string(),
  policy_id: z.string(),
  current_revision: policyRecord,
  revisions: z.array(policyRecord),
});
const policyDecision = z.object({
  tenant_id: z.string(),
  scope: policyScope,
  effect: z.string(),
  matched: z.boolean(),
  matched_policy_id: nullableStringSchema.optional(),
  matched_policy_version: nullableStringSchema.optional(),
  matched_revision_number: z.number().nullable().optional(),
  matched_policies: z.array(z.object({
    policy_id: z.string(),
    revision_number: z.number(),
    policy_version: z.string(),
    effect: policyEffect,
    matched_constraints: unknownRecord,
  })).optional(),
  evaluated_policy_count: z.number(),
  precedence_rule: z.string().optional(),
  evidence: unknownRecord.optional(),
});

export function parsePlatformPolicyRecord(value: unknown): PlatformPolicyRecord {
  return parseContract(policyRecord, value);
}

export function parsePlatformPolicyRegistry(value: unknown): PlatformPolicyRegistry {
  return parseContract(policyRegistry, value);
}

export function parsePlatformPolicyDetail(value: unknown): PlatformPolicyDetail {
  return parseContract(policyDetail, value);
}

export function parsePlatformPolicyDecision(value: unknown): PlatformPolicyDecision {
  return parseContract(policyDecision, value);
}
