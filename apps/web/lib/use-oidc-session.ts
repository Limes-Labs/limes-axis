"use client";

import { useCallback, useEffect, useState } from "react";

import {
  clearStoredOidcSession,
  createOidcSessionFromAccessToken,
  readStoredOidcSession,
  writeStoredOidcSession,
  type OidcConsoleSession,
} from "./oidc-session";

export const AXIS_OIDC_SESSION_UPDATED_EVENT = "limes-axis:oidc-session-updated";

function sessionStorageOrNull(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.sessionStorage ?? null;
  } catch {
    return null;
  }
}

function readBrowserSession(): OidcConsoleSession | null {
  const storage = sessionStorageOrNull();
  return storage ? readStoredOidcSession(storage) : null;
}

export function useOidcConsoleSession() {
  const [session, setSession] = useState<OidcConsoleSession | null>(null);

  useEffect(() => {
    function refreshSession() {
      setSession(readBrowserSession());
    }

    const refreshHandle = window.setTimeout(refreshSession, 0);
    window.addEventListener("storage", refreshSession);
    window.addEventListener(AXIS_OIDC_SESSION_UPDATED_EVENT, refreshSession);
    return () => {
      window.clearTimeout(refreshHandle);
      window.removeEventListener("storage", refreshSession);
      window.removeEventListener(AXIS_OIDC_SESSION_UPDATED_EVENT, refreshSession);
    };
  }, []);

  const saveAccessToken = useCallback((accessToken: string): OidcConsoleSession => {
    const storage = sessionStorageOrNull();
    const nextSession = createOidcSessionFromAccessToken(accessToken);
    if (storage) {
      writeStoredOidcSession(storage, nextSession);
    }

    setSession(nextSession);
    window.dispatchEvent(new Event(AXIS_OIDC_SESSION_UPDATED_EVENT));
    return nextSession;
  }, []);

  const clearSession = useCallback(() => {
    const storage = sessionStorageOrNull();
    if (storage) {
      clearStoredOidcSession(storage);
    }

    setSession(null);
    window.dispatchEvent(new Event(AXIS_OIDC_SESSION_UPDATED_EVENT));
  }, []);

  return {
    session,
    saveAccessToken,
    clearSession,
  };
}
