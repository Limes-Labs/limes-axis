import { z } from "zod";

import type { IdentityBrowserSessionList } from "../identity-sessions";
import type {
  AxisReadyReport,
  DeploymentReadinessReport,
  OidcReadinessReport,
  SupportDiagnosticsReport,
} from "../platform-settings";
import {
  nullableStringSchema,
  parseContract,
  readinessStatusSchema,
  stringArraySchema,
} from "./shared";

const settingsCheck = z.object({
  check_id: z.string(),
  status: readinessStatusSchema,
  detail: z.string(),
});

const axisReadyReport = z.object({
  status: z.enum(["ready", "not_ready"]),
  service: z.string(),
  dependencies: z.record(z.string(), z.object({
    required: z.boolean(),
    status: z.enum(["ready", "disabled", "timeout", "unavailable"]),
    latency_ms: z.number(),
  })),
  identity: z.object({
    oidc_auth_required: z.boolean(),
    enterprise_sso_ready: z.boolean(),
    readiness_status: readinessStatusSchema,
  }),
  external_model_egress_enabled: z.boolean(),
});

const oidcReadinessReport = z.object({
  status: readinessStatusSchema,
  enterprise_sso_ready: z.boolean(),
  auth_required: z.boolean(),
  issuer: z.string(),
  audience: z.string(),
  jwks_source: z.string(),
  jwks_url_configured: z.boolean(),
  jwks_cache_seconds: z.number(),
  algorithms: stringArraySchema,
  token_binding: z.object({
    actor_claim: z.string(),
    tenant_claim: z.string(),
    scope_sources: stringArraySchema,
  }),
  checks: z.array(settingsCheck),
});

const deploymentReadinessReport = z.object({
  status: readinessStatusSchema,
  environment: z.string(),
  profile: z.string(),
  production_ready: z.boolean(),
  demo_safe: z.boolean(),
  capabilities: z.record(z.string(), z.union([z.boolean(), z.number(), z.string()])),
  production_blockers: stringArraySchema,
  checks: z.array(settingsCheck.extend({ production_required: z.boolean() })),
  notes: stringArraySchema,
});

const supportDiagnosticsReport = z.object({
  status: readinessStatusSchema,
  service: z.string(),
  environment: z.string(),
  safe_to_share: z.boolean(),
  demo_support_ready: z.boolean(),
  production_support_ready: z.boolean(),
  support_blockers: stringArraySchema,
  diagnostics: z.object({
    deployment: z.object({
      profile: z.string(),
      demo_safe: z.boolean(),
      production_ready: z.boolean(),
      production_blockers: stringArraySchema,
    }),
    identity: z.object({
      readiness_status: readinessStatusSchema,
      enterprise_sso_ready: z.boolean(),
      oidc_auth_required: z.boolean(),
      jwks_source: z.string(),
      jwks_url_configured: z.boolean(),
    }),
    external_model_egress_enabled: z.boolean(),
    live_connector_execution_enabled: z.boolean(),
    audit_ledger_signing_configured: z.boolean(),
    object_store_adapter: z.string(),
    object_store_worm_retention_enabled: z.boolean(),
    object_store_retention_mode: z.string(),
    object_store_retention_days: z.number(),
  }),
  checks: z.array(settingsCheck),
  support_artifacts: z.array(z.object({ label: z.string(),
    path: z.string() })),
  redaction_policy: stringArraySchema,
  notes: stringArraySchema,
});

const identityBrowserSessionList = z.object({
  tenant_id: z.string(),
  actor_id: z.string(),
  tenant_wide: z.boolean(),
  sessions: z.array(z.object({
    session_ref: z.string(),
    actor_id: z.string(),
    status: z.string(),
    current: z.boolean(),
    created_at: z.string(),
    expires_at: z.string(),
    absolute_expires_at: nullableStringSchema,
    last_seen_at: nullableStringSchema,
    refresh_count: z.number(),
    revoked_at: nullableStringSchema,
    revocation_reason: nullableStringSchema,
  })),
  notes: stringArraySchema,
});

export function parseAxisReadyReport(value: unknown): AxisReadyReport {
  return parseContract(axisReadyReport, value);
}

export function parseOidcReadinessReport(value: unknown): OidcReadinessReport {
  return parseContract(oidcReadinessReport, value);
}

export function parseDeploymentReadinessReport(value: unknown): DeploymentReadinessReport {
  return parseContract(deploymentReadinessReport, value);
}

export function parseSupportDiagnosticsReport(value: unknown): SupportDiagnosticsReport {
  return parseContract(supportDiagnosticsReport, value);
}

export function parseIdentityBrowserSessionList(value: unknown): IdentityBrowserSessionList {
  return parseContract(identityBrowserSessionList, value);
}
