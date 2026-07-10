"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, History, RadioTower, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { TenantLifecycleActions } from "@/components/tenant-lifecycle-actions";
import { TenantQuotaEditor } from "@/components/tenant-quota-editor";
import { TenantUsagePanel } from "@/components/tenant-usage-panel";
import {
  buildPlatformTenantDetailPath,
  fetchTenantDetail,
  tenantStatusClass,
  tenantStatusLabel,
  type TenantRecord,
} from "@/lib/platform-tenants";
import { formatOverviewTimestamp } from "@/lib/platform-overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type DetailSource = "loading" | "api" | "unavailable" | "missing";

function sourceLabel(source: DetailSource): string {
  if (source === "api") {
    return "API tenant detail";
  }

  if (source === "missing") {
    return "Tenant not found";
  }

  return source === "loading" ? "Loading tenant API" : "Tenant API unavailable";
}

type TimelineEntry = {
  key: string;
  label: string;
  timestamp: string | null;
  actor: string | null;
  reason: string | null;
  auditEventId: string | null;
};

function buildTimeline(tenant: TenantRecord): TimelineEntry[] {
  const entries: TimelineEntry[] = [
    {
      key: "created",
      label: "Provisioned",
      timestamp: tenant.created_at,
      actor: tenant.created_by,
      reason: null,
      // The record only carries the latest audit event id; attribute it to the
      // creation entry only when no later lifecycle change has occurred.
      auditEventId:
        tenant.suspended_at || tenant.reactivated_at ? null : tenant.audit_event_id ?? null,
    },
  ];

  if (tenant.suspended_at) {
    entries.push({
      key: "suspended",
      label: "Suspended",
      timestamp: tenant.suspended_at,
      actor: tenant.suspended_by ?? null,
      reason: tenant.suspension_reason ?? null,
      auditEventId: tenant.status === "suspended" ? tenant.audit_event_id ?? null : null,
    });
  }

  if (tenant.reactivated_at) {
    entries.push({
      key: "reactivated",
      label: "Reactivated",
      timestamp: tenant.reactivated_at,
      actor: tenant.reactivated_by ?? null,
      reason: null,
      auditEventId: tenant.status === "active" ? tenant.audit_event_id ?? null : null,
    });
  }

  return entries;
}

export function TenantDetail({ tenantId }: { tenantId: string }) {
  const [tenant, setTenant] = useState<TenantRecord | null>(null);
  const [source, setSource] = useState<DetailSource>("loading");
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();

  useEffect(() => {
    const controller = new AbortController();

    async function loadTenant() {
      try {
        const result = await fetchTenantDetail(tenantId, {
          session,
          signal: controller.signal,
        });

        if (controller.signal.aborted) {
          return;
        }

        if (result.kind === "notFound") {
          setTenant(null);
          setSource("missing");
          return;
        }

        setTenant(result.record);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setTenant(null);
          setSource("unavailable");
        }
      }
    }

    void loadTenant();

    return () => controller.abort();
  }, [tenantId, session, refreshNonce]);

  if (!tenant) {
    if (source !== "missing") {
      return (
        <ApiRequiredState
          detail="Axis did not receive an API-backed platform tenant. Local fallback tenant records are disabled."
          endpoint={buildPlatformTenantDetailPath(tenantId)}
          title={source === "loading" ? "Loading tenant API" : "Tenant API unavailable"}
        />
      );
    }

    return (
      <div className="console-stack">
        <section className="panel overview-context">
          <div>
            <p className="section-label">Platform Tenant</p>
            <h2 className="panel-title">Tenant not found</h2>
            <p className="row-detail mono">{tenantId}</p>
            <p className="row-detail">
              The tenant read route returned 404: no tenant with this id is provisioned.
            </p>
          </div>
          <Link className="command-button" href="/tenants">
            <ArrowLeft size={17} />
            Tenants
          </Link>
        </section>
      </div>
    );
  }

  const timeline = buildTimeline(tenant);
  const notes = tenant.notes ?? [];

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Platform Tenant</p>
          <h2 className="panel-title">{tenant.display_name}</h2>
          <p className="row-detail">{tenant.description || "No description recorded."}</p>
          <p className="row-detail mono">{tenant.tenant_id}</p>
        </div>
        <div className="overview-meta" aria-label="Tenant source and status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${tenantStatusClass(tenant.status)}`}>
            <ShieldCheck size={15} />
            {tenantStatusLabel(tenant.status)}
          </span>
          <Link className="command-button" href="/tenants">
            <ArrowLeft size={17} />
            Tenants
          </Link>
        </div>
      </section>

      <div className="metric-grid">
        <article className="metric-card compact-card">
          <p className="metric-label">Status</p>
          <p className="metric-value">{tenantStatusLabel(tenant.status)}</p>
          <p className="metric-detail">Only active tenants can establish sessions</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Created By</p>
          <p className="metric-value">{tenant.created_by}</p>
          <p className="metric-detail">{formatOverviewTimestamp(tenant.created_at)}</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Bootstrap Admin</p>
          <p className="metric-value mono">{tenant.bootstrap_admin_actor_id ?? "None"}</p>
          <p className="metric-detail">Optional actor created at provisioning time</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Last Audit Event</p>
          <p className="metric-value">{tenant.audit_event_type}</p>
          <p className="metric-detail mono">{tenant.audit_event_id ?? "No audit id"}</p>
        </article>
      </div>

      <section className="panel">
        <div className="row">
          <div>
            <p className="section-label">Lifecycle Timeline</p>
            <h2 className="panel-title">Provisioning and lifecycle transitions</h2>
            <p className="row-detail">
              Every transition records the operator actor, an optional reason and append-only
              audit evidence.
            </p>
          </div>
          <History size={18} />
        </div>
        <div className="stack">
          {timeline.map((entry) => (
            <div className="approval-detail-grid" key={entry.key}>
              <div>
                <p className="metric-label">Event</p>
                <p className="row-title">{entry.label}</p>
                <p className="row-detail">
                  {entry.timestamp ? formatOverviewTimestamp(entry.timestamp) : "Unknown time"}
                </p>
              </div>
              <div>
                <p className="metric-label">Actor</p>
                <p className="row-detail">{entry.actor ?? "Unknown actor"}</p>
              </div>
              <div>
                <p className="metric-label">Reason</p>
                <p className="row-detail">{entry.reason ?? "No reason recorded"}</p>
              </div>
              <div>
                <p className="metric-label">Audit Event ID</p>
                <p className="row-detail mono">{entry.auditEventId ?? "Superseded by later event"}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <TenantLifecycleActions tenant={tenant} />

      <TenantUsagePanel tenantId={tenant.tenant_id} />

      <TenantQuotaEditor tenantId={tenant.tenant_id} />

      {notes.length > 0 ? (
        <section className="panel">
          <p className="section-label">Tenant Notes</p>
          <div className="stack">
            {notes.map((note) => (
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
