"use client";

import { Check, KeyRound, LogOut, UserRound, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useOidcConsoleSession } from "@/lib/use-oidc-session";

function compactActorLabel(actorId: string): string {
  return actorId.length > 28 ? `${actorId.slice(0, 25)}...` : actorId;
}

export function OidcSessionBridge() {
  const { session, saveAccessToken, clearSession } = useOidcConsoleSession();
  const [isEditing, setIsEditing] = useState(false);
  const [accessToken, setAccessToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  function connectSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const token = accessToken.trim();
    if (!token) {
      setError(null);
      return;
    }

    try {
      saveAccessToken(token);
      setAccessToken("");
      setError(null);
      setIsEditing(false);
    } catch {
      setError("Invalid token");
    }
  }

  function cancelEdit() {
    setAccessToken("");
    setError(null);
    setIsEditing(false);
  }

  if (!session) {
    if (isEditing) {
      return (
        <form className="inline-flex max-w-[min(100%,440px)] min-w-0 items-center gap-1.5" onSubmit={connectSession} aria-label="OIDC session">
          <KeyRound size={16} aria-hidden="true" />
          <input
            aria-invalid={Boolean(error)}
            aria-label="OIDC bearer token"
            className="min-h-[38px] w-[min(34vw,180px)] min-w-[132px] rounded-xl border border-line bg-surface px-2.5 text-sm text-ink focus:border-signal focus:ring-2 focus:ring-signal/25 focus:outline-none aria-[invalid=true]:border-danger dark:border-white/15 dark:bg-white/5"
            onChange={(event) => {
              setAccessToken(event.target.value);
              setError(null);
            }}
            placeholder="Bearer token"
            type="password"
            value={accessToken}
          />
          {error ? (
            <span className="text-xs font-semibold whitespace-nowrap text-danger" role="status">
              {error}
            </span>
          ) : null}
          <button className="icon-button" type="submit" aria-label="Connect OIDC session">
            <Check size={16} />
          </button>
          <button
            className="icon-button"
            type="button"
            onClick={cancelEdit}
            aria-label="Cancel OIDC session entry"
          >
            <X size={16} />
          </button>
        </form>
      );
    }

    return (
      <button
        className="icon-button"
        type="button"
        onClick={() => setIsEditing(true)}
        title="Connect OIDC bearer token"
        aria-label="Connect OIDC bearer token"
      >
        <KeyRound size={17} />
      </button>
    );
  }

  return (
    <div className="inline-flex min-w-0 items-center gap-2" aria-label="OIDC session">
      <span className="status-pill signal-ready max-w-[220px] overflow-hidden text-ellipsis whitespace-nowrap" title={session.actorId}>
        <UserRound size={15} />
        {compactActorLabel(session.actorId)}
      </span>
      <button
        className="icon-button"
        type="button"
        onClick={clearSession}
        aria-label="Clear OIDC session"
        title="Clear OIDC session"
      >
        <LogOut size={16} />
      </button>
    </div>
  );
}
