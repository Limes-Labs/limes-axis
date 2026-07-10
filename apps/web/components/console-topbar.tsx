"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Bell,
  CircleHelp,
  KeyRound,
  LogOut,
  MonitorSmartphone,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";

import { ConsoleCommandMenu } from "@/components/console-command-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { Input } from "@/components/ui/input";
import { axisFetchJson } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
import { buildOidcAuthorizeUrl, buildOidcLogoutUrl } from "@/lib/oidc-session";
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

/* Shared popover chrome. The `.topbar-popover-header` / `.notification-row`
 * class names stay as e2e markers; all styling is Tailwind on tokens. */
const popoverClass =
  "absolute top-[calc(100%+10px)] right-0 z-70 grid max-h-[calc(100vh-94px)] w-[min(360px,calc(100vw-32px))] gap-3 overflow-y-auto overscroll-contain rounded-2xl border border-line bg-surface p-3 shadow-[0_26px_80px_rgb(4_18_46/0.28)] dark:border-white/10";
const popoverRowClass =
  "grid min-w-0 grid-cols-[18px_minmax(0,1fr)] items-start gap-2.5 rounded-xl border border-line/60 bg-ink/3 p-2.5 text-ink/80 dark:border-white/10 dark:bg-white/4 " +
  "[&_strong]:block [&_strong]:min-w-0 [&_strong]:text-xs [&_strong]:leading-tight [&_strong]:break-words [&_strong]:text-ink " +
  "[&_small]:mt-0.5 [&_small]:block [&_small]:text-[11px] [&_small]:leading-snug [&_small]:text-muted [&>svg]:text-positive";
const popoverRowLinkClass =
  "transition-colors hover:border-signal/30 hover:bg-signal/10";
const popoverLinkClass =
  "inline-flex min-h-[34px] items-center justify-center rounded-xl border border-line text-xs font-semibold text-signal transition-colors hover:border-signal/40 hover:bg-signal/10 dark:border-white/15";
const commandClass =
  "inline-flex min-h-9 w-full min-w-0 items-center justify-center gap-2 rounded-full bg-navy px-4 text-sm font-medium text-white transition-colors select-none hover:bg-signal dark:bg-signal dark:hover:bg-white dark:hover:text-navy";
const commandSecondaryClass =
  "inline-flex min-h-9 w-full min-w-0 items-center justify-center gap-2 rounded-full border border-line bg-transparent px-4 text-sm font-medium text-ink transition-colors select-none hover:border-signal/50 hover:text-signal dark:border-white/20";
const tagClass =
  "inline-flex max-w-full min-w-0 items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs break-words text-muted dark:border-white/15 dark:bg-white/5";

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

function PopoverHeader({ label, children }: { label: string; children?: React.ReactNode }) {
  return (
    <div className="topbar-popover-header flex items-center justify-between gap-3">
      <p className="eyebrow m-0">{label}</p>
      {children}
    </div>
  );
}

