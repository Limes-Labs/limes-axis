import { afterEach, describe, expect, it, vi } from "vitest";

import { isDefaultApiBaseUrl, summarizeApiStatus } from "./api-status";

describe("api status summary", () => {
  it("reports online when health and readiness are responding", () => {
    expect(summarizeApiStatus({ healthOk: true, readyOk: true })).toMatchObject({
      state: "online",
      label: "Online",
    });
  });

  it("reports degraded when health responds but readiness does not", () => {
    expect(summarizeApiStatus({ healthOk: true, readyOk: false })).toMatchObject({
      state: "degraded",
      label: "Degraded",
    });
  });

  it("reports unavailable when health is unreachable", () => {
    expect(summarizeApiStatus({ healthOk: false, readyOk: false })).toMatchObject({
      state: "unavailable",
      label: "Unavailable",
    });
  });
});

describe("default api base url detection", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("reports the default when no override is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_AXIS_API_BASE_URL", "");
    expect(isDefaultApiBaseUrl()).toBe(true);
  });

  it("reports the default when the override matches the default", () => {
    vi.stubEnv("NEXT_PUBLIC_AXIS_API_BASE_URL", "http://localhost:8000");
    expect(isDefaultApiBaseUrl()).toBe(true);
  });

  it("reports a custom base url when an override is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_AXIS_API_BASE_URL", "https://axis.example.com");
    expect(isDefaultApiBaseUrl()).toBe(false);
  });
});
