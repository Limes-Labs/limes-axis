import type { ConsoleStrings } from "@/lib/i18n";
import { strings } from "@/lib/strings";

export type ApiStatusState = "checking" | "online" | "degraded" | "unavailable";

export type ApiStatusSummary = {
  state: ApiStatusState;
  label: string;
  detail: string;
};

export type ApiProbeResult = {
  healthOk: boolean;
  readyOk: boolean;
};

export const DEFAULT_API_BASE_URL = "http://localhost:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_AXIS_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export function isDefaultApiBaseUrl(): boolean {
  const configured = process.env.NEXT_PUBLIC_AXIS_API_BASE_URL;
  return !configured || configured === DEFAULT_API_BASE_URL;
}

/** Label and detail for an API status, from the active catalogue. */
export function apiStatusCopy(
  state: ApiStatusState,
  copy: ConsoleStrings = strings,
): { label: string; detail: string } {
  return copy.labels.apiStatus[state];
}

export function summarizeApiStatus(probe: ApiProbeResult): ApiStatusSummary {
  const state: ApiStatusState = probe.healthOk && probe.readyOk
    ? "online"
    : probe.healthOk
      ? "degraded"
      : "unavailable";
  return { state, ...apiStatusCopy(state) };
}
