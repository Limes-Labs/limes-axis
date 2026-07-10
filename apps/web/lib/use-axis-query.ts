"use client";

import { useEffect, useRef, useState } from "react";

import { axisFetchJson } from "@/lib/axis-api";
import { useConsole } from "@/providers/console-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

export type AxisQuerySource = "loading" | "api" | "unavailable";

type UseAxisQueryOptions = {
  enabled?: boolean;
};

/**
 * Fetch a JSON payload from the Axis API with stale-while-revalidate
 * semantics: the initial load starts at `source: "loading"`, but refetches
 * triggered by the global refresh bus or a session change keep the previous
 * data on screen and flag `isRefreshing` instead. A failed refresh flips
 * `source` to "unavailable" and sets `error` while keeping the stale data
 * for display. Changing `path` is a different query, so it resets to
 * loading and drops the old data.
 */
export function useAxisQuery<T>(path: string, options: UseAxisQueryOptions = {}) {
  const { refreshNonce } = useConsole();
  const { session } = useOidcConsoleSession();
  const [data, setData] = useState<T | null>(null);
  const [source, setSource] = useState<AxisQuerySource>("loading");
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const enabled = options.enabled ?? true;

  // The data currently held for `lastLoadedPathRef.current`; used to decide
  // whether a refetch is a background refresh (keep data) or a fresh load.
  const staleDataRef = useRef<T | null>(null);
  const lastLoadedPathRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    if (lastLoadedPathRef.current !== path) {
      lastLoadedPathRef.current = path;
      staleDataRef.current = null;
    }

    const isRefresh = staleDataRef.current !== null;
    const controller = new AbortController();

    async function load() {
      if (isRefresh) {
        setIsRefreshing(true);
      } else {
        setData(null);
        setSource("loading");
        setError(null);
        setIsRefreshing(false);
      }

      try {
        const payload = await axisFetchJson<T>(path, {
          session,
          signal: controller.signal,
        });

        if (!controller.signal.aborted) {
          staleDataRef.current = payload;
          setData(payload);
          setSource("api");
          setError(null);
          setIsRefreshing(false);
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          if (!isRefresh) {
            setData(null);
          }
          setSource("unavailable");
          setError(caught instanceof Error ? caught.message : "Axis API request failed.");
          setIsRefreshing(false);
        }
      }
    }

    void load();

    return () => controller.abort();
  }, [path, session, refreshNonce, enabled]);

  return {
    data,
    source,
    error,
    isRefreshing,
    isLoading: source === "loading",
    isUnavailable: source === "unavailable",
  };
}