function NotificationPanel({
  center,
  identitySession,
  onAcknowledged,
  session,
}: {
  center: ManufacturingNotificationCenter | null;
  identitySession: IdentitySessionReadModel | null;
  onAcknowledged: () => void;
  session: ReturnType<typeof useOidcConsoleSession>["session"];
}) {
  const [pendingNotificationId, setPendingNotificationId] = useState<string | null>(null);
  const [acknowledgementError, setAcknowledgementError] = useState<string | null>(null);

  if (!center) {
    return (
      <section className={popoverClass} aria-label="Notifications">
        <PopoverHeader label="Notifications">
          <span className="status-pill signal-action-required">API required</span>
        </PopoverHeader>
        <p className="m-0 text-sm leading-snug text-muted">
          Live notification data requires `/demo/manufacturing/notifications`.
        </p>
      </section>
    );
  }

  const items = center.notifications.slice(0, 5);
  const canAcknowledge = Boolean(
    identitySession?.authenticated
      && identitySession.actor_id
      && identitySession.tenant_id
      && identitySession.scopes.includes("notifications:acknowledge"),
  );
  const sessionRequiredLabel = identitySession?.authenticated
    ? "Your OIDC session needs notifications:acknowledge."
    : "Sign in with SSO to acknowledge notifications.";

  async function acknowledgeNotification(item: ManufacturingPlatformNotification) {
    if (
      !identitySession?.actor_id
      || !identitySession.tenant_id
      || !canAcknowledge
      || item.read_state === "acknowledged"
    ) {
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
            tenant_id: identitySession.tenant_id,
            actor_id: identitySession.actor_id,
            actor_scopes: identitySession.scopes,
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
    <section className={popoverClass} aria-label="Notifications">
      <PopoverHeader label="Notifications">
        <span className="status-pill signal-ready">{center.unread_count} live</span>
      </PopoverHeader>
      <div className="grid gap-2">
        {items.length > 0 ? (
          items.map((item) => {
            const acknowledged = item.read_state === "acknowledged";
            const pending = pendingNotificationId === item.notification_id;
            return (
              <div
                aria-label={`${item.action_label}: ${item.title}`}
                className={cn(
                  "notification-row",
                  popoverRowClass,
                  acknowledged && "opacity-70",
                )}
                key={item.notification_id}
              >
                <span
                  aria-hidden="true"
                  className={`status-dot ${notificationTone(item.severity)}`}
                />
                <span className="min-w-0 [&_small]:line-clamp-2 [&_strong]:truncate">
                  <strong>{item.title}</strong>
                  <small>
                    {acknowledged
                      ? item.acknowledgement_reason ?? "Acknowledged"
                      : item.detail}
                  </small>
                </span>
                <span className="col-start-2 mt-2 inline-flex items-center gap-1.5">
                  <Link
                    className="grid h-7 w-[54px] place-items-center rounded-lg border border-line text-[11px] leading-none font-bold whitespace-nowrap text-signal dark:border-white/15"
                    href={item.route}
                    title={item.action_label}
                  >
                    Open
                  </Link>
                  <button
                    className="grid h-7 w-[52px] cursor-pointer place-items-center rounded-lg border border-positive/35 bg-positive/8 text-[11px] leading-none font-bold whitespace-nowrap text-positive disabled:cursor-not-allowed disabled:border-line/60 disabled:bg-ink/3 disabled:text-muted dark:disabled:bg-white/5"
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
          <div className={popoverRowClass}>
            <span aria-hidden="true" className="status-dot signal-ready" />
            <span>
              <strong>No active notifications</strong>
              <small>Axis did not derive pending alerts from persisted platform state.</small>
            </span>
          </div>
        )}
      </div>
      {items.length > 0 && !canAcknowledge ? (
        <p className="m-0 text-[11px] leading-snug text-muted">{sessionRequiredLabel}</p>
      ) : null}
      {acknowledgementError ? (
        <p className="m-0 text-[11px] leading-snug text-warning" role="status">
          {acknowledgementError}
        </p>
      ) : null}
      <Link className={popoverLinkClass} href="/audit">
        Open audit evidence
      </Link>
    </section>
  );
}

function HelpPanel() {
  return (
    <section className={popoverClass} aria-label="Platform help">
      <PopoverHeader label="Platform help">
        <span className="status-pill signal-ready">Docs</span>
      </PopoverHeader>
      <div className="grid gap-2">
        <Link className={cn(popoverRowClass, popoverRowLinkClass)} href="/model-routing">
          <ShieldCheck size={16} />
          <span>
            <strong>Model routing</strong>
            <small>Inspect provider boundaries and egress decisions.</small>
          </span>
        </Link>
        <a
          className={cn(popoverRowClass, popoverRowLinkClass)}
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

function currentReturnPath(): string {
  if (typeof window === "undefined") {
    return "/";
  }

  return `${window.location.pathname}${window.location.search}`;
}

function AccountPanel({
  identitySession,
  identitySessionUnavailable,
}: {
  identitySession: IdentitySessionReadModel | null;
  identitySessionUnavailable: boolean;
}) {
  const { session, saveAccessToken, clearSession } = useOidcConsoleSession();
  const { apiBaseUrl, apiStatus } = useConsole();
  const [accessToken, setAccessToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [developerBridgeOpen, setDeveloperBridgeOpen] = useState(false);
  const verifiedCookieSession =
    identitySession?.authenticated && identitySession.mode === "secure_oidc_cookie";
  const authenticatedSession = identitySession?.authenticated || Boolean(session);
  const visibleScopes =
    identitySession?.scopes.length ? identitySession.scopes : session?.scopes ?? [];
  const authorizeUrl = buildOidcAuthorizeUrl(apiBaseUrl, currentReturnPath());
  const onboardingUrl = `${apiBaseUrl}/identity/oidc/onboarding`;

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

  function signOutWithIdentityProvider() {
    clearSession();
    window.location.assign(buildOidcLogoutUrl(apiBaseUrl, currentReturnPath()));
  }

  return (
    <section
      className={cn(popoverClass, "w-[min(390px,calc(100vw-32px))]")}
      aria-label="Operator account"
    >
      <PopoverHeader label="Operator">
        <span className={`status-pill ${identitySessionTone(identitySession)}`}>
          {identitySessionLabel(identitySession)}
        </span>
      </PopoverHeader>

      <div className="grid grid-cols-[42px_minmax(0,1fr)] items-center gap-3">
        <div className="grid size-[42px] place-items-center rounded-full border border-line bg-signal/15 text-xs font-extrabold text-ink dark:border-white/15">
          {operatorInitials(identitySession?.actor_id ?? undefined)}
        </div>
        <div>
          <p className="m-0 font-medium break-words text-ink">
            {identitySession?.authenticated && identitySession.actor_id
              ? compactActorLabel(identitySession.actor_id)
              : identitySessionUnavailable
                ? "Session API unavailable"
                : "Public evaluation operator"}
          </p>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug break-words text-muted">
            {identitySession?.authenticated && identitySession.tenant_id
              ? identitySession.tenant_id
              : identitySession?.session_boundary ?? "Identity session requires `/identity/session`."}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 [&>span]:min-w-0 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:block [&_small]:text-[11px] [&_small]:text-muted [&_strong]:mt-0.5 [&_strong]:block [&_strong]:min-w-0 [&_strong]:text-xs [&_strong]:leading-tight [&_strong]:break-words [&_strong]:text-ink">
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
        <div className="grid max-h-[188px] gap-2 overflow-y-auto overscroll-contain">
          {identitySession.capabilities.slice(0, 2).map((capability) => (
            <div className={popoverRowClass} key={capability}>
              <span aria-hidden="true" className="status-dot signal-ready" />
              <span>
                <strong>Capability</strong>
                <small>{capability}</small>
              </span>
            </div>
          ))}
          {identitySession.limitations.slice(0, 2).map((limitation) => (
            <div className={popoverRowClass} key={limitation}>
              <span aria-hidden="true" className="status-dot signal-watch" />
              <span>
                <strong>Limitation</strong>
                <small>{limitation}</small>
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="m-0 text-sm leading-snug text-muted">
          The account panel needs `/identity/session` before it can display an API-verified
          actor.
        </p>
      )}

      {verifiedCookieSession || session ? (
        <>
          <div className="flex max-h-[86px] min-w-0 flex-wrap gap-2 overflow-y-auto overscroll-contain">
            {visibleScopes.length > 0 ? (
              visibleScopes.slice(0, 6).map((scope) => (
                <span className={tagClass} key={scope}>
                  {scope}
                </span>
              ))
            ) : (
              <span className={tagClass}>
                {identitySession?.authenticated ? "No scopes in token" : "Awaiting API validation"}
              </span>
            )}
          </div>
          <Link className={commandSecondaryClass} href="/settings/sessions">
            <MonitorSmartphone size={16} />
            Manage sessions
          </Link>
          {verifiedCookieSession ? (
            <button
              className={commandClass}
              onClick={signOutWithIdentityProvider}
              type="button"
            >
              <LogOut size={16} />
              Sign out with identity provider
            </button>
          ) : (
            <button className={commandClass} onClick={clearSession} type="button">
              <LogOut size={16} />
              Clear bearer bridge
            </button>
          )}
        </>
      ) : (
        <div className="grid gap-2">
          <a className={commandClass} href={authorizeUrl}>
            <ShieldCheck size={16} />
            Sign in with SSO
          </a>
          <a
            className={commandSecondaryClass}
            href={onboardingUrl}
            rel="noreferrer"
            target="_blank"
          >
            <CircleHelp size={16} />
            Open SSO setup
          </a>
          <button
            className={commandSecondaryClass}
            onClick={() => setDeveloperBridgeOpen((value) => !value)}
            type="button"
          >
            <KeyRound size={16} />
            Connect bearer token
          </button>
        </div>
      )}

      {!authenticatedSession && developerBridgeOpen ? (
        <form className="grid gap-2" onSubmit={connectSession}>
          <label className="grid gap-1.5 text-xs font-semibold text-muted">
            Developer bearer bridge
            <Input
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
            <span className="text-xs font-semibold text-danger" role="status">
              {error}
            </span>
          ) : null}
          <button className={commandClass} type="submit">
            <KeyRound size={16} />
            Attach bearer bridge
          </button>
        </form>
      ) : null}
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
  const { data: identitySession, isUnavailable: identitySessionUnavailable } =
    useAxisQuery<IdentitySessionReadModel>("/identity/session");

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
    <header
      className="ops-topbar sticky top-0 isolate z-10 flex min-h-[62px] flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-surface/80 py-2 backdrop-blur-xl max-sm:grid max-sm:min-h-0 max-sm:grid-cols-[minmax(0,1fr)_auto] max-sm:gap-2 max-sm:py-1.5 dark:border-white/10"
      aria-label="Console status bar"
    >
      <div className="hidden min-w-0 flex-1 sm:block">
        <span className="flex items-center gap-2.5 text-xs font-semibold text-ink/80 [&>svg]:text-positive">
          <ShieldCheck size={17} />
          Sovereign Control
        </span>
      </div>
      <div className="flex min-w-0 flex-wrap items-center gap-2 max-sm:flex-nowrap max-sm:overflow-x-auto max-sm:pb-px max-sm:[&_.status-pill]:px-2 max-sm:[&_.status-pill]:text-[11px] max-sm:[&_.status-pill]:whitespace-nowrap sm:ml-auto sm:justify-end">
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
      <div
        className="ops-toolbar-icons flex min-w-0 flex-wrap items-center justify-end gap-2 max-sm:flex-nowrap max-sm:gap-1"
        aria-label="Utility actions"
      >
        <button
          className="icon-button"
          type="button"
          aria-label="Refresh state"
          title="Refresh state"
          onClick={triggerRefresh}
        >
          <RefreshCw size={17} />
        </button>
        <ThemeToggle />
        <button
          className="icon-button"
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
          className={`icon-button${activePanel === "notifications" ? " icon-button-active" : ""}`}
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
            <span className="absolute top-1 right-1 grid h-[14px] min-w-[14px] place-items-center rounded-full border border-surface bg-positive px-0.5 font-mono text-[9px] leading-none font-extrabold text-white">
              {notificationCount}
            </span>
          ) : null}
        </button>
        <button
          className={`icon-button${activePanel === "help" ? " icon-button-active" : ""}`}
          type="button"
          aria-expanded={activePanel === "help"}
          aria-label="Open platform help"
          title="Open platform help"
          onClick={() => setActivePanel((current) => (current === "help" ? null : "help"))}
        >
          <CircleHelp size={17} />
        </button>
        <span className="mx-0.5 h-[22px] w-px shrink-0 bg-line dark:bg-white/15" aria-hidden="true" />
        <button
          className={cn(
            "grid size-[34px] shrink-0 cursor-pointer place-items-center rounded-full border border-line bg-surface text-xs font-bold text-ink/80 transition-colors hover:border-signal/40 hover:bg-signal/10 active:translate-y-px dark:border-white/20 dark:bg-white/5",
            activePanel === "account" && "border-signal/40 bg-signal/10",
          )}
          type="button"
          aria-expanded={activePanel === "account"}
          aria-label="Open operator account"
          title="Open operator account"
          onClick={() => setActivePanel((current) => (current === "account" ? null : "account"))}
        >
          {operatorInitials(identitySession?.actor_id ?? session?.actorId)}
        </button>
        {activePanel === "notifications" ? (
          <NotificationPanel
            center={notificationCenter}
            identitySession={identitySession}
            onAcknowledged={triggerRefresh}
            session={session}
          />
        ) : null}
        {activePanel === "help" ? <HelpPanel /> : null}
        {activePanel === "account" ? (
          <AccountPanel
            identitySession={identitySession}
            identitySessionUnavailable={identitySessionUnavailable}
          />
        ) : null}
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
