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
import { axisFetchJson } from "@/lib/axis-api";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import type {
  IdentitySessionReadModel,
  ManufacturingNotificationAcknowledgementResult,
  ManufacturingNotificationCenter,
  ManufacturingPlatformNotification,
} from "@/lib/platform-overview";
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

function notificationTone(severity: string): string {
  if (severity === "ready") {
    return "signal-ready";
  }

  return severity === "watch" ? "signal-watch" : "signal-action-required";
}

function identitySessionLabel(identitySession: IdentitySessionReadModel | null): string {
  if (!identitySession) {
    return "API required";
  }

  return identitySession.authenticated ? "API verified" : "Public";
}

function identitySessionTone(identitySession: IdentitySessionReadModel | null): string {
  if (!identitySession) {
    return "signal-action-required";
  }

  if (identitySession.authenticated) {
    return "signal-ready";
  }

  return identitySession.api_auth_required ? "signal-action-required" : "signal-watch";
}

function NotificationPanel({
  center,
  onAcknowledged,
  session,
}: {
  center: ManufacturingNotificationCenter | null;
  onAcknowledged: () => void;
  session: ReturnType<typeof useOidcConsoleSession>["session"];
}) {
  const [pendingNotificationId, setPendingNotificationId] = useState<string | null>(null);
  const [acknowledgementError, setAcknowledgementError] = useState<string | null>(null);

  if (!center) {
    return (
      <section className="topbar-popover" aria-label="Notifications">
        <div className="topbar-popover-header">
          <p className="section-label">Notifications</p>
          <span className="status-pill signal-action-required">API required</span>
        </div>
        <p className="row-detail">
          Live notification data requires `/demo/manufacturing/notifications`.
        </p>
      </section>
    );
  }

  const items = center.notifications.slice(0, 5);
  const canAcknowledge = Boolean(
    session?.actorId && session.scopes.includes("notifications:acknowledge"),
  );
  const sessionRequiredLabel = session
    ? "Your OIDC session needs notifications:acknowledge."
    : "Connect an OIDC session to acknowledge notifications.";

  async function acknowledgeNotification(item: ManufacturingPlatformNotification) {
    if (!session?.actorId || !canAcknowledge || item.read_state === "acknowledged") {
      return;
    }

    setPendingNotificationId(item.notification_id);
    setAcknowledgementError(null);
    try {
      await axisFetchJson<ManufacturingNotificationAcknowledgementResult>(
        `/demo/manufacturing/notifications/${item.notification_id}/acknowledgement`,
        {
          method: "POST",
          session,
          body: {
            tenant_id: session.tenantId,
            actor_id: session.actorId,
            actor_scopes: session.scopes,
            state: "acknowledged",
            reason: "Acknowledged from the Axis console notification center.",
          },
        },
      );
      onAcknowledged();
    } catch {
      setAcknowledgementError("Axis could not persist the acknowledgement.");
    } finally {
      setPendingNotificationId(null);
    }
  }

  return (
    <section className="topbar-popover" aria-label="Notifications">
      <div className="topbar-popover-header">
        <p className="section-label">Notifications</p>
        <span className="status-pill signal-ready">{center.unread_count} live</span>
      </div>
      <div className="topbar-popover-list">
        {items.length > 0 ? (
          items.map((item) => {
            const acknowledged = item.read_state === "acknowledged";
            const pending = pendingNotificationId === item.notification_id;
            return (
              <div
                aria-label={`${item.action_label}: ${item.title}`}
                className={`topbar-popover-row notification-row${
                  acknowledged ? " notification-row-acknowledged" : ""
                }`}
                key={item.notification_id}
              >
                <span
                  aria-hidden="true"
                  className={`status-dot ${notificationTone(item.severity)}`}
                />
                <span className="notification-row-copy">
                  <strong>{item.title}</strong>
                  <small>
                    {acknowledged
                      ? item.acknowledgement_reason ?? "Acknowledged"
                      : item.detail}
                  </small>
                </span>
                <span className="notification-row-actions">
                  <a className="notification-open-link" href={item.route} title={item.action_label}>
                    Open
                  </a>
                  <button
                    className="notification-ack-button"
                    disabled={!canAcknowledge || acknowledged || pending}
                    onClick={() => void acknowledgeNotification(item)}
                    type="button"
                  >
                    {acknowledged ? "Acked" : pending ? "Saving" : "Ack"}
                  </button>
                </span>
              </div>
            );
          })
        ) : (
          <div className="topbar-popover-row">
            <span aria-hidden="true" className="status-dot signal-ready" />
            <span>
              <strong>No active notifications</strong>
              <small>Axis did not derive pending alerts from persisted platform state.</small>
            </span>
          </div>
        )}
      </div>
      {items.length > 0 && !canAcknowledge ? (
        <p className="notification-panel-note">{sessionRequiredLabel}</p>
      ) : null}
      {acknowledgementError ? (
        <p className="notification-panel-error" role="status">
          {acknowledgementError}
        </p>
      ) : null}
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
  const { data: identitySession, isUnavailable: identitySessionUnavailable } =
    useAxisQuery<IdentitySessionReadModel>("/identity/session");
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
        <span className={`status-pill ${identitySessionTone(identitySession)}`}>
          {identitySessionLabel(identitySession)}
        </span>
      </div>

      <div className="account-summary">
        <div className="account-avatar">
          {operatorInitials(identitySession?.actor_id ?? undefined)}
        </div>
        <div>
          <p className="row-title">
            {identitySession?.authenticated && identitySession.actor_id
              ? compactActorLabel(identitySession.actor_id)
              : identitySessionUnavailable
                ? "Session API unavailable"
                : "Public evaluation operator"}
          </p>
          <p className="row-detail">
            {identitySession?.authenticated && identitySession.tenant_id
              ? identitySession.tenant_id
              : identitySession?.session_boundary ?? "Identity session requires `/identity/session`."}
          </p>
        </div>
      </div>

      <div className="account-grid">
        <span>
          <small>API</small>
          <strong>{apiBaseUrl}</strong>
        </span>
        <span>
          <small>API status</small>
          <strong>{apiStatus.label}</strong>
        </span>
        <span>
          <small>SSO posture</small>
          <strong>
            {identitySession
              ? identitySession.enterprise_sso_ready
                ? "Enterprise ready"
                : "Needs hardening"
              : "Unknown"}
          </strong>
        </span>
        <span>
          <small>Session expires</small>
          <strong>{formatExpiry(identitySession?.expires_at ?? undefined)}</strong>
        </span>
      </div>

      {identitySession ? (
        <div className="topbar-popover-list account-readiness-list">
          {identitySession.capabilities.slice(0, 2).map((capability) => (
            <div className="topbar-popover-row" key={capability}>
              <span aria-hidden="true" className="status-dot signal-ready" />
              <span>
                <strong>Capability</strong>
                <small>{capability}</small>
              </span>
            </div>
          ))}
          {identitySession.limitations.slice(0, 2).map((limitation) => (
            <div className="topbar-popover-row" key={limitation}>
              <span aria-hidden="true" className="status-dot signal-watch" />
              <span>
                <strong>Limitation</strong>
                <small>{limitation}</small>
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="row-detail">
          The account panel needs `/identity/session` before it can display an API-verified
          actor.
        </p>
      )}

      {session ? (
        <>
          <div className="tag-list account-scope-list">
            {(identitySession?.scopes ?? []).length > 0 ? (
              (identitySession?.scopes ?? []).slice(0, 6).map((scope) => (
                <span className="tag" key={scope}>
                  {scope}
                </span>
              ))
            ) : (
              <span className="tag">
                {identitySession?.authenticated ? "No scopes in token" : "Awaiting API validation"}
              </span>
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
  const { data: notificationCenter } =
    useAxisQuery<ManufacturingNotificationCenter>("/demo/manufacturing/notifications");
  const { session } = useOidcConsoleSession();

  const notificationCount = useMemo(() => {
    if (!notificationCenter) {
      return 0;
    }

    return Math.min(9, notificationCenter.unread_count);
  }, [notificationCenter]);

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
        {activePanel === "notifications" ? (
          <NotificationPanel
            center={notificationCenter}
            onAcknowledged={triggerRefresh}
            session={session}
          />
        ) : null}
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
