"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Bell,
  CircleHelp,
  KeyRound,
  LogOut,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";

import { ConsoleCommandMenu } from "@/components/console-command-menu";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import type { ManufacturingOverview, PlatformStatus } from "@/lib/platform-overview";
import { useConsole } from "@/providers/console-provider";

type TopbarPanel = "notifications" | "help" | "account" | null;

function apiStatusClass(state: string): string {
  if (state === "online") {
    return "signal-ready";
  }

  if (state === "degraded" || state === "checking") {
    return "signal-watch";
  }

  return "signal-action-required";
}

function platformTone(status: PlatformStatus): string {
  if (status === "ready") {
    return "signal-ready";
  }

  return status === "watch" ? "signal-watch" : "signal-action-required";
}

function compactActorLabel(actorId: string): string {
  return actorId.length > 30 ? `${actorId.slice(0, 27)}...` : actorId;
}

function operatorInitials(actorId?: string): string {
  if (!actorId) {
    return "OP";
  }

  const parts = actorId
    .split(/[^a-zA-Z0-9]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  const letters = (parts.length > 1 ? [parts[0], parts[1]] : [actorId.slice(0, 2)])
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return letters || "OP";
}

function formatExpiry(expiresAt?: number): string {
  if (!expiresAt) {
    return "Not provided";
  }

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(expiresAt * 1000));
}

function NotificationPanel({ overview }: { overview: ManufacturingOverview | null }) {
  if (!overview) {
    return (
      <section className="topbar-popover" aria-label="Notifications">
        <div className="topbar-popover-header">
          <p className="section-label">Notifications</p>
          <span className="status-pill signal-action-required">API required</span>
        </div>
        <p className="row-detail">
          Live notification data requires `/demo/manufacturing/overview`.
        </p>
      </section>
    );
  }

  const approvalItems = overview.approvals.slice(0, 3).map((approval) => ({
    detail: `${approval.requested_by} / ${approval.due}`,
    key: approval.approval_id,
    label: approval.action,
    tone: approval.risk_level === "high" ? "signal-watch" : "signal-ready",
  }));
  const riskItems = overview.risk_signals.slice(0, 3).map((signal) => ({
    detail: signal.evidence,
    key: signal.title,
    label: signal.title,
    tone: platformTone(signal.severity),
  }));
  const items = [...riskItems, ...approvalItems].slice(0, 5);

  return (
    <section className="topbar-popover" aria-label="Notifications">
      <div className="topbar-popover-header">
        <p className="section-label">Notifications</p>
        <span className="status-pill signal-ready">{items.length} live</span>
      </div>
      <div className="topbar-popover-list">
        {items.map((item) => (
          <div className="topbar-popover-row" key={item.key}>
            <span aria-hidden="true" className={`status-dot ${item.tone}`} />
            <span>
              <strong>{item.label}</strong>
              <small>{item.detail}</small>
            </span>
          </div>
        ))}
      </div>
      <a className="topbar-popover-link" href="/audit">
        Open audit evidence
      </a>
    </section>
  );
}

function HelpPanel() {
  return (
    <section className="topbar-popover" aria-label="Platform help">
      <div className="topbar-popover-header">
        <p className="section-label">Platform help</p>
        <span className="status-pill signal-ready">Docs</span>
      </div>
      <div className="topbar-popover-list">
        <a className="topbar-popover-row" href="/model-routing">
          <ShieldCheck size={16} />
          <span>
            <strong>Model routing</strong>
            <small>Inspect provider boundaries and egress decisions.</small>
          </span>
        </a>
        <a
          className="topbar-popover-row"
          href="https://github.com/Limes-Labs/limes-axis/blob/main/docs/architecture.md"
          rel="noreferrer"
          target="_blank"
        >
          <CircleHelp size={16} />
          <span>
            <strong>Architecture docs</strong>
            <small>Open the public platform architecture notes.</small>
          </span>
        </a>
      </div>
    </section>
  );
}

