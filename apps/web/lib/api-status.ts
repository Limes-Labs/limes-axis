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

export function summarizeApiStatus(probe: ApiProbeResult): ApiStatusSummary {
  if (probe.healthOk && probe.readyOk) {
    return {
      state: "online",
      label: "Online",
      detail: "Health and readiness checks are responding.",
    };
  }

  if (probe.healthOk) {
    return {
      state: "degraded",
      label: "Degraded",
      detail: "Health is responding, but readiness is not confirmed.",
    };
  }

  return {
    state: "unavailable",
    label: "Unavailable",
    detail: "API is not reachable from the console.",
  };
}
