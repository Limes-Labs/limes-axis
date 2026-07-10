"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

import {
  buildPlatformTenantUsagePath,
  defaultUsageWindowDays,
  fetchTenantUsage,
  platformTenantUsageScope,
  summarizeUsageByMetric,
  type TenantUsageSummary,
  type UsageMetricSummaryRow,
} from "@/lib/platform-tenant-usage";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type UsageSource = "loading" | "api" | "unavailable" | "missing";

function sourceLabel(source: UsageSource): string {
  if (source === "api") {
    return "API usage ledger";
  }

  if (source === "missing") {
    return "Tenant not found";
  }

  return source === "loading" ? "Loading usage API" : "Usage API unavailable";
}

export function TenantUsagePanel({ tenantId }: { tenantId: string }) {
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();
  const [summary, setSummary] = useState<TenantUsageSummary | null>(null);
  const [source, setSource] = useState<UsageSource>("loading");

  useEffect(() => {
    const controller = new AbortController();

    async function loadUsage() {
      setSource("loading");

      try {
        const result = await fetchTenantUsage(
          tenantId,
          { session, signal: controller.signal },
          defaultUsageWindowDays,
        );

        if (controller.signal.aborted) {
          return;
        }

        if (result === null) {
          setSummary(null);
          setSource("missing");
          return;
        }

        setSummary(result);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setSummary(null);
          setSource("unavailable");
        }
      }
    }

    void loadUsage();

    return () => controller.abort();
  }, [tenantId, session, refreshNonce]);

  const rows: UsageMetricSummaryRow[] = summarizeUsageByMetric(summary);
  const usageNotes = summary?.usage_notes ?? [];

  return (
    <section className="panel">
      <div className="row">
        <div>
          <p className="section-label">Usage Metering</p>
          <h2 className="panel-title">Consumption over the last {defaultUsageWindowDays} days</h2>
          <p className="row-detail">
            Reads GET /platform/tenants/{tenantId}/usage. Requires the{" "}
            {platformTenantUsageScope} scope. Metering is cumulative consumption
            accounting; quotas remain the enforcement ceilings.
          </p>
          <p className="row-detail mono">{buildPlatformTenantUsagePath(tenantId)}</p>
        </div>
        <Activity size={18} />
      </div>

      {source !== "api" ? (
        <p className="row-detail" role="status">
          {sourceLabel(source)}
        </p>
      ) : rows.length === 0 ? (
        <p className="row-detail" role="status">
          No metered consumption in this window.
        </p>
      ) : (
        <div className="metric-grid" aria-label="Per-metric consumption">
          {rows.map((row) => (
            <article className="metric-card compact-card" key={row.metricKey}>
              <p className="metric-label">{row.label}</p>
              <p className="metric-value">{row.total.toLocaleString()}</p>
              <p className="metric-detail">
                {row.periodCount} {row.periodCount === 1 ? "period" : "periods"} in window
              </p>
            </article>
          ))}
        </div>
      )}

      {usageNotes.length > 0 ? (
        <div className="stack">
          {usageNotes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
