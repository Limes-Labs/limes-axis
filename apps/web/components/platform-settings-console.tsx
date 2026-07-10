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
    <div className="grid min-w-0 gap-2.5 border-t border-line/60 pt-2 dark:border-white/10">
      {checks.map((check) => (
        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10" key={check.check_id}>
          <div>
            <p className="m-0 font-medium text-ink break-words">{compactId(check.check_id)}</p>
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{check.detail}</p>
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
      <ConsolePage pageKey="settings" sourceLabel={sourceLabel}>
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
    <ConsolePage pageKey="settings" sourceLabel={sourceLabel}>
      <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0" aria-label="Platform readiness metrics">
        {cards.map((card) => {
          const Icon = card.icon;

          return (
            <article
              className="grid min-w-0 content-start gap-2 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5"
              data-kpi-card
              key={card.label}
            >
              <Icon className="text-signal" size={22} strokeWidth={1.6} />
              <p className="eyebrow m-0">{card.label}</p>
              <p
                className={`font-display m-0 text-xl break-words ${
                  card.status === "ready" ? "text-positive" : "text-danger"
                }`}
              >
                {card.value}
              </p>
              <div aria-hidden="true" className="rule-dotted" />
              <p className="m-0 text-xs leading-snug text-muted break-words">{card.detail}</p>
            </article>
          );
        })}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Identity and SSO</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">OIDC readiness</h2>
            </div>
            <SettingsStatusPill status={oidcReport.status} />
          </div>
          <div className="mb-3.5 grid gap-2.5 sm:grid-cols-2 [&>span]:grid [&>span]:min-w-0 [&>span]:gap-1 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:text-[11px] [&_small]:font-medium [&_small]:tracking-wide [&_small]:uppercase [&_small]:text-muted [&_strong]:min-w-0 [&_strong]:break-words [&_strong]:text-[13px] [&_strong]:leading-tight [&_strong]:text-ink">
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

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Deployment posture</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{deploymentReport.profile}</h2>
            </div>
            <SettingsStatusPill status={deploymentReport.status} />
          </div>
          <div className="mb-3.5 grid gap-2.5 sm:grid-cols-2 [&>span]:grid [&>span]:min-w-0 [&>span]:gap-1 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:text-[11px] [&_small]:font-medium [&_small]:tracking-wide [&_small]:uppercase [&_small]:text-muted [&_strong]:min-w-0 [&_strong]:break-words [&_strong]:text-[13px] [&_strong]:leading-tight [&_strong]:text-ink">
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
            <span>
              <small>WORM retention</small>
              <strong>
                {boolLabel(Boolean(deploymentReport.capabilities.object_store_worm_retention_enabled))}
              </strong>
            </span>
            <span>
              <small>Retention mode</small>
              <strong>
                {String(deploymentReport.capabilities.object_store_retention_mode)}
              </strong>
            </span>
            <span>
              <small>Retention days</small>
              <strong>
                {String(deploymentReport.capabilities.object_store_retention_days)}
              </strong>
            </span>
          </div>
          <CheckList checks={requiredDeploymentChecks} />
        </section>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Runtime dependencies</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Axis API boundary</h2>
            </div>
            <SettingsStatusPill status={readyReport.status} />
          </div>
          <div className="mb-3.5 grid gap-2.5 sm:grid-cols-2 [&>span]:grid [&>span]:min-w-0 [&>span]:gap-1 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:text-[11px] [&_small]:font-medium [&_small]:tracking-wide [&_small]:uppercase [&_small]:text-muted [&_strong]:min-w-0 [&_strong]:break-words [&_strong]:text-[13px] [&_strong]:leading-tight [&_strong]:text-ink [&>span]:grid-cols-[auto_minmax(0,1fr)] [&>span]:items-center [&_small]:col-start-2 [&_small]:normal-case [&_small]:tracking-normal">
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
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
            <div>
              <p className="m-0 font-medium text-ink break-words">External model egress</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
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

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Support diagnostics</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Public-safe support bundle</h2>
            </div>
            <SettingsStatusPill status={supportReport.status} />
          </div>
          <div className="mb-3.5 grid gap-2.5 sm:grid-cols-2 [&>span]:grid [&>span]:min-w-0 [&>span]:gap-1 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:text-[11px] [&_small]:font-medium [&_small]:tracking-wide [&_small]:uppercase [&_small]:text-muted [&_strong]:min-w-0 [&_strong]:break-words [&_strong]:text-[13px] [&_strong]:leading-tight [&_strong]:text-ink">
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
            <span>
              <small>Object retention</small>
              <strong>
                {supportReport.diagnostics.object_store_worm_retention_enabled
                  ? `${supportReport.diagnostics.object_store_retention_mode} / ${supportReport.diagnostics.object_store_retention_days}d`
                  : "Action required"}
              </strong>
            </span>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2">
            {supportReport.redaction_policy.map((policy) => (
              <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={policy}>
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
