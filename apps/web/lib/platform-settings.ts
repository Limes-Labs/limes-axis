export type SettingsReadinessStatus = "ready" | "action_required";

export type SettingsCheck = {
  check_id: string;
  status: SettingsReadinessStatus;
  detail: string;
};

export type AxisReadyReport = {
  status: "ready";
  service: string;
  dependencies: Record<string, boolean>;
  identity: {
    oidc_auth_required: boolean;
    enterprise_sso_ready: boolean;
    readiness_status: SettingsReadinessStatus;
  };
  external_model_egress_enabled: boolean;
};

export type OidcReadinessReport = {
  status: SettingsReadinessStatus;
  enterprise_sso_ready: boolean;
  auth_required: boolean;
  issuer: string;
  audience: string;
  jwks_source: string;
  jwks_url_configured: boolean;
  jwks_cache_seconds: number;
  algorithms: string[];
  token_binding: {
    actor_claim: string;
    tenant_claim: string;
    scope_sources: string[];
  };
  checks: SettingsCheck[];
};

export type DeploymentReadinessReport = {
  status: SettingsReadinessStatus;
  environment: string;
  profile: string;
  production_ready: boolean;
  demo_safe: boolean;
  capabilities: Record<string, boolean | number | string>;
  production_blockers: string[];
  checks: Array<SettingsCheck & { production_required: boolean }>;
  notes: string[];
};

export type SupportDiagnosticsReport = {
  status: SettingsReadinessStatus;
  service: string;
  environment: string;
  safe_to_share: boolean;
  demo_support_ready: boolean;
  production_support_ready: boolean;
  support_blockers: string[];
  diagnostics: {
    deployment: {
      profile: string;
      demo_safe: boolean;
      production_ready: boolean;
      production_blockers: string[];
    };
    identity: {
      readiness_status: SettingsReadinessStatus;
      enterprise_sso_ready: boolean;
      oidc_auth_required: boolean;
      jwks_source: string;
      jwks_url_configured: boolean;
    };
    external_model_egress_enabled: boolean;
    live_connector_execution_enabled: boolean;
    audit_ledger_signing_configured: boolean;
    object_store_adapter: string;
    object_store_worm_retention_enabled: boolean;
    object_store_retention_mode: string;
    object_store_retention_days: number;
  };
  checks: SettingsCheck[];
  support_artifacts: Array<{ label: string; path: string }>;
  redaction_policy: string[];
  notes: string[];
};

export function settingsStatusLabel(status: SettingsReadinessStatus): string {
  return status === "ready" ? "Ready" : "Action required";
}

export function settingsStatusClass(status: SettingsReadinessStatus): string {
  return status === "ready" ? "signal-ready" : "signal-action-required";
}

export function countActionRequiredChecks(checks: SettingsCheck[]): number {
  return checks.filter((check) => check.status === "action_required").length;
}
