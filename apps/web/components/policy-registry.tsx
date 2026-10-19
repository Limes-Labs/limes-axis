"use client";

import Link from "next/link";
import { RotateCcw, ScrollText, ShieldCheck, TriangleAlert } from "lucide-react";

import { DataTable } from "@/components/ui/data-table";
import { Disclosure } from "@/components/ui/disclosure";
import { PolicyCreateForm } from "@/components/policy-create-form";
import {
  enumUrlField,
  opaqueStringUrlField,
  useConsoleUrlState,
} from "@/lib/console-url-state";
import {
  allPolicyFilter,
  buildPlatformPoliciesPath,
  countPoliciesByEffect,
  platformPolicyScopes,
  platformPolicyStatuses,
  policyEffectClass,
  policyEffectLabel,
  policyScopeLabel,
  policyStatusClass,
  policyStatusLabel,
  summarizePolicyConditions,
  type PlatformPolicyRegistry,
  type PlatformPolicyRegistryFilters,
  type PlatformPolicyScope,
} from "@/lib/platform-policies";
import { formatNumber, formatTimestamp } from "@/lib/format";
import { deriveSourceState, PROVENANCE_NOT_APPLICABLE } from "@/lib/source-state";
import { useStrings } from "@/providers/locale-provider";
import { parsePlatformPolicyRegistry } from "@/lib/runtime-contracts/policies";
import { useAxisQuery } from "@/lib/use-axis-query";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { SourcePill } from "@/components/ui/source-pill";
import { StatCard } from "@/components/ui/stat-card";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import { TemplateText } from "@/components/ui/template-text";
import {
  missingRequiredScopePermission,
  ScopeDenialPanel,
} from "@/components/ui/scope-denial";
import {
  IDENTITY_SESSION_ENDPOINT,
  useConsoleTenantScope,
} from "@/lib/use-console-tenant-scope";

const defaultFilters: PlatformPolicyRegistryFilters = {
  scope: allPolicyFilter,
  status: allPolicyFilter,
};
const policyUrlSchema = {
  scope: enumUrlField(
    "scope",
    [allPolicyFilter, ...platformPolicyScopes],
    allPolicyFilter,
  ),
  status: enumUrlField(
    "status",
    [allPolicyFilter, ...platformPolicyStatuses],
    allPolicyFilter,
  ),
  // Authoring confirmation marker. The success feedback is derived from the
  // refreshed registry (server truth) through this marker, so it survives
  // the query refresh that authoring itself triggers.
  authored: opaqueStringUrlField("authored"),
};

function isPlatformPolicyScope(value: string): value is PlatformPolicyScope {
  return platformPolicyScopes.some((scope) => scope === value);
}

