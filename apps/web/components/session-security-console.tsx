"use client";

import { LogOut, MonitorSmartphone, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ErrorPanel } from "@/components/ui/states";
import { SsoSignInLink } from "@/components/sso-sign-in-link";
import { ConsolePage } from "@/components/console-page";
import {
  toAxisOperatorError,
  type AxisOperatorError,
} from "@/lib/axis-api";
import { formatNumber } from "@/lib/format";
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
import { parseIdentityBrowserSessionList } from "@/lib/runtime-contracts/identity";
import type { ConsoleStrings } from "@/lib/i18n";
import { useStrings } from "@/providers/locale-provider";
import {
  deriveSourceState,
  PROVENANCE_NOT_APPLICABLE,
  type SourceState,
} from "@/lib/source-state";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useIdentitySession } from "@/lib/use-identity-session";
import { useConsole } from "@/providers/console-provider";

const SESSIONS_ROUTE = "/settings/sessions";
const SESSION_ENDPOINTS = "/identity/session /identity/sessions";

function revokeOperatorError(caught: unknown, strings: ConsoleStrings): AxisOperatorError {
  const failure = toAxisOperatorError(caught, "Axis could not revoke the session.");
  if (failure.status === 403) {
    return {
      ...failure,
      message: strings.settings.revokeDenied,
    };
  }
  if (failure.status === 404) {
    return {
      ...failure,
      message: "Axis could not find that session in this tenant. Refresh the list.",
    };
  }
  return failure;
}

/**
 * `ConsolePage.sourceLabel` is a plain string (it pre-dates `SourcePill` and
 * other callers we don't own still pass literal text), so the source pill it
 * renders can't carry real tone here — text is the only channel available.
 * This mirrors `SourcePill`'s own wording so the copy stays consistent with
 * consoles that render the full component.
 */
function sourceStateLabel(state: SourceState, subject: string, copy: ConsoleStrings): string {
  const labels = copy.sources.pageLabels;
  if (state === "live") {
    return labels.live(subject);
  }
  if (state === "stale") {
    return labels.stale(subject);
  }
  if (state === "unavailable") {
    return labels.unavailable(subject);
  }
  return labels.loading(subject);
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
  const strings = useStrings();
  const revocable = isRevocableSessionStatus(record.status);
  const sessionName = showActor
    ? record.actor_id
    : strings.ui.sessionSecurityConsole.sessionShort(record.session_ref.slice(0, 8));

  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10" aria-label={strings.ui.sessionSecurityConsole.browserSession(record.session_ref)}>
      <div>
        <p className="m-0 font-medium text-ink break-words">
          {record.current ? strings.ui.sessionSecurityConsole.thisBrowser(sessionName) : sessionName}
        </p>
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
          {strings.ui.sessionSecurityConsole.sessionTimes(
            formatSessionInstant(record.created_at),
            formatSessionInstant(record.last_seen_at),
            formatSessionInstant(record.expires_at),
            formatNumber(record.refresh_count),
          )}
        </p>
        {record.revoked_at ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {strings.ui.sessionSecurityConsole.revokedAt(formatSessionInstant(record.revoked_at))}
            {record.revocation_reason ? ` (${record.revocation_reason.replaceAll("_", " ")})` : ""}
          </p>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className={`status-pill ${sessionStatusClass(record.status)}`}>
          {record.current ? strings.ui.sessionSecurityConsole.current : sessionStatusLabel(record.status, strings)}
        </span>
        {revocable ? (
          record.current ? (
            <a
              className={buttonVariants({ variant: "secondary" })}
              href={logoutUrl}
              title={strings.ui.sessionSecurityConsole.revokingThisBrowsersSessionSigns}
            >
              <LogOut size={15} />
              {strings.ui.sessionSecurityConsole.signOut}
            </a>
          ) : (
            <Button
              variant="secondary"
              disabled={pending}
              onClick={() => onRevoke(record)}
              type="button"
            >
              {pending ? strings.ui.sessionSecurityConsole.revoking : strings.ui.sessionSecurityConsole.revoke}
            </Button>
          )
        ) : null}
      </div>
    </div>
  );
}

