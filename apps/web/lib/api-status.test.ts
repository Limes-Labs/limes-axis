import { describe, expect, it } from "vitest";

import { summarizeApiStatus } from "./api-status";

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
