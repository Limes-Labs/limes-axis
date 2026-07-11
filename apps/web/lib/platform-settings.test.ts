import { describe, expect, it } from "vitest";

import {
  countActionRequiredChecks,
  settingsCheckGuidance,
  settingsStatusClass,
  settingsStatusLabel,
} from "./platform-settings";
import { strings } from "./strings";

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

  it("returns a plain-English what-to-do line for known check ids", () => {
    expect(settingsCheckGuidance("https_issuer")).toBe(
      "Use an HTTPS issuer URL from your enterprise IdP before production.",
    );
    expect(settingsCheckGuidance("api_rate_limiting")).toBe(
      strings.settings.guidance.api_rate_limiting,
    );
    expect(settingsCheckGuidance("production_support_model")).toBe(
      strings.settings.guidance.production_support_model,
    );
  });

  it("falls back to generic guidance for unknown check ids", () => {
    expect(settingsCheckGuidance("brand_new_check")).toBe(strings.settings.guidanceFallback);
  });
});