function SignedOutPanel({ signInUrl }: { signInUrl: string }) {
  const strings = useStrings();
  return (
    <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="eyebrow m-0">{strings.ui.sessionSecurityConsole.signedOut}</p>
        <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.sessionSecurityConsole.noAuthenticatedOperatorSession}</h2>
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
          {strings.ui.sessionSecurityConsole.sessionManagementListsOnlyApi}
        </p>
      </div>
      <SsoSignInLink className={buttonVariants({ variant: "secondary" })} href={signInUrl}>
        <ShieldCheck size={16} />
        {strings.identityGate.signIn}
      </SsoSignInLink>
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
  const strings = useStrings();
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const adminCapable = canListTenantSessions(identitySession.scopes);
  const [tenantWide, setTenantWide] = useState(false);
  const listTenantWide = adminCapable && tenantWide;
  const sessions = useAxisQuery<IdentityBrowserSessionList>(
    identitySessionsPath(listTenantWide),
    { parse: parseIdentityBrowserSessionList },
  );
  // A Set of in-flight session refs, not a single id: revoking two sessions
  // back to back (a slow one, then a fast one) must not let the fast one's
  // completion clear the pending flag for the still in-flight slow one and
  // re-enable its button for a double submit.
  const [pendingSessionRefs, setPendingSessionRefs] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [revokeError, setRevokeError] = useState<AxisOperatorError | null>(null);

  async function revokeSession(record: IdentityBrowserSessionRecord) {
    setPendingSessionRefs((current) => new Set(current).add(record.session_ref));
    setRevokeError(null);
    try {
      await revokeIdentitySession(record.session_ref, { session });
      triggerRefresh();
    } catch (caught) {
      setRevokeError(revokeOperatorError(caught, strings));
    } finally {
      setPendingSessionRefs((current) => {
        const next = new Set(current);
        next.delete(record.session_ref);
        return next;
      });
    }
  }

  if (sessions.isUnavailable && !sessions.data) {
    return (
      <ErrorPanel
        detail={strings.ui.sessionSecurityConsole.liveSessionDataRequiresThe}
        endpoint={identitySessionsPath(listTenantWide)}
        reference={sessions.errorRequestId ?? undefined}
        title={strings.ui.sessionSecurityConsole.sessionsApiUnavailable}
      />
    );
  }

  const list = sessions.data;

  return (
    <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">{strings.ui.sessionSecurityConsole.browserSessions}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
            {listTenantWide ? strings.ui.sessionSecurityConsole.tenantWideSessions : strings.ui.sessionSecurityConsole.yourSessions}
          </h2>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {adminCapable ? (
            <Button
              variant="secondary"
              onClick={() => setTenantWide((value) => !value)}
              type="button"
            >
              {listTenantWide ? strings.ui.sessionSecurityConsole.showMySessions : strings.ui.sessionSecurityConsole.showTenantSessions}
            </Button>
          ) : null}
          <span className={`status-pill ${list ? "signal-ready" : "signal-watch"}`}>
            {list ? strings.ui.sessionSecurityConsole.recordedCount(list.sessions.length) : strings.ui.sessionSecurityConsole.loadingSessions}
          </span>
        </div>
      </div>

      {sessions.isUnavailable && list ? (
        <p className="m-0 text-sm text-warning" role="status">
          {strings.ui.sessionSecurityConsole.liveRefreshFailedShowingThe}
        </p>
      ) : null}

      {list ? (
        <div className="grid min-w-0 gap-2.5">
          {list.sessions.length > 0 ? (
            list.sessions.map((record) => (
              <SessionRow
                key={record.session_ref}
                logoutUrl={logoutUrl}
                onRevoke={(target) => void revokeSession(target)}
                pending={pendingSessionRefs.has(record.session_ref)}
                record={record}
                showActor={listTenantWide}
              />
            ))
          ) : (
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
              <div>
                <p className="m-0 font-medium text-ink break-words">{strings.ui.sessionSecurityConsole.noBrowserSessionsRecorded}</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {strings.ui.sessionSecurityConsole.axisHasNoPersistedOidc}
                </p>
              </div>
              <span className="status-pill signal-ready">{strings.ui.sessionSecurityConsole.empty}</span>
            </div>
          )}
        </div>
      ) : (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{strings.ui.sessionSecurityConsole.loadingPersistedSessionRecordsFrom}</p>
      )}

      {revokeError ? (
        <div role="alert">
          <ErrorPanel
            detail={revokeError.message}
            reference={revokeError.requestId ?? undefined}
            title={strings.ui.sessionSecurityConsole.sessionRevocationFailed}
          />
        </div>
      ) : null}

      {list?.notes.length ? (
        <div className="flex min-w-0 flex-wrap gap-2">
          {list.notes.map((note) => (
            <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={note}>
              {note}
            </span>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function SessionSecurityConsole() {
  const strings = useStrings();
  const { apiBaseUrl } = useConsole();
  const identity = useIdentitySession();
  const identitySession = identity.data;
  const signInUrl = buildOidcAuthorizeUrl(apiBaseUrl, SESSIONS_ROUTE);
  const logoutUrl = buildOidcLogoutUrl(apiBaseUrl, SESSIONS_ROUTE);

  return (
    <ConsolePage
      controls={
        identitySession?.authenticated && identitySession.mode === "secure_oidc_cookie" ? (
          <a className={buttonVariants({ variant: "secondary" })} href={logoutUrl}>
            <LogOut size={16} />
            {strings.ui.sessionSecurityConsole.signOut}
          </a>
        ) : undefined
      }
      eyebrow={strings.ui.sessionSecurityConsole.platformControl}
      sourceLabel={sourceStateLabel(
        deriveSourceState(
          identity.source,
          Boolean(identitySession),
          PROVENANCE_NOT_APPLICABLE,
        ),
        strings.sources.subjects.sessionSecurity,
        strings,
      )}
      subtitle={strings.ui.sessionSecurityConsole.apiOwnedOidcBrowserSessions}
      title={strings.ui.sessionSecurityConsole.sessionSecurity}
    >
      {!identitySession ? (
        <ErrorPanel
          detail={strings.ui.sessionSecurityConsole.liveSessionManagementRequiresThe}
          endpoint={SESSION_ENDPOINTS}
          reference={identity.errorRequestId ?? undefined}
          title={strings.ui.common.sessionApiUnavailable}
        />
      ) : !identitySession.authenticated ? (
        <SignedOutPanel signInUrl={signInUrl} />
      ) : (
        <>
          <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">{strings.ui.sessionSecurityConsole.operatorSession}</p>
                <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.sessionSecurityConsole.apiVerifiedIdentity}</h2>
              </div>
              <span className="status-pill signal-ready">
                <MonitorSmartphone size={15} />
                {identitySession.mode === "secure_oidc_cookie" ? strings.ui.sessionSecurityConsole.cookieSession : strings.ui.sessionSecurityConsole.bearerSession}
              </span>
            </div>
            <div className="mb-3.5 grid gap-2.5 sm:grid-cols-2 [&>span]:grid [&>span]:min-w-0 [&>span]:gap-1 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:text-[11px] [&_small]:font-medium [&_small]:tracking-wide [&_small]:uppercase [&_small]:text-muted [&_strong]:min-w-0 [&_strong]:break-words [&_strong]:text-[13px] [&_strong]:leading-tight [&_strong]:text-ink">
              <span>
                <small>{strings.ui.common.actor}</small>
                <strong>{identitySession.actor_id ?? strings.ui.common.unknown}</strong>
              </span>
              <span>
                <small>{strings.ui.common.tenant}</small>
                <strong>{identitySession.tenant_id ?? strings.ui.common.unknown}</strong>
              </span>
              <span>
                <small>{strings.ui.sessionSecurityConsole.sessionBoundary}</small>
                <strong>{identitySession.session_boundary.replaceAll("_", " ")}</strong>
              </span>
              <span>
                <small>{strings.ui.sessionSecurityConsole.scopes}</small>
                <strong>{formatNumber(identitySession.scopes.length)}</strong>
              </span>
            </div>
            {identitySession.mode !== "secure_oidc_cookie" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {strings.ui.sessionSecurityConsole.thisConsoleIsAttachedThrough}
              </p>
            ) : null}
          </section>
          <SessionListPanel identitySession={identitySession} logoutUrl={logoutUrl} />
        </>
      )}
    </ConsolePage>
  );
}
