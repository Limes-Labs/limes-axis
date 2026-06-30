"use client";

import {
  Database,
  KeyRound,
  LifeBuoy,
  LockKeyhole,
  ServerCog,
  ShieldCheck,
} from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { ConsolePage } from "@/components/console-page";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import {
  countActionRequiredChecks,
  settingsStatusClass,
  settingsStatusLabel,
  type AxisReadyReport,
  type DeploymentReadinessReport,
  type OidcReadinessReport,
  type SettingsCheck,
  type SupportDiagnosticsReport,
} from "@/lib/platform-settings";
import { useAxisQuery } from "@/lib/use-axis-query";

type SettingsCard = {
  label: string;
  value: string;
  detail: string;
  status: "ready" | "action_required";
  icon: typeof ShieldCheck;
};

const SETTINGS_ENDPOINTS = [
  "/ready",
  "/identity/oidc/readiness",
  "/identity/session",
  "/deployment/readiness",
  "/support/diagnostics",
];

function boolLabel(value: boolean): string {
  return value ? "Enabled" : "Disabled";
}

function compactId(value: string): string {
  return value.replaceAll("_", " ");
}

function SettingsStatusPill({ status }: { status: "ready" | "action_required" }) {
  return (
    <span className={`status-pill ${settingsStatusClass(status)}`}>
      {settingsStatusLabel(status)}
    </span>
  );
}

function CheckList({ checks }: { checks: SettingsCheck[] }) {
  return (
    <div className="stack settings-check-list">
      {checks.map((check) => (
        <div className="row" key={check.check_id}>
          <div>
            <p className="row-title">{compactId(check.check_id)}</p>
            <p className="row-detail">{check.detail}</p>
          </div>
          <SettingsStatusPill status={check.status} />
        </div>
      ))}
    </div>
  );
}

function SettingsApiRequired() {
  return (
    <ApiRequiredState
      detail="Live Settings data requires the Axis readiness, identity, deployment and support APIs. Local fallback settings records are disabled."
      endpoint={SETTINGS_ENDPOINTS.join(" ")}
      title="Settings API unavailable"
    />
  );
}