function AccountPanel() {
  const { session, saveAccessToken, clearSession } = useOidcConsoleSession();
  const { apiBaseUrl, apiStatus } = useConsole();
  const [accessToken, setAccessToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  function connectSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const token = accessToken.trim();
    if (!token) {
      setError("Paste a JWT bearer token to bridge an OIDC session.");
      return;
    }

    try {
      saveAccessToken(token);
      setAccessToken("");
      setError(null);
    } catch {
      setError("Token rejected. Axis expects a JWT with sub and axis_tenant claims.");
    }
  }

  return (
    <section className="topbar-popover account-popover" aria-label="Operator account">
      <div className="topbar-popover-header">
        <p className="section-label">Operator</p>
        <span className={`status-pill ${apiStatusClass(apiStatus.state)}`}>{apiStatus.label}</span>
      </div>

      <div className="account-summary">
        <div className="account-avatar">{operatorInitials(session?.actorId)}</div>
        <div>
          <p className="row-title">{session ? compactActorLabel(session.actorId) : "Unauthenticated operator"}</p>
          <p className="row-detail">
            {session ? session.tenantId : "Public evaluation data / OIDC bridge not connected"}
          </p>
        </div>
      </div>

      <div className="account-grid">
        <span>
          <small>API</small>
          <strong>{apiBaseUrl}</strong>
        </span>
        <span>
          <small>Session expires</small>
          <strong>{formatExpiry(session?.expiresAt)}</strong>
        </span>
      </div>

      {session ? (
        <>
          <div className="tag-list account-scope-list">
            {session.scopes.length > 0 ? (
              session.scopes.slice(0, 6).map((scope) => (
                <span className="tag" key={scope}>
                  {scope}
                </span>
              ))
            ) : (
              <span className="tag">No scopes in token</span>
            )}
          </div>
          <button className="command-button account-command" onClick={clearSession} type="button">
            <LogOut size={16} />
            Clear session
          </button>
        </>
      ) : (
        <form className="account-token-form" onSubmit={connectSession}>
          <label>
            OIDC bearer token
            <input
              aria-invalid={Boolean(error)}
              onChange={(event) => {
                setAccessToken(event.target.value);
                setError(null);
              }}
              placeholder="Paste JWT access token"
              type="password"
              value={accessToken}
            />
          </label>
          {error ? (
            <span className="session-bridge-error" role="status">
              {error}
            </span>
          ) : null}
          <button className="command-button account-command" type="submit">
            <KeyRound size={16} />
            Connect session
          </button>
        </form>
      )}
    </section>
  );
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
  const [activePanel, setActivePanel] = useState<TopbarPanel>(null);
  const { data: overview } = useAxisQuery<ManufacturingOverview>("/demo/manufacturing/overview");
  const { session } = useOidcConsoleSession();

  const notificationCount = useMemo(() => {
    if (!overview) {
      return 0;
    }

    return Math.min(9, overview.risk_signals.length + overview.approvals.length);
  }, [overview]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTextInput =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.isContentEditable;

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setActivePanel(null);
        setCommandMenuOpen(true);
        return;
      }

      if (!isTextInput && event.key === "/") {
        event.preventDefault();
        setActivePanel(null);
        setCommandMenuOpen(true);
      }

      if (event.key === "Escape") {
        setActivePanel(null);
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
          onClick={() => {
            setActivePanel(null);
            setCommandMenuOpen(true);
          }}
        >
          <Search size={17} />
        </button>
        <button
          className={`ops-icon-button${activePanel === "notifications" ? " ops-icon-button-active" : ""}`}
          type="button"
          aria-expanded={activePanel === "notifications"}
          aria-label="Open notifications"
          title="Open notifications"
          onClick={() =>
            setActivePanel((current) => (current === "notifications" ? null : "notifications"))
          }
        >
          <Bell size={17} />
          {notificationCount > 0 ? (
            <span className="notification-badge">{notificationCount}</span>
          ) : null}
        </button>
        <button
          className={`ops-icon-button${activePanel === "help" ? " ops-icon-button-active" : ""}`}
          type="button"
          aria-expanded={activePanel === "help"}
          aria-label="Open platform help"
          title="Open platform help"
          onClick={() => setActivePanel((current) => (current === "help" ? null : "help"))}
        >
          <CircleHelp size={17} />
        </button>
        <span className="topbar-divider" aria-hidden="true" />
        <button
          className={`ops-user-chip${activePanel === "account" ? " ops-user-chip-active" : ""}`}
          type="button"
          aria-expanded={activePanel === "account"}
          aria-label="Open operator account"
          title="Open operator account"
          onClick={() => setActivePanel((current) => (current === "account" ? null : "account"))}
        >
          {operatorInitials(session?.actorId)}
        </button>
        {activePanel === "notifications" ? <NotificationPanel overview={overview} /> : null}
        {activePanel === "help" ? <HelpPanel /> : null}
        {activePanel === "account" ? <AccountPanel /> : null}
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
