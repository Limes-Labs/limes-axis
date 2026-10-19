"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  getApiBaseUrl,
  summarizeApiStatus,
  type ApiStatusState,
  type ApiStatusSummary,
} from "@/lib/api-status";
import { AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT } from "@/lib/axis-api";

type ConsoleContextValue = {
  apiStatus: ApiStatusSummary;
  apiBaseUrl: string;
  refreshNonce: number;
  triggerRefresh: () => void;
};

const ConsoleContext = createContext<ConsoleContextValue | null>(null);

export async function probeApi(baseUrl: string, signal: AbortSignal) {
  const [healthResult, readyResult] = await Promise.allSettled([
    fetch(`${baseUrl}/health`, { signal, cache: "no-store" }),
    fetch(`${baseUrl}/ready`, { signal, cache: "no-store" }),
  ]);

  return summarizeApiStatus({
    healthOk: healthResult.status === "fulfilled" && healthResult.value.ok,
    readyOk: readyResult.status === "fulfilled" && readyResult.value.ok,
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
  /**
   * Last probe result that was not "checking". Every probe passes through
   * "checking", so recovery is detected against the previous settled state.
   */
  const settledApiStateRef = useRef<ApiStatusState | null>(null);

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
    let latestProbe = 0;

    async function checkApi() {
      const probeId = ++latestProbe;
      try {
        setApiStatus({
          state: "checking",
          label: "Checking",
          detail: "Probing Axis API health and readiness.",
        });
        const nextStatus = await probeApi(apiBaseUrl, controller.signal);
        if (!controller.signal.aborted && probeId === latestProbe) {
          settle(nextStatus);
        }
      } catch {
        if (!controller.signal.aborted) {
          settle(summarizeApiStatus({ healthOk: false, readyOk: false }));
        }
      }
    }

    function settle(nextStatus: ApiStatusSummary) {
      const previous = settledApiStateRef.current;
      settledApiStateRef.current = nextStatus.state;
      setApiStatus(nextStatus);
      if (previous === "unavailable" && nextStatus.state !== "unavailable") {
        // The API came back after an outage. Every query (identity first —
        // tenant queries wait on it) failed while it was down and nothing else
        // would re-run them, so re-run the console. The refresh re-probes once
        // more; that probe settles from a reachable state and cannot loop.
        triggerRefresh();
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
  }, [apiBaseUrl, refreshNonce, triggerRefresh]);

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
