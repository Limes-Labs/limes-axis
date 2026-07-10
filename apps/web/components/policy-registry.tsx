"use client";

import Link from "next/link";
import { useState } from "react";
import { RadioTower, RotateCcw, ScrollText, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { PolicyCreateForm } from "@/components/policy-create-form";
import {
  allPolicyFilter,
  buildPlatformPoliciesPath,
  countPoliciesByEffect,
  platformPoliciesPath,
  platformPolicyPrecedenceSteps,
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
} from "@/lib/platform-policies";
import { formatOverviewTimestamp } from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";

const defaultFilters: PlatformPolicyRegistryFilters = {
  scope: allPolicyFilter,
  status: allPolicyFilter,
};

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API policy registry";
  }

  return source === "loading" ? "Loading policy API" : "Policy API unavailable";
}

export function PolicyRegistry() {
  const [filters, setFilters] = useState<PlatformPolicyRegistryFilters>(defaultFilters);
  const { data: registry, source } = useAxisQuery<PlatformPolicyRegistry>(
    buildPlatformPoliciesPath(filters),
  );

  function updateFilter(filterName: keyof PlatformPolicyRegistryFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [filterName]: value,
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  if (!registry) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed platform policy records. Local fallback policy records are disabled."
        endpoint={platformPoliciesPath}
        title={source === "loading" ? "Loading policy API" : "Policy API unavailable"}
      />
    );
  }

  const policies = registry.policies ?? [];
  const policyNotes = registry.policy_notes ?? [];
  const denyCount = countPoliciesByEffect(policies, "deny");
  const requireApprovalCount = countPoliciesByEffect(policies, "require_approval");
  const evidenceCount = countPoliciesByEffect(policies, "allow_with_evidence");

  return (
    <div className="grid min-w-0 gap-4">
      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Platform Policy Registry</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Tenant policy rules</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            Versioned governance rules for {registry.tenant_id}
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2" aria-label="Policy source and registry status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className="status-pill signal-watch">
            <ShieldCheck size={15} />
            {registry.active_policy_count} active
          </span>
        </div>
      </section>

      <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        <article className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">Policies</p>
          <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{registry.policy_count}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">Tenant-scoped rules matching the current filters</p>
        </article>
        <article className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">Deny</p>
          <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{denyCount}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">Hard blocks that reject matching action runs</p>
        </article>
        <article className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">Require Approval</p>
          <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{requireApprovalCount}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">Rules that force the human approval gate</p>
        </article>
        <article className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">Allow With Evidence</p>
          <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{evidenceCount}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">Rules that record decision evidence on execution</p>
        </article>
      </div>

      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Filters</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Policy registry</h2>
        </div>
        <div className="grid w-full min-w-0 gap-2.5 sm:flex sm:w-auto sm:flex-wrap sm:items-end sm:justify-end">
          <Field label="Scope">
            <Select
              value={filters.scope}
              onChange={(event) => updateFilter("scope", event.target.value)}
            >
              <option value={allPolicyFilter}>All scopes</option>
              {platformPolicyScopes.map((scope) => (
                <option key={scope} value={scope}>
                  {policyScopeLabel(scope)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Status">
            <Select
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value={allPolicyFilter}>All statuses</option>
              {platformPolicyStatuses.map((status) => (
                <option key={status} value={status}>
                  {policyStatusLabel(status)}
                </option>
              ))}
            </Select>
          </Field>
          <button className="icon-button" onClick={resetFilters} title="Reset filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      {policies.length > 0 ? (
        <section className="min-w-0 overflow-x-auto rounded-2xl border border-line bg-surface dark:border-white/10 dark:bg-white/5">
          <table className="w-full min-w-[640px] border-collapse text-left text-sm text-ink [&_th]:border-b [&_th]:border-line [&_th]:px-4 [&_th]:py-3 [&_th]:text-left [&_th]:font-mono [&_th]:text-[11px] [&_th]:font-medium [&_th]:tracking-[0.16em] [&_th]:uppercase [&_th]:text-signal dark:[&_th]:border-white/10 [&_td]:border-b [&_td]:border-line/60 [&_td]:px-4 [&_td]:py-3 [&_td]:align-top dark:[&_td]:border-white/6 [&_tbody_tr:last-child_td]:border-b-0">
            <thead>
              <tr>
                <th>Policy</th>
                <th>Scope</th>
                <th>Effect</th>
                <th>Conditions</th>
                <th>Revision</th>
                <th>Status</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((policy) => (
                <tr key={`${policy.policy_id}-${policy.revision_number}`}>
                  <td>
                    <Link className="font-medium text-signal underline decoration-1 underline-offset-2" href={`/policies/${policy.policy_id}`}>
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
                      r{policy.revision_number} / {policy.policy_version}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${policyStatusClass(policy.status)}`}>
                      {policyStatusLabel(policy.status)}
                    </span>
                  </td>
                  <td>
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{formatOverviewTimestamp(policy.created_at)}</p>
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.created_by}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : (
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">Registry</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">No policies match the current filters</h2>
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
              The policy API responded without records for this tenant, scope and status
              selection. Author the tenant&apos;s first policy with the form below.
            </p>
          </div>
          <span className="status-pill status-checking">
            <ScrollText size={15} />
            Empty registry
          </span>
        </section>
      )}

      <PolicyCreateForm tenantId={registry.tenant_id} />

      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
        <p className="eyebrow m-0">Evaluation Precedence</p>
        <div className="grid min-w-0 gap-2.5">
          {platformPolicyPrecedenceSteps.map((step) => (
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={step}>
              {step}
            </p>
          ))}
        </div>
      </section>

      {policyNotes.length > 0 ? (
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <p className="eyebrow m-0">Registry Notes</p>
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
