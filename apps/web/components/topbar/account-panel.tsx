"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { CircleHelp, KeyRound, LogOut, MonitorSmartphone, ShieldCheck } from "lucide-react";

import {
  PopoverHeader,
  commandClass,
  commandSecondaryClass,
  popoverClass,
  popoverRowClass,
  tagClass,
} from "@/components/topbar/panel-chrome";
import { Disclosure } from "@/components/ui/disclosure";
import { LocaleSwitch } from "@/components/locale-switch";
import { SsoSignInLink } from "@/components/sso-sign-in-link";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import {
  compactActorLabel,
  formatExpiry,
  identitySessionLabel,
  identitySessionTone,
  operatorInitials,
} from "@/lib/identity-format";
import {
  buildOidcAuthorizeUrl,
  buildOidcLogoutUrl,
  currentReturnPath,
} from "@/lib/oidc-session";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { useStrings } from "@/providers/locale-provider";
import { humanizeIdentifier, humanizeScope } from "@/lib/display-names";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

export function AccountPanel({
  className,
  identitySession,
  identitySessionUnavailable,
}: {
  className?: string;
  identitySession: IdentitySessionReadModel | null;
  identitySessionUnavailable: boolean;
}) {
  const strings = useStrings();
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
      setError(strings.ui.topbarAccountPanel.pasteTokenError);
      return;
    }

    try {
      saveAccessToken(token);
      setAccessToken("");
      setError(null);
    } catch {
      setError(strings.ui.topbarAccountPanel.tokenRejected);
    }
  }

  function signOutWithIdentityProvider() {
    clearSession();
    window.location.assign(buildOidcLogoutUrl(apiBaseUrl, currentReturnPath()));
  }

  return (
    <section
      className={cn(className ?? popoverClass, "w-[min(390px,calc(100vw-32px))]")}
      aria-label={strings.ui.topbarAccountPanel.operatorAccount}
    >
      <PopoverHeader label={strings.ui.topbarAccountPanel.operator}>
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
                ? strings.ui.common.sessionApiUnavailable
                : strings.ui.topbarAccountPanel.publicEvaluationOperator}
          </p>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug break-words text-muted">
            {identitySession?.authenticated && identitySession.tenant_id
              ? (
                  <span title={identitySession.tenant_id}>
                    {humanizeIdentifier(identitySession.tenant_id)}
                  </span>
                )
              : identitySession?.session_boundary ?? strings.ui.topbarAccountPanel.sessionEndpointRequired}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 [&>span]:min-w-0 [&>span]:rounded-xl [&>span]:border [&>span]:border-line/60 [&>span]:bg-ink/3 [&>span]:p-2.5 dark:[&>span]:border-white/10 dark:[&>span]:bg-white/4 [&_small]:block [&_small]:text-[11px] [&_small]:text-muted [&_strong]:mt-0.5 [&_strong]:block [&_strong]:min-w-0 [&_strong]:text-xs [&_strong]:leading-tight [&_strong]:break-words [&_strong]:text-ink">
        <span>
          <small>API</small>
          <strong>{apiBaseUrl}</strong>
        </span>
        <span>
          <small>{strings.ui.topbarAccountPanel.apiStatus}</small>
          <strong>{apiStatus.label}</strong>
        </span>
        <span>
          <small>{strings.ui.topbarAccountPanel.ssoPosture}</small>
          <strong>
            {identitySession
              ? identitySession.enterprise_sso_ready
                ? strings.ui.topbarAccountPanel.enterpriseReady
                : strings.ui.topbarAccountPanel.needsHardening
              : strings.ui.common.unknown}
          </strong>
        </span>
        <span>
          <small>{strings.ui.topbarAccountPanel.sessionExpires}</small>
          <strong>{formatExpiry(identitySession?.expires_at ?? undefined)}</strong>
        </span>
      </div>

      {identitySession ? (
        <div className="grid max-h-[188px] gap-2 overflow-y-auto overscroll-contain">
          {identitySession.capabilities.slice(0, 2).map((capability) => (
            <div className={popoverRowClass} key={capability}>
              <span aria-hidden="true" className="status-dot signal-ready" />
              <span>
                <strong>{strings.ui.topbarAccountPanel.capability}</strong>
                <small>{capability}</small>
              </span>
            </div>
          ))}
          {identitySession.limitations.slice(0, 2).map((limitation) => (
            <div className={popoverRowClass} key={limitation}>
              <span aria-hidden="true" className="status-dot signal-watch" />
              <span>
                <strong>{strings.ui.topbarAccountPanel.limitation}</strong>
                <small>{limitation}</small>
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="m-0 text-sm leading-snug text-muted">
          {strings.ui.topbarAccountPanel.needsSessionEndpoint}
        </p>
      )}

      {verifiedCookieSession || session ? (
        <>
          <div className="flex max-h-[86px] min-w-0 flex-wrap gap-2 overflow-y-auto overscroll-contain">
            {visibleScopes.length > 0 ? (
              // Scopes read as plain words; the raw scope strings stay behind
              // the Inspect disclosure.
              <Disclosure
                className="text-xs text-muted"
                size="sm"
                title={`${strings.identifiers.permissions(visibleScopes.length)} · ${strings.identifiers.inspect}`}
                variant="plain"
              >
                <ul className="m-0 grid list-none gap-1 p-0" data-account-scopes>
                  {visibleScopes.map((scope) => (
                    <li key={scope}>
                      {humanizeScope(scope)}{" "}
                      <span className="font-mono text-[11px] text-muted">{scope}</span>
                    </li>
                  ))}
                </ul>
              </Disclosure>
            ) : (
              <span className={tagClass}>
                {identitySession?.authenticated ? strings.ui.topbarAccountPanel.noScopesInToken : strings.ui.topbarAccountPanel.awaitingApiValidation}
              </span>
            )}
          </div>
          <Link className={commandSecondaryClass} href="/settings/sessions">
            <MonitorSmartphone size={16} />
            {strings.ui.topbarAccountPanel.manageSessions}
          </Link>
          {verifiedCookieSession ? (
            <button
              className={commandClass}
              onClick={signOutWithIdentityProvider}
              type="button"
            >
              <LogOut size={16} />
              {strings.ui.topbarAccountPanel.signOutWithIdentityProvider}
            </button>
          ) : (
            <button className={commandClass} onClick={clearSession} type="button">
              <LogOut size={16} />
              {strings.ui.topbarAccountPanel.clearBearerBridge}
            </button>
          )}
        </>
      ) : (
        <div className="grid gap-2">
          <SsoSignInLink className={commandClass} href={authorizeUrl}>
            <ShieldCheck size={16} />
            {strings.identityGate.signIn}
          </SsoSignInLink>
          <a
            className={commandSecondaryClass}
            href={onboardingUrl}
            rel="noreferrer"
            target="_blank"
          >
            <CircleHelp size={16} />
            {strings.ui.topbarAccountPanel.openSsoSetup}
          </a>
          <Disclosure
            className="justify-self-start"
            keepMounted={false}
            onOpenChange={setDeveloperBridgeOpen}
            open={developerBridgeOpen}
            size="sm"
            title={strings.ui.topbarAccountPanel.developerAccess}
            variant="plain"
          >
            <div className="grid gap-2">
              <p className="m-0 text-xs leading-snug text-muted">
                {strings.ui.topbarAccountPanel.forLocalDevelopmentAgainstA}
              </p>
              {!authenticatedSession ? (
                <form className="grid gap-2" onSubmit={connectSession}>
                  <label className="grid gap-1.5 text-xs font-semibold text-muted">
                    {strings.ui.topbarAccountPanel.developerBearerBridge}
                    <Input
                      aria-invalid={Boolean(error)}
                      onChange={(event) => {
                        setAccessToken(event.target.value);
                        setError(null);
                      }}
                      placeholder={strings.ui.topbarAccountPanel.pasteJwtAccessToken}
                      type="password"
                      value={accessToken}
                    />
                  </label>
                  {error ? (
                    <span className="text-xs font-semibold text-danger" role="alert">
                      {error}
                    </span>
                  ) : null}
                  <button className={commandClass} type="submit">
                    <KeyRound size={16} />
                    {strings.ui.topbarAccountPanel.attachBearerBridge}
                  </button>
                </form>
              ) : null}
            </div>
          </Disclosure>
        </div>
      )}

      <LocaleSwitch />
    </section>
  );
}
