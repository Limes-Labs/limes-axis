"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell, CircleHelp, RefreshCw, Search, ShieldCheck } from "lucide-react";

import { ConsoleCommandMenu } from "@/components/console-command-menu";
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
  const [commandMenuOpen, setCommandMenuOpen] = useState(false);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTextInput =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandMenuOpen(true);
        return;
      }

      if (!isTextInput && event.key === "/") {
        event.preventDefault();
        setCommandMenuOpen(true);
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

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
        <button
          className="ops-icon-button"
          type="button"
          aria-label="Search console"
          title="Search console"
          onClick={() => setCommandMenuOpen(true)}
        >
          <Search size={17} />
        </button>
        <Link
          className="ops-icon-button"
          aria-label="Open audit notifications"
          href="/audit"
          title="Open audit notifications"
        >
          <Bell size={17} />
        </Link>
        <a
          className="ops-icon-button"
          aria-label="Open Axis docs"
          href="https://github.com/Limes-Labs/limes-axis/tree/main/docs"
          rel="noreferrer"
          target="_blank"
          title="Open Axis docs"
        >
          <CircleHelp size={17} />
        </a>
        <OidcSessionBridge />
        <span className="ops-user-chip" aria-label="Operator role">
          OP
        </span>
      </div>
      <ConsoleCommandMenu
        apiLabel={apiStatus.label}
        onClose={() => setCommandMenuOpen(false)}
        onRefresh={triggerRefresh}
        open={commandMenuOpen}
      />
    </header>
  );
}
