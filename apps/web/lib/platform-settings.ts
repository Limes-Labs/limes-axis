import { strings } from "./strings";

export type SettingsReadinessStatus = "ready" | "action_required";

export type SettingsCheck = {
  check_id: string;
  status: SettingsReadinessStatus;
  detail: string;
};

export type AxisReadyReport = {
  status: "ready" | "not_ready";
  service: string;
  dependencies: Record<
    string,
    {
      required: boolean;
      status: "ready" | "disabled" | "timeout" | "unavailable";
      latency_ms: number;
    }
  >;
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

type DependencyStatus = AxisReadyReport["dependencies"][string]["status"];

/**
 * Tone for a `/ready` dependency. Only a reachable dependency reads as healthy:
 * `disabled` means the dependency is not configured, which is neutral when it
 * is optional and needs attention when the API marks it required — never green.
 */
export function dependencyStatusClass(status: DependencyStatus, required: boolean): string {
  if (status === "ready") {
    return "signal-ready";
  }
  if (status === "disabled") {
    return required ? "signal-watch" : "status-checking";
  }
  return "signal-action-required";
}

export function countActionRequiredChecks(checks: SettingsCheck[]): number {
  return checks.filter((check) => check.status === "action_required").length;
}

/**
 * One-line plain-English guidance for an "Action required" readiness check,
 * keyed by the check id the API emits. Unknown ids get generic guidance so a
 * new API check never renders a pill without a what-to-do line.
 */
export function settingsCheckGuidance(checkId: string): string {
  const guidance: Record<string, string> = strings.settings.guidance;
  return guidance[checkId] ?? strings.settings.guidanceFallback;
}

const checkLabelAcronyms = new Set(["api", "dr", "https", "jwks", "oidc", "slo", "sso", "url"]);

/**
 * Operator-facing name for a readiness check id. Known ids use curated copy;
 * an id the console has not seen yet is sentence-cased (acronyms upper-cased)
 * rather than shown as a raw lowercase identifier.
 */
export function settingsCheckLabel(checkId: string): string {
  const labels: Record<string, string> = strings.settings.checkLabels;
  const known = labels[checkId];
  if (known) {
    return known;
  }
  const words = checkId
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => (checkLabelAcronyms.has(word) ? word.toUpperCase() : word));
  const sentence = words.join(" ");
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

export type SettingsCheckAction = { href: string; label: string };

const actions = strings.settings.checkActions;

/**
 * In-console destination for checks an operator can act on from here. Checks
 * that only change through deployment configuration have none: their guidance
 * line and technical detail are the actionable part.
 */
const checkActionById: Record<string, SettingsCheckAction> = {
  oidc_enterprise_sso: { href: "/settings?tab=identity", label: actions.identityTab },
  oidc_secure_cookie_session: { href: "/settings?tab=identity", label: actions.identityTab },
  demo_support_ready: { href: "/settings?tab=deployment", label: actions.deploymentTab },
  deployment_readiness_attached: {
    href: "/settings?tab=deployment",
    label: actions.deploymentTab,
  },
  registered_tenant_admission: { href: "/tenants", label: actions.tenants },
  external_model_egress_disabled: { href: "/model-routing", label: actions.modelRouting },
  live_connector_execution_disabled: { href: "/connectors", label: actions.connectors },
  ontology_graph_mutation_posture: { href: "/ontology", label: actions.ontology },
  audit_ledger_signing_configured: { href: "/audit", label: actions.audit },
};

export function settingsCheckAction(checkId: string): SettingsCheckAction | null {
  return checkActionById[checkId] ?? null;
}

/**
 * Failures first, then production-required before optional checks, keeping
 * the API's order within each group so the list is stable between refreshes.
 */
export function sortSettingsChecks<T extends SettingsCheck & { production_required?: boolean }>(
  checks: readonly T[],
): T[] {
  const rank = (check: T) =>
    (check.status === "action_required" ? 0 : 2) + (check.production_required === false ? 1 : 0);
  return checks
    .map((check, index) => ({ check, index }))
    .sort((left, right) => rank(left.check) - rank(right.check) || left.index - right.index)
    .map(({ check }) => check);
}
