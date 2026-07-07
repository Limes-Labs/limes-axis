"use client";

import Link from "next/link";
import { useState } from "react";
import { RadioTower, RotateCcw, ScrollText, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
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

  const denyCount = countPoliciesByEffect(registry.policies, "deny");
  const requireApprovalCount = countPoliciesByEffect(registry.policies, "require_approval");
  const evidenceCount = countPoliciesByEffect(registry.policies, "allow_with_evidence");

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Platform Policy Registry</p>
          <h2 className="panel-title">Tenant policy rules</h2>
          <p className="row-detail">
            Versioned governance rules for {registry.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Policy source and registry status">
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

      <div className="metric-grid">
        <article className="metric-card compact-card">
          <p className="metric-label">Policies</p>
          <p className="metric-value">{registry.policy_count}</p>
          <p className="metric-detail">Tenant-scoped rules matching the current filters</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Deny</p>
          <p className="metric-value">{denyCount}</p>
          <p className="metric-detail">Hard blocks that reject matching action runs</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Require Approval</p>
          <p className="metric-value">{requireApprovalCount}</p>
          <p className="metric-detail">Rules that force the human approval gate</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Allow With Evidence</p>
          <p className="metric-value">{evidenceCount}</p>
          <p className="metric-detail">Rules that record decision evidence on execution</p>
        </article>
      </div>

      <section className="panel agent-filter-panel">
        <div>
          <p className="section-label">Filters</p>
          <h2 className="panel-title">Policy registry</h2>
        </div>
        <div className="agent-filters">
          <label>
            <span className="metric-label">Scope</span>
            <select
              value={filters.scope}
              onChange={(event) => updateFilter("scope", event.target.value)}
            >
              <option value={allPolicyFilter}>All scopes</option>
              {platformPolicyScopes.map((scope) => (
                <option key={scope} value={scope}>
                  {policyScopeLabel(scope)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Status</span>
            <select
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value={allPolicyFilter}>All statuses</option>
              {platformPolicyStatuses.map((status) => (
                <option key={status} value={status}>
                  {policyStatusLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={resetFilters} title="Reset filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      {registry.policies.length > 0 ? (
        <section className="table-panel">
          <table className="data-table">
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
              {registry.policies.map((policy) => (
                <tr key={`${policy.policy_id}-${policy.revision_number}`}>
                  <td>
                    <Link className="text-link" href={`/policies/${policy.policy_id}`}>
                      {policy.display_name}
                    </Link>
                    <p className="row-detail mono">{policy.policy_id}</p>
                  </td>
                  <td>{policyScopeLabel(policy.scope)}</td>
                  <td>
                    <span className={`status-pill ${policyEffectClass(policy.effect)}`}>
                      {policyEffectLabel(policy.effect)}
                    </span>
                  </td>
                  <td>
                    <p className="row-detail">{summarizePolicyConditions(policy.conditions)}</p>
                  </td>
                  <td>
                    <span className="mono">
                      r{policy.revision_number} / {policy.policy_version}
                    </span>
                  </td>
                  <td>
                    <span className={`status-pill ${policyStatusClass(policy.status)}`}>
                      {policyStatusLabel(policy.status)}
                    </span>
                  </td>
                  <td>
                    <p className="row-detail">{formatOverviewTimestamp(policy.created_at)}</p>
                    <p className="row-detail">{policy.created_by}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : (
        <section className="panel overview-context">
          <div>
            <p className="section-label">Registry</p>
            <h2 className="panel-title">No policies match the current filters</h2>
            <p className="row-detail">
              The policy API responded without records for this tenant, scope and status
              selection. Policies are authored through the API; this console is read and
              evaluate only.
            </p>
          </div>
          <span className="status-pill status-checking">
            <ScrollText size={15} />
            Empty registry
          </span>
        </section>
      )}

      <section className="panel">
        <p className="section-label">Evaluation Precedence</p>
        <div className="stack">
          {platformPolicyPrecedenceSteps.map((step) => (
            <p className="row-detail" key={step}>
              {step}
            </p>
          ))}
        </div>
      </section>

      {registry.policy_notes.length > 0 ? (
        <section className="panel">
          <p className="section-label">Registry Notes</p>
          <div className="stack">
            {registry.policy_notes.map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