export function PolicyRegistry() {
  const strings = useStrings();
  const [filters, setFilters] = useConsoleUrlState(policyUrlSchema);
  const authoredPolicyId = filters.authored;
  const { identity, tenantId, tenantQueriesEnabled } = useConsoleTenantScope();
  const registryPath = buildPlatformPoliciesPath(filters, tenantId ?? undefined);
  const {
    data: registry,
    errorCode: registryErrorCode,
    errorReason: registryErrorReason,
    errorRequiredPermission: registryErrorRequiredPermission,
    errorRequestId: registryErrorRequestId,
    errorStatus: registryErrorStatus,
    source,
  } = useAxisQuery<PlatformPolicyRegistry>(
    registryPath,
    {
      enabled: tenantQueriesEnabled,
      expectedTenantId: tenantId ?? undefined,
      parse: parsePlatformPolicyRegistry,
    },
  );

  function updateFilter(filterName: keyof PlatformPolicyRegistryFilters, value: string) {
    if (
      filterName === "scope"
      && (value === allPolicyFilter || isPlatformPolicyScope(value))
    ) {
      setFilters({ scope: value });
    }
    if (
      filterName === "status"
      && (value === allPolicyFilter || platformPolicyStatuses.some((status) => status === value))
    ) {
      setFilters({ status: value });
    }
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  function dismissAuthoredBanner() {
    setFilters({ authored: "" });
  }

  if (identity.source === "loading") {
    return <LoadingPanel layout="detail" />;
  }

  if (identity.source === "unavailable" || !tenantId) {
    return (
      <ErrorPanel
        detail={strings.ui.common.theConsoleCouldNotVerify}
        endpoint={IDENTITY_SESSION_ENDPOINT}
        reference={identity.errorRequestId ?? undefined}
        onRetry={identity.refetch}
        title={strings.states.identityUnavailable.title}
      />
    );
  }

  if (!registry) {
    if (source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    const deniedScope = missingRequiredScopePermission({
      errorCode: registryErrorCode,
      errorReason: registryErrorReason,
      errorRequiredPermission: registryErrorRequiredPermission,
      errorStatus: registryErrorStatus,
    });
    if (deniedScope) {
      return (
        <ScopeDenialPanel requiredPermission={deniedScope} subject="policy registry" />
      );
    }

    return (
      <ErrorPanel
        detail={strings.policyDetail.error.registryDetail}
        endpoint={registryPath}
        reference={registryErrorRequestId ?? undefined}
        title={strings.policyDetail.error.title}
      />
    );
  }

  const policies = registry.policies ?? [];
  const policyNotes = registry.policy_notes ?? [];
  const denyCount = countPoliciesByEffect(policies, "deny");
  const requireApprovalCount = countPoliciesByEffect(policies, "require_approval");
  const evidenceCount = countPoliciesByEffect(policies, "allow_with_evidence");

  const authoredRecord = authoredPolicyId
    ? policies.find((policy) => policy.policy_id === authoredPolicyId)
    : undefined;

  return (
    <div className="grid min-w-0 gap-4">
      {authoredPolicyId ? (
        authoredRecord ? (
          <div
            aria-label={strings.ui.policyRegistry.policyAuthoringResult}
            className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl border border-signal/30 bg-tint-50 px-4 py-3 dark:border-signal/40 dark:bg-signal/10"
            data-policy-authored={authoredRecord.policy_id}
            role="status"
          >
            <p className="m-0 min-w-0 text-sm leading-snug break-words text-ink">
              {strings.ui.policyRegistry.policyAuthored(
                authoredRecord.revision_number,
                authoredRecord.policy_version,
                authoredRecord.display_name,
              )}
            </p>
            <button
              className="inline-flex min-h-6 cursor-pointer items-center font-mono text-xs text-muted transition-colors hover:text-signal"
              onClick={dismissAuthoredBanner}
              type="button"
            >
              {strings.ui.common.dismiss}
            </button>
          </div>
        ) : (
          <div
            aria-label={strings.ui.policyRegistry.policyAuthoringResult}
            className="rounded-2xl border border-line bg-surface px-4 py-3 dark:border-white/10"
            role="status"
          >
            <p className="m-0 text-sm text-muted">
              {strings.ui.policyRegistry.authoredNotInView(authoredPolicyId)}
            </p>
          </div>
        )
      ) : null}
      <div
        aria-label={strings.ui.policyRegistry.policySourceAndRegistryStatus}
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm leading-snug break-words text-muted">
          <TemplateText
            template={strings.ui.policyRegistry.versionedRulesFor}
            values={{ tenant: <span title={registry.tenant_id}>{strings.identifiers.thisTenant}</span> }}
          />
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <SourcePill
            state={deriveSourceState(source, Boolean(registry), PROVENANCE_NOT_APPLICABLE)}
            subject="policy registry"
          />
          <span className="status-pill signal-watch">
            <ShieldCheck size={15} />
            {strings.ui.policyRegistry.activeCount(registry.active_policy_count)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 [&>*]:min-w-0" role="list">
        <StatCard
          detail={strings.ui.policyRegistry.tenantScopedRulesMatchingThe}
          label={strings.ui.common.policies}
          value={formatNumber(registry.policy_count)}
        />
        <StatCard
          detail={strings.ui.policyRegistry.hardBlocksThatRejectMatching}
          label={strings.ui.policyRegistry.deny}
          value={formatNumber(denyCount)}
        />
        <StatCard
          detail={strings.ui.policyRegistry.rulesThatForceTheHuman}
          label={strings.ui.policyRegistry.requireApproval}
          value={formatNumber(requireApprovalCount)}
        />
        <StatCard
          detail={strings.ui.policyRegistry.rulesThatRecordDecisionEvidence}
          label={strings.ui.policyRegistry.allowWithEvidence}
          value={formatNumber(evidenceCount)}
        />
      </div>

      <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow m-0">{strings.ui.common.filters}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.policyRegistry.policyRegistry}</h2>
        </div>
        <div className="grid w-full min-w-0 gap-2.5 sm:flex sm:w-auto sm:flex-wrap sm:items-end sm:justify-end">
          <Field label={strings.ui.common.scope}>
            <Select
              value={filters.scope}
              onChange={(event) => updateFilter("scope", event.target.value)}
            >
              <option value={allPolicyFilter}>{strings.ui.common.allScopes}</option>
              {platformPolicyScopes.map((scope) => (
                <option key={scope} value={scope}>
                  {policyScopeLabel(scope)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={strings.ui.common.status}>
            <Select
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value={allPolicyFilter}>{strings.ui.common.allStatuses}</option>
              {platformPolicyStatuses.map((status) => (
                <option key={status} value={status}>
                  {policyStatusLabel(status)}
                </option>
              ))}
            </Select>
          </Field>
          <button className="icon-button" onClick={resetFilters} title={strings.ui.common.resetFilters} type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      {policies.length > 0 ? (
        <DataTable wrapperProps={{ className: "min-w-0" }}>
          <thead>
            <tr>
              <th>{strings.ui.common.policy}</th>
              <th>{strings.ui.common.scope}</th>
              <th>{strings.ui.common.effect}</th>
              <th>{strings.ui.common.conditions}</th>
              <th>{strings.ui.common.revision}</th>
              <th>{strings.ui.common.status}</th>
              <th>{strings.ui.common.updated}</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((policy) => (
              <tr key={`${policy.policy_id}-${policy.revision_number}`}>
                <td>
                  <Link className="inline-flex min-h-6 items-center font-medium text-signal underline decoration-1 underline-offset-2" href={`/policies/${policy.policy_id}`}>
                    {policy.display_name}
                  </Link>
                  <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{policy.policy_id}</p>
                </td>
                <td>{policyScopeLabel(policy.scope)}</td>
                <td>
                  <span className={`status-pill ${policyEffectClass(policy.effect)}`}>
                    {policyEffectLabel(policy.effect)}
                  </span>
                </td>
                <td>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{summarizePolicyConditions(policy.conditions)}</p>
                </td>
                <td>
                  <span className="font-mono text-[13px] break-words">
                    {strings.ui.common.revisionVersion(policy.revision_number, policy.policy_version)}
                  </span>
                </td>
                <td>
                  <span className={`status-pill ${policyStatusClass(policy.status)}`}>
                    {policyStatusLabel(policy.status)}
                  </span>
                </td>
                <td>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{formatTimestamp(policy.created_at)}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.created_by}</p>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      ) : (
        <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">{strings.ui.common.registry}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.policyRegistry.noPoliciesMatchTheCurrent}</h2>
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
              {strings.ui.policyRegistry.thePolicyApiRespondedWithout}
            </p>
          </div>
          <span className="status-pill status-checking">
            <ScrollText size={15} />
            {strings.ui.common.emptyRegistry}
          </span>
        </section>
      )}

      {/* The default outcome is easy to miss and has the largest blast
          radius, so it gets its own callout instead of a footnote. */}
      <aside
        aria-label={strings.policyDetail.precedence.defaultAllowTitle}
        className="flex min-w-0 items-start gap-3 rounded-2xl border border-warning/40 bg-warning/8 p-4 dark:border-warning/40 dark:bg-warning/10"
        data-default-allow-callout
      >
        <TriangleAlert aria-hidden="true" className="mt-0.5 shrink-0 text-warning" size={18} />
        <div className="grid min-w-0 gap-1">
          <p className="m-0 font-medium text-ink">{strings.policyDetail.precedence.defaultAllowTitle}</p>
          <p className="m-0 text-sm leading-snug text-muted">
            {strings.policyDetail.precedence.defaultAllowDetail}
          </p>
        </div>
      </aside>

      <Disclosure title={strings.clarity.createPolicy}>
        <PolicyCreateForm tenantId={registry.tenant_id} />
      </Disclosure>

      <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
        <p className="eyebrow m-0">{strings.policyDetail.precedence.eyebrow}</p>
        <h2 className="font-display mx-0 mt-1 mb-3 text-xl text-ink">
          {strings.policyDetail.precedence.title}
        </h2>
        <div className="grid min-w-0 gap-2.5">
          {strings.policyDetail.precedence.steps.map((step) => (
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={step}>
              {step}
            </p>
          ))}
        </div>
      </section>

      {policyNotes.length > 0 ? (
        <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <p className="eyebrow m-0">{strings.ui.common.registryNotes}</p>
          <div className="grid min-w-0 gap-2.5">
            {policyNotes.map((note) => (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={note}>
                {note}
              </p>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
