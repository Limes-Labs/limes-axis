"use client";

import { LogOut, MonitorSmartphone, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { ApiRequiredState } from "@/components/api-required-state";
import { ConsolePage } from "@/components/console-page";
import { AxisApiError } from "@/lib/axis-api";
import {
  canListTenantSessions,
  formatSessionInstant,
  identitySessionsPath,
  isRevocableSessionStatus,
  revokeIdentitySession,
  sessionStatusClass,
  sessionStatusLabel,
  type IdentityBrowserSessionList,
  type IdentityBrowserSessionRecord,
} from "@/lib/identity-sessions";
import { buildOidcAuthorizeUrl, buildOidcLogoutUrl } from "@/lib/oidc-session";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

const SESSIONS_ROUTE = "/settings/sessions";
const SESSION_ENDPOINTS = "/identity/session /identity/sessions";

function revokeErrorMessage(caught: unknown): string {
  if (caught instanceof AxisApiError) {
    if (caught.status === 403) {
      return "Axis denied the revocation. Managing other actors' sessions requires identity:sessions:admin.";
    }
    if (caught.status === 404) {
      return "Axis could not find that session in this tenant. Refresh the list.";
    }
  }
  return "Axis could not revoke the session.";
}

function SessionRow({
  record,
  showActor,
  pending,
  logoutUrl,
  onRevoke,
}: {
  record: IdentityBrowserSessionRecord;
  showActor: boolean;
  pending: boolean;
  logoutUrl: string;
  onRevoke: (record: IdentityBrowserSessionRecord) => void;
}) {
  const revocable = isRevocableSessionStatus(record.status);

  return (
    <div className="row" aria-label={`Browser session ${record.session_ref}`}>
      <div>
        <p className="row-title">
          {showActor ? record.actor_id : `Session ${record.session_ref.slice(0, 8)}`}
          {record.current ? " (this browser)" : ""}
        </p>
        <p className="row-detail">
          Created {formatSessionInstant(record.created_at)} · Last seen{" "}
          {formatSessionInstant(record.last_seen_at)} · Expires{" "}
          {formatSessionInstant(record.expires_at)} · Refreshes {record.refresh_count}
        </p>
        {record.revoked_at ? (
          <p className="row-detail">
            Revoked {formatSessionInstant(record.revoked_at)}
            {record.revocation_reason ? ` (${record.revocation_reason.replaceAll("_", " ")})` : ""}
          </p>
        ) : null}
      </div>
      <div className="ops-controls">
        <span className={`status-pill ${sessionStatusClass(record.status)}`}>
          {record.current ? "Current" : sessionStatusLabel(record.status)}
        </span>
        {revocable ? (
          record.current ? (
            <a
              className="command-button"
              href={logoutUrl}
              title="Revoking this browser's session signs you out through the identity provider"
            >
              <LogOut size={15} />
              Sign out
            </a>
          ) : (
            <button
              className="command-button"
              disabled={pending}
              onClick={() => onRevoke(record)}
              type="button"
            >
              {pending ? "Revoking" : "Revoke"}
            </button>
          )
        ) : null}
      </div>
    </div>
  );
}

function SignedOutPanel({ signInUrl }: { signInUrl: string }) {
  return (
    <section className="panel overview-context">
      <div>
        <p className="section-label">Signed out</p>
        <h2 className="panel-title">No authenticated operator session</h2>
        <p className="row-detail">
          Session management lists only API-verified sessions. Sign in with the API-owned OIDC
          browser session, or attach a bearer token from the account panel, before managing
          sessions.
        </p>
      </div>
      <a className="command-button" href={signInUrl}>
        <ShieldCheck size={16} />
        Sign in with SSO
      </a>
    </section>
  );
}

function SessionListPanel({
  identitySession,
  logoutUrl,
}: {
  identitySession: IdentitySessionReadModel;
  logoutUrl: string;
}) {
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const adminCapable = canListTenantSessions(identitySession.scopes);
  const [tenantWide, setTenantWide] = useState(false);
  const listTenantWide = adminCapable && tenantWide;
  const sessions = useAxisQuery<IdentityBrowserSessionList>(
    identitySessionsPath(listTenantWide),
  );
  const [pendingSessionRef, setPendingSessionRef] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  async function revokeSession(record: IdentityBrowserSessionRecord) {
    setPendingSessionRef(record.session_ref);
    setRevokeError(null);
    try {
      await revokeIdentitySession(record.session_ref, { session });
      triggerRefresh();
    } catch (caught) {
      setRevokeError(revokeErrorMessage(caught));
    } finally {
      setPendingSessionRef(null);
    }
  }

  if (sessions.isUnavailable) {
    return (
      <ApiRequiredState
        detail="Live session data requires the Axis identity session APIs. Local fallback session records are disabled."
        endpoint={identitySessionsPath(listTenantWide)}
        title="Sessions API unavailable"
      />
    );
  }

  const list = sessions.data;

  return (
    <section className="panel">
      <div className="section-heading-row">
        <div>
          <p className="section-label">Browser sessions</p>
          <h2 className="panel-title">
            {listTenantWide ? "Tenant-wide sessions" : "Your sessions"}
          </h2>
        </div>
        <div className="ops-controls">
          {adminCapable ? (
            <button
              className="command-button"
              onClick={() => setTenantWide((value) => !value)}
              type="button"
            >
              {listTenantWide ? "Show my sessions" : "Show tenant sessions"}
            </button>
          ) : null}
          <span className={`status-pill ${list ? "signal-ready" : "signal-watch"}`}>
            {list ? `${list.sessions.length} recorded` : "Loading sessions"}
          </span>
        </div>
      </div>

      {list ? (
        <div className="stack">
          {list.sessions.length > 0 ? (
            list.sessions.map((record) => (
              <SessionRow
                key={record.session_ref}
                logoutUrl={logoutUrl}
                onRevoke={(target) => void revokeSession(target)}
                pending={pendingSessionRef === record.session_ref}
                record={record}
                showActor={listTenantWide}
              />
            ))
          ) : (
            <div className="row">
              <div>
                <p className="row-title">No browser sessions recorded</p>
                <p className="row-detail">
                  Axis has no persisted OIDC browser sessions for this actor. Bearer-token
                  bridges do not create cookie sessions; sign in with SSO to start one.
                </p>
              </div>
              <span className="status-pill signal-ready">Empty</span>
            </div>
          )}
        </div>
      ) : (
        <p className="row-detail">Loading persisted session records from the Axis API.</p>
      )}

      {revokeError ? (
        <p className="row-detail signal-action-required" role="status">
          {revokeError}
        </p>
      ) : null}

      {list?.notes.length ? (
        <div className="tag-list">
          {list.notes.map((note) => (
            <span className="tag" key={note}>
              {note}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function SessionSecurityConsole() {
  const { apiBaseUrl } = useConsole();
  const identity = useAxisQuery<IdentitySessionReadModel>("/identity/session");
  const identitySession = identity.data;
  const signInUrl = buildOidcAuthorizeUrl(apiBaseUrl, SESSIONS_ROUTE);
  const logoutUrl = buildOidcLogoutUrl(apiBaseUrl, SESSIONS_ROUTE);
  const sourceLabel = identitySession
    ? "Live sessions"
    : identity.isLoading
      ? "Loading sessions"
      : "API required";

  return (
    <ConsolePage
      controls={
        identitySession?.authenticated && identitySession.mode === "secure_oidc_cookie" ? (
          <a className="command-button" href={logoutUrl}>
            <LogOut size={16} />
            Sign out
          </a>
        ) : undefined
      }
      eyebrow="Platform control"
      sourceLabel={sourceLabel}
      subtitle="API-owned OIDC browser sessions with rotation, revocation and logout evidence."
      title="Session security"
    >
      {identity.isUnavailable || !identitySession ? (
        <ApiRequiredState
          detail="Live session management requires the Axis identity APIs. Local fallback session records are disabled."
          endpoint={SESSION_ENDPOINTS}
          title="Session API unavailable"
        />
      ) : !identitySession.authenticated ? (
        <SignedOutPanel signInUrl={signInUrl} />
      ) : (
        <>
          <section className="panel">
            <div className="section-heading-row">
              <div>
                <p className="section-label">Operator session</p>
                <h2 className="panel-title">API-verified identity</h2>
              </div>
              <span className="status-pill signal-ready">
                <MonitorSmartphone size={15} />
                {identitySession.mode === "secure_oidc_cookie" ? "Cookie session" : "Bearer session"}
              </span>
            </div>
            <div className="settings-summary-grid">
              <span>
                <small>Actor</small>
                <strong>{identitySession.actor_id ?? "Unknown"}</strong>
              </span>
              <span>
                <small>Tenant</small>
                <strong>{identitySession.tenant_id ?? "Unknown"}</strong>
              </span>
              <span>
                <small>Session boundary</small>
                <strong>{identitySession.session_boundary.replaceAll("_", " ")}</strong>
              </span>
              <span>
                <small>Scopes</small>
                <strong>{identitySession.scopes.length}</strong>
              </span>
            </div>
            {identitySession.mode !== "secure_oidc_cookie" ? (
              <p className="row-detail">
                This console is attached through the developer bearer bridge. Revocation below
                applies to persisted browser cookie sessions; clear the bearer bridge from the
                account panel to detach this console.
              </p>
            ) : null}
          </section>
          <SessionListPanel identitySession={identitySession} logoutUrl={logoutUrl} />
        </>
      )}
    </ConsolePage>
  );
}
