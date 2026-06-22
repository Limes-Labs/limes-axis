import { describe, expect, it } from "vitest";

import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "./platform-overview";

describe("platform overview helpers", () => {
  it("formats platform status labels and classes", () => {
    expect(platformStatusLabel("action_required")).toBe("Action Required");
    expect(platformStatusClass("action_required")).toBe("signal-action-required");
    expect(platformStatusClass("ready")).toBe("signal-ready");
    expect(platformStatusLabel("watch")).toBe("Watch");
  });

  it("formats API timestamps for display", () => {
    expect(formatOverviewTimestamp("2026-06-22T09:00:00+02:00")).toContain("2026");
  });
});