export function PlatformSettingsConsole() {
  const ready = useAxisQuery<AxisReadyReport>("/ready");
  const oidc = useAxisQuery<OidcReadinessReport>("/identity/oidc/readiness");
  const identity = useAxisQuery<IdentitySessionReadModel>("/identity/session");
  const deployment = useAxisQuery<DeploymentReadinessReport>("/deployment/readiness");
  const support = useAxisQuery<SupportDiagnosticsReport>("/support/diagnostics");

  const hasUnavailableSettings =
    ready.isUnavailable ||
    oidc.isUnavailable ||
    identity.isUnavailable ||
    deployment.isUnavailable ||
    support.isUnavailable;
  const isLoading =
    ready.isLoading ||
    oidc.isLoading ||
    identity.isLoading ||
    deployment.isLoading ||
    support.isLoading;
  const readyReport = ready.data;
  const oidcReport = oidc.data;
  const identityReport = identity.data;
  const deploymentReport = deployment.data;
  const supportReport = support.data;
  const hasApiSettings =
    readyReport && oidcReport && identityReport && deploymentReport && supportReport;
  const sourceLabel = hasApiSettings ? "Live settings" : isLoading ? "Loading settings" : "API required";

  if (hasUnavailableSettings || !hasApiSettings) {
    return (
      <ConsolePage
        eyebrow="Platform control"
        sourceLabel={sourceLabel}
        subtitle="Identity, deployment, support and runtime posture from Axis API contracts."
        title="Platform settings"
      >
        <SettingsApiRequired />
      </ConsolePage>
    );
  }

  const requiredDeploymentChecks = deploymentReport.checks.filter((check) => check.production_required);
  const cards: SettingsCard[] = [
    {
      label: "API readiness",
      value: readyReport.status === "ready" ? "Ready" : "Action required",
      detail: `${Object.values(readyReport.dependencies).filter(Boolean).length} dependencies reachable`,
      status: readyReport.status,
      icon: ServerCog,
    },
    {
      label: "Enterprise SSO",
      value: oidcReport.enterprise_sso_ready ? "Ready" : "Needs hardening",
      detail: `${countActionRequiredChecks(oidcReport.checks)} identity checks need action`,
      status: oidcReport.status,
      icon: KeyRound,
    },
    {
      label: "Deployment",
      value: deploymentReport.demo_safe ? "Demo safe" : "Action required",
      detail: deploymentReport.production_ready
        ? "Production readiness gates are clear"
        : `${deploymentReport.production_blockers.length} production blockers`,
      status: deploymentReport.status,
      icon: LockKeyhole,
    },
    {
      label: "Support",
      value: supportReport.demo_support_ready ? "Demo support ready" : "Needs triage",
      detail: `${supportReport.support_blockers.length} support blockers tracked`,
      status: supportReport.status,
      icon: LifeBuoy,
    },
  ];

  return (
    <ConsolePage
      eyebrow="Platform control"
      sourceLabel={sourceLabel}
      subtitle="Identity, deployment, support and runtime posture from Axis API contracts."
      title="Platform settings"
    >
      <div className="settings-kpi-grid" aria-label="Platform readiness metrics">
        {cards.map((card) => {
          const Icon = card.icon;

          return (
            <article className="ops-kpi-card" key={card.label}>
              <Icon size={30} strokeWidth={1.5} />
              <div>
                <p className="section-label">{card.label}</p>
                <p className={`ops-kpi-value ${settingsStatusClass(card.status)}`}>
                  {card.value}
                </p>
                <p className="row-detail">{card.detail}</p>
              </div>
            </article>
          );
        })}
      </div>

      <div className="settings-layout">
        <section className="panel">
          <div className="section-heading-row">
            <div>
              <p className="section-label">Identity and SSO</p>
              <h2 className="panel-title">OIDC readiness</h2>
            </div>
            <SettingsStatusPill status={oidcReport.status} />
          </div>
          <div className="settings-summary-grid">
            <span>
              <small>Issuer</small>
              <strong>{oidcReport.issuer}</strong>
            </span>
            <span>
              <small>Audience</small>
              <strong>{oidcReport.audience}</strong>
            </span>
            <span>
              <small>Auth required</small>
              <strong>{boolLabel(oidcReport.auth_required)}</strong>
            </span>
            <span>
              <small>Actor claim</small>
              <strong>{oidcReport.token_binding.actor_claim}</strong>
            </span>
          </div>
          <CheckList checks={oidcReport.checks} />
        </section>

        <section className="panel">
          <div className="section-heading-row">
            <div>
              <p className="section-label">Deployment posture</p>
              <h2 className="panel-title">{deploymentReport.profile}</h2>
            </div>
            <SettingsStatusPill status={deploymentReport.status} />
          </div>
          <div className="settings-summary-grid">
            <span>
              <small>Environment</small>
              <strong>{deploymentReport.environment}</strong>
            </span>
            <span>
              <small>Demo safe</small>
              <strong>{boolLabel(deploymentReport.demo_safe)}</strong>
            </span>
            <span>
              <small>Production ready</small>
              <strong>{boolLabel(deploymentReport.production_ready)}</strong>
            </span>
            <span>
              <small>Object store</small>
              <strong>{String(deploymentReport.capabilities.object_store_adapter)}</strong>
            </span>
          </div>
          <CheckList checks={requiredDeploymentChecks} />
        </section>
      </div>

      <div className="settings-layout">
        <section className="panel">
          <div className="section-heading-row">
            <div>
              <p className="section-label">Runtime dependencies</p>
              <h2 className="panel-title">Axis API boundary</h2>
            </div>
            <SettingsStatusPill status={readyReport.status} />
          </div>
          <div className="settings-dependency-grid">
            {Object.entries(readyReport.dependencies).map(([dependency, reachable]) => (
              <span key={dependency}>
                <Database size={16} />
                <strong>{compactId(dependency)}</strong>
                <small className={reachable ? "signal-ready" : "signal-action-required"}>
                  {reachable ? "reachable" : "not configured"}
                </small>
              </span>
            ))}
          </div>
          <div className="row">
            <div>
              <p className="row-title">External model egress</p>
              <p className="row-detail">
                Axis reports this from `/ready`; no browser-local policy is synthesized.
              </p>
            </div>
            <span
              className={`status-pill ${
                readyReport.external_model_egress_enabled
                  ? "signal-action-required"
                  : "signal-ready"
              }`}
            >
              {boolLabel(readyReport.external_model_egress_enabled)}
            </span>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading-row">
            <div>
              <p className="section-label">Support diagnostics</p>
              <h2 className="panel-title">Public-safe support bundle</h2>
            </div>
            <SettingsStatusPill status={supportReport.status} />
          </div>
          <div className="settings-summary-grid">
            <span>
              <small>Safe to share</small>
              <strong>{boolLabel(supportReport.safe_to_share)}</strong>
            </span>
            <span>
              <small>Demo support</small>
              <strong>{boolLabel(supportReport.demo_support_ready)}</strong>
            </span>
            <span>
              <small>Production support</small>
              <strong>{boolLabel(supportReport.production_support_ready)}</strong>
            </span>
            <span>
              <small>Session actor</small>
              <strong>
                {identityReport.authenticated ? identityReport.actor_id : "public evaluation"}
              </strong>
            </span>
          </div>
          <div className="tag-list">
            {supportReport.redaction_policy.map((policy) => (
              <span className="tag" key={policy}>
                {compactId(policy)}
              </span>
            ))}
          </div>
          <CheckList checks={supportReport.checks} />
        </section>
      </div>
    </ConsolePage>
  );
}
