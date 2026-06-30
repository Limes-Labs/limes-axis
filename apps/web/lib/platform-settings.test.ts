import { describe, expect, it } from "vitest";

import {
  countActionRequiredChecks,
  settingsStatusClass,
  settingsStatusLabel,
} from "./platform-settings";

describe("platform settings helpers", () => {
  it("formats readiness status labels for enterprise operators", () => {
    expect(settingsStatusLabel("ready")).toBe("Ready");
    expect(settingsStatusLabel("action_required")).toBe("Action required");
  });

  it("maps readiness statuses to existing console signal classes", () => {
    expect(settingsStatusClass("ready")).toBe("signal-ready");
    expect(settingsStatusClass("action_required")).toBe("signal-action-required");
  });

  it("counts only checks that need action", () => {
    expect(
      countActionRequiredChecks([
        { check_id: "oidc", status: "action_required", detail: "OIDC needs hardening." },
        { check_id: "egress", status: "ready", detail: "External egress is disabled." },
      ]),
    ).toBe(1);
  });
});
