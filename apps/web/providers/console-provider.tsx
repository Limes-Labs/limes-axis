"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getApiBaseUrl, summarizeApiStatus, type ApiStatusSummary } from "@/lib/api-status";
import { AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT } from "@/lib/axis-api";

type ConsoleContextValue = {
  apiStatus: ApiStatusSummary;
  apiBaseUrl: string;
  refreshNonce: number;
  triggerRefresh: () => void;
};

const ConsoleContext = createContext<ConsoleContextValue | null>(null);

async function probeApi(baseUrl: string, signal: AbortSignal) {
  const [healthResponse, readyResponse] = await Promise.all([
    fetch(`${baseUrl}/health`, { signal, cache: "no-store" }),
    fetch(`${baseUrl}/ready`, { signal, cache: "no-store" }),
  ]);

  return summarizeApiStatus({
    healthOk: healthResponse.ok,
    readyOk: readyResponse.ok,
  });
}

export function ConsoleProvider({ children }: { children: ReactNode }) {
  const apiBaseUrl = getApiBaseUrl();
  const [apiStatus, setApiStatus] = useState<ApiStatusSummary>({
    state: "checking",
    label: "Checking",
    detail: "Probing Axis API health and readiness.",
  });
  const [refreshNonce, setRefreshNonce] = useState(0);

  const triggerRefresh = useCallback(() => {
    setRefreshNonce((value) => value + 1);
  }, []);

  useEffect(() => {
    // When a browser-session refresh fails the API request layer announces the
    // signed-out state; re-running the live queries lets /identity/session
    // report the public state across the console without local session state.
    window.addEventListener(AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT, triggerRefresh);
    return () => {
      window.removeEventListener(AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT, triggerRefresh);
    };
  }, [triggerRefresh]);

  useEffect(() => {
    const controller = new AbortController();

    async function checkApi() {
      try {
        setApiStatus({
          state: "checking",
          label: "Checking",
          detail: "Probing Axis API health and readiness.",
        });
        setApiStatus(await probeApi(apiBaseUrl, controller.signal));
      } catch {
        if (!controller.signal.aborted) {
          setApiStatus(summarizeApiStatus({ healthOk: false, readyOk: false }));
        }
      }
    }

    void checkApi();
    const interval = window.setInterval(() => {
      void checkApi();
    }, 30_000);

    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [apiBaseUrl, refreshNonce]);

  const value = useMemo(
    () => ({
      apiStatus,
      apiBaseUrl,
      refreshNonce,
      triggerRefresh,
    }),
    [apiBaseUrl, apiStatus, refreshNonce, triggerRefresh],
  );

  return <ConsoleContext.Provider value={value}>{children}</ConsoleContext.Provider>;
}

export function useConsole(): ConsoleContextValue {
  const context = useContext(ConsoleContext);
  if (!context) {
    throw new Error("useConsole must be used within ConsoleProvider.");
  }

  return context;
}