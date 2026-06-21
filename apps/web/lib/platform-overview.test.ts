import { describe, expect, it } from "vitest";

import {
  defaultManufacturingOverview,
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "./platform-overview";

describe("platform overview demo contract", () => {
  it("keeps a manufacturing demo seed available without the API", () => {
    expect(defaultManufacturingOverview.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingOverview.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingOverview.approvals.some((item) => item.risk_level === "high")).toBe(
      true,
    );
  });

  it("formats platform status labels and classes", () => {
    expect(platformStatusLabel("action_required")).toBe("Action Required");
    expect(platformStatusClass("action_required")).toBe("signal-action-required");
    expect(platformStatusLabel("watch")).toBe("Watch");
  });

  it("formats the demo timestamp for display", () => {
    expect(formatOverviewTimestamp(defaultManufacturingOverview.as_of)).toContain("2026");
  });
});
