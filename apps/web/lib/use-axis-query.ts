"use client";

import { useEffect, useState } from "react";

import { axisFetchJson } from "@/lib/axis-api";
import { useConsole } from "@/providers/console-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

export type AxisQuerySource = "loading" | "api" | "unavailable";

type UseAxisQueryOptions = {
  enabled?: boolean;
};

export function useAxisQuery<T>(path: string, options: UseAxisQueryOptions = {}) {
  const { refreshNonce } = useConsole();
  const { session } = useOidcConsoleSession();
  const [data, setData] = useState<T | null>(null);
  const [source, setSource] = useState<AxisQuerySource>("loading");
  const [error, setError] = useState<string | null>(null);
  const enabled = options.enabled ?? true;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const controller = new AbortController();

    async function load() {
      setSource("loading");
      setError(null);

      try {
        const payload = await axisFetchJson<T>(path, {
          session,
          signal: controller.signal,
        });

        if (!controller.signal.aborted) {
          setData(payload);
          setSource("api");
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setData(null);
          setSource("unavailable");
          setError(caught instanceof Error ? caught.message : "Axis API request failed.");
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
    isLoading: source === "loading",
    isUnavailable: source === "unavailable",
  };
}
