"use client";

import Link from "next/link";
import { useState } from "react";
import { Building2, RadioTower, RotateCcw, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { TenantProvisionForm } from "@/components/tenant-provision-form";
import {
  allTenantFilter,
  buildPlatformTenantsPath,
  platformTenantsPath,
  tenantLifecycleStatuses,
  tenantStatusClass,
  tenantStatusLabel,
  type TenantLifecycleStatus,
  type TenantRegistry as TenantRegistryData,
  type TenantRegistryFilters,
} from "@/lib/platform-tenants";
import { formatOverviewTimestamp } from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";

const defaultFilters: TenantRegistryFilters = {
  status: allTenantFilter,
};

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API tenant registry";
  }

  return source === "loading" ? "Loading tenant API" : "Tenant API unavailable";
}

export function TenantRegistry() {
  const [filters, setFilters] = useState<TenantRegistryFilters>(defaultFilters);
  const { data: registry, source } = useAxisQuery<TenantRegistryData>(
    buildPlatformTenantsPath(filters),
  );

  function updateStatus(value: string) {
    setFilters({ status: value as TenantRegistryFilters["status"] });
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  if (!registry) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed platform tenant records. Local fallback tenant records are disabled."
        endpoint={platformTenantsPath}
        title={source === "loading" ? "Loading tenant API" : "Tenant API unavailable"}
      />
    );
  }

  const tenants = registry.tenants ?? [];
  const tenantNotes = registry.tenant_notes ?? [];
  const suspendedCount = tenants.filter((tenant) => tenant.status === "suspended").length;
  const pendingDeletionCount = tenants.filter(
    (tenant) => tenant.status === "pending_deletion",
  ).length;

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Platform Tenant Registry</p>
          <h2 className="panel-title">Tenant lifecycle</h2>
          <p className="row-detail">
            Cross-tenant operator surface. Requires the platform:tenant:operator scope plus a
            per-action scope; every lifecycle change appends audit evidence.
          </p>
        </div>
        <div className="overview-meta" aria-label="Tenant source and registry status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className="status-pill signal-watch">
            <ShieldCheck size={15} />
            {registry.active_tenant_count} active
          </span>
        </div>
      </section>

      <div className="metric-grid">
        <article className="metric-card compact-card">
          <p className="metric-label">Tenants</p>
          <p className="metric-value">{registry.tenant_count}</p>
          <p className="metric-detail">Tenants matching the current status filter</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Active</p>
          <p className="metric-value">{registry.active_tenant_count}</p>
          <p className="metric-detail">Tenants able to establish sessions</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Suspended</p>
          <p className="metric-value">{suspendedCount}</p>
          <p className="metric-detail">Rejected fail-closed at the OIDC principal boundary</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Pending Deletion</p>
          <p className="metric-value">{pendingDeletionCount}</p>
          <p className="metric-detail">Modeled and blocked; no deletion pipeline yet</p>
        </article>
      </div>

      <section className="panel agent-filter-panel">
        <div>
          <p className="section-label">Filters</p>
          <h2 className="panel-title">Tenant registry</h2>
        </div>
        <div className="agent-filters">
          <label>
            <span className="metric-label">Status</span>
            <select value={filters.status} onChange={(event) => updateStatus(event.target.value)}>
              <option value={allTenantFilter}>All statuses</option>
              {tenantLifecycleStatuses.map((status: TenantLifecycleStatus) => (
                <option key={status} value={status}>
                  {tenantStatusLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={resetFilters} title="Reset filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      {tenants.length > 0 ? (
        <section className="table-panel">
          <table className="data-table">
            <thead>
              <tr>
                <th>Tenant</th>
                <th>Status</th>
                <th>Created by</th>
                <th>Lifecycle</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((tenant) => (
                <tr key={tenant.tenant_id}>
                  <td>
                    <Link className="text-link" href={`/tenants/${tenant.tenant_id}`}>
                      {tenant.display_name}
                    </Link>
                    <p className="row-detail mono">{tenant.tenant_id}</p>
                  </td>
                  <td>
                    <span className={`status-pill ${tenantStatusClass(tenant.status)}`}>
                      {tenantStatusLabel(tenant.status)}
                    </span>
                  </td>
                  <td>
                    <p className="row-detail">{tenant.created_by}</p>
                  </td>
                  <td>
                    {tenant.status === "suspended" ? (
                      <p className="row-detail">
                        Suspended by {tenant.suspended_by ?? "unknown"}
                        {tenant.suspension_reason ? ` — ${tenant.suspension_reason}` : ""}
                      </p>
                    ) : tenant.reactivated_at ? (
                      <p className="row-detail">
                        Reactivated by {tenant.reactivated_by ?? "unknown"}
                      </p>
                    ) : (
                      <p className="row-detail">No lifecycle changes</p>
                    )}
                  </td>
                  <td>
                    <p className="row-detail">{formatOverviewTimestamp(tenant.updated_at)}</p>
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
            <h2 className="panel-title">No tenants match the current filter</h2>
            <p className="row-detail">
              The tenant API responded without records for this status selection. Provision the
              first tenant with the form below.
            </p>
          </div>
          <span className="status-pill status-checking">
            <Building2 size={15} />
            Empty registry
          </span>
        </section>
      )}

      <TenantProvisionForm />

      {tenantNotes.length > 0 ? (
        <section className="panel">
          <p className="section-label">Registry Notes</p>
          <div className="stack">
            {tenantNotes.map((note) => (
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
