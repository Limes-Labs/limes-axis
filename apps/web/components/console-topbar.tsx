"use client";

import { Bell, CircleHelp, RefreshCw, Search, ShieldCheck } from "lucide-react";

import { OidcSessionBridge } from "@/components/oidc-session-bridge";
import { useConsole } from "@/providers/console-provider";

function apiStatusClass(state: string): string {
  if (state === "online") {
    return "signal-ready";
  }

  if (state === "degraded" || state === "checking") {
    return "signal-watch";
  }

  return "signal-action-required";
}

export function ConsoleTopbar({
  sourceLabel,
  evidenceLabel,
}: {
  sourceLabel?: string;
  evidenceLabel?: string;
}) {
  const { apiStatus, triggerRefresh } = useConsole();

  return (
    <header className="ops-topbar" aria-label="Console status bar">
      <div className="ops-topbar-left">
        <span className="ops-product-pill">
          <ShieldCheck size={17} />
          Sovereign Control
        </span>
      </div>
      <div className="ops-live-pills">
        <span className={`status-pill ${apiStatusClass(apiStatus.state)}`} title={apiStatus.detail}>
          <span aria-hidden="true" className={`status-dot ${apiStatusClass(apiStatus.state)}`} />
          API {apiStatus.label}
        </span>
        {sourceLabel ? (
          <span className="status-pill signal-ready">{sourceLabel}</span>
        ) : null}
        {evidenceLabel ? (
          <span className="status-pill signal-ready">{evidenceLabel}</span>
        ) : null}
      </div>
      <div className="ops-toolbar-icons" aria-label="Utility actions">
        <button
          className="ops-icon-button"
          type="button"
          aria-label="Refresh state"
          title="Refresh state"
          onClick={triggerRefresh}
        >
          <RefreshCw size={17} />
        </button>
        <button className="ops-icon-button" type="button" aria-label="Search" title="Search">
          <Search size={17} />
        </button>
        <button
          className="ops-icon-button"
          type="button"
          aria-label="Notifications"
          title="Notifications"
        >
          <Bell size={17} />
        </button>
        <button className="ops-icon-button" type="button" aria-label="Help" title="Help">
          <CircleHelp size={17} />
        </button>
        <OidcSessionBridge />
        <span className="ops-user-chip" aria-label="Operator role">
          OP
        </span>
      </div>
    </header>
  );
}