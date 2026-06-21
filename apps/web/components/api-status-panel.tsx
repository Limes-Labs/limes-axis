"use client";

import { useEffect, useState } from "react";
import { Activity, ServerCrash } from "lucide-react";

import {
  getApiBaseUrl,
  summarizeApiStatus,
  type ApiStatusSummary,
} from "@/lib/api-status";

const checkingStatus: ApiStatusSummary = {
  state: "checking",
  label: "Checking",
  detail: "Reading API health and readiness.",
};

async function endpointResponds(url: string, signal: AbortSignal): Promise<boolean> {
  const response = await fetch(url, { signal, cache: "no-store" });
  return response.ok;
}

export function ApiStatusPanel() {
  const [status, setStatus] = useState<ApiStatusSummary>(checkingStatus);
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function probeApi() {
      try {
        const [healthOk, readyOk] = await Promise.all([
          endpointResponds(`${apiBaseUrl}/health`, controller.signal),
          endpointResponds(`${apiBaseUrl}/ready`, controller.signal),
        ]);
        setStatus(summarizeApiStatus({ healthOk, readyOk }));
      } catch {
        setStatus(summarizeApiStatus({ healthOk: false, readyOk: false }));
      }
    }

    void probeApi();

    return () => controller.abort();
  }, [apiBaseUrl]);

  const Icon = status.state === "unavailable" ? ServerCrash : Activity;

  return (
    <section className="panel api-status-panel">
      <div>
        <p className="section-label">API Status</p>
        <h2 className="panel-title">Control API</h2>
      </div>
      <div className="api-status-body">
        <span className={`status-pill status-${status.state}`}>
          <Icon size={15} />
          {status.label}
        </span>
        <p className="row-detail">{status.detail}</p>
        <p className="mono api-url">{apiBaseUrl}</p>
      </div>
    </section>
  );
}
