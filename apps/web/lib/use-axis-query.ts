"use client";

import { useEffect, useRef, useState } from "react";

import { AxisApiDecodeError, AxisApiError, axisFetchParsedJson } from "@/lib/axis-api";
import { useConsole } from "@/providers/console-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

export type AxisQuerySource = "loading" | "api" | "unavailable";

type AxisQueryFailureDetails = {
  code: string | null;
  reason: string | null;
  requestId: string | null;
  validationIssues: readonly unknown[];
};

const EMPTY_FAILURE_DETAILS: AxisQueryFailureDetails = {
  code: null,
  reason: null,
  requestId: null,
  validationIssues: [],
};

type UseAxisQueryOptions<T> = {
  enabled?: boolean;
  parse: (value: unknown) => T;
};

/**
 * Fetch a JSON payload from the Axis API with stale-while-revalidate
 * semantics: the initial load starts at `source: "loading"`, but refetches
 * triggered by the global refresh bus keep the previous data on screen and
 * flag `isRefreshing` instead. A failed refresh flips
 * `source` to "unavailable" and sets `error` while keeping the stale data
 * for display. Changing `path` is a different query, so it resets to
 * loading and drops the old data. An actor or tenant change is also a new
 * query identity and can never reuse the previous principal's data.
 */
export function useAxisQuery<T>(path: string, options: UseAxisQueryOptions<T>) {
  const { refreshNonce } = useConsole();
  const { session } = useOidcConsoleSession();
  const [data, setData] = useState<T | null>(null);
  const [source, setSource] = useState<AxisQuerySource>("loading");
  const [error, setError] = useState<string | null>(null);
  /** HTTP status of the last failed request; null for non-HTTP failures. */
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [errorDetails, setErrorDetails] = useState<AxisQueryFailureDetails>(
    EMPTY_FAILURE_DETAILS,
  );
  const [isRefreshing, setIsRefreshing] = useState(false);
  const enabled = options.enabled ?? true;
  const parse = options.parse;

  // The data currently held for `lastLoadedKeyRef.current`; used to decide
  // whether a refetch is a background refresh (keep data) or a fresh load.
  const staleDataRef = useRef<T | null>(null);
  const lastLoadedKeyRef = useRef<string | null>(null);
  const sessionIdentity = session ? `${session.tenantId}\u0000${session.actorId}` : "cookie-session";

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const queryKey = `${path}\u0000${sessionIdentity}`;
    if (lastLoadedKeyRef.current !== queryKey) {
      lastLoadedKeyRef.current = queryKey;
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
        setErrorStatus(null);
        setErrorDetails(EMPTY_FAILURE_DETAILS);
        setIsRefreshing(false);
      }

      try {
        const fetchOptions = { session, signal: controller.signal };
        const payload = await axisFetchParsedJson(path, parse, fetchOptions);

        if (!controller.signal.aborted) {
          staleDataRef.current = payload;
          setData(payload);
          setSource("api");
          setError(null);
          setErrorStatus(null);
          setErrorDetails(EMPTY_FAILURE_DETAILS);
          setIsRefreshing(false);
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          if (!isRefresh) {
            setData(null);
          }
          setSource("unavailable");
          setError(caught instanceof Error ? caught.message : "Axis API request failed.");
          setErrorStatus(caught instanceof AxisApiError ? caught.status : null);
          setErrorDetails({
            code: caught instanceof AxisApiError ? caught.code : null,
            reason: caught instanceof AxisApiError ? caught.reason : null,
            requestId:
              caught instanceof AxisApiError || caught instanceof AxisApiDecodeError
                ? caught.requestId
                : null,
            validationIssues:
              caught instanceof AxisApiError || caught instanceof AxisApiDecodeError
                ? caught.validationIssues
                : [],
          });
          setIsRefreshing(false);
        }
      }
    }

    void load();

    return () => controller.abort();
  }, [path, session, sessionIdentity, refreshNonce, enabled, parse]);

  return {
    data,
    source,
    error,
    errorStatus,
    errorCode: errorDetails.code,
    errorReason: errorDetails.reason,
    errorRequestId: errorDetails.requestId,
    validationIssues: errorDetails.validationIssues,
    isRefreshing,
    isLoading: source === "loading",
    isUnavailable: source === "unavailable",
  };
}
