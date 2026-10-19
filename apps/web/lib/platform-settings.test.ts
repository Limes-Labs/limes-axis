import { describe, expect, it } from "vitest";

import {
  countActionRequiredChecks,
  dependencyStatusClass,
  settingsCheckAction,
  settingsCheckGuidance,
  settingsCheckLabel,
  sortSettingsChecks,
  settingsStatusClass,
  settingsStatusLabel,
} from "./platform-settings";
import { strings } from "./strings";
import { stringsIt } from "./strings.it";

describe("platform settings helpers", () => {
  it("formats readiness status labels for enterprise operators", () => {
    expect(settingsStatusLabel("ready")).toBe("Ready");
    expect(settingsStatusLabel("action_required")).toBe("Action required");
    expect(settingsStatusLabel("ready", stringsIt)).toBe("Pronto");
    expect(settingsStatusLabel("action_required", stringsIt)).toBe("Azione richiesta");
  });

  it("maps readiness statuses to existing console signal classes", () => {
    expect(settingsStatusClass("ready")).toBe("signal-ready");
    expect(settingsStatusClass("action_required")).toBe("signal-action-required");
  });

  it("never styles a not-configured dependency as healthy", () => {
    expect(dependencyStatusClass("ready", true)).toBe("signal-ready");
    expect(dependencyStatusClass("disabled", false)).toBe("status-checking");
    expect(dependencyStatusClass("disabled", true)).toBe("signal-watch");
    expect(dependencyStatusClass("unavailable", true)).toBe("signal-action-required");
    expect(dependencyStatusClass("timeout", false)).toBe("signal-action-required");
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

  it("gives every guided check a human label and humanizes unknown ids", () => {
    for (const checkId of Object.keys(strings.settings.guidance)) {
      expect(settingsCheckLabel(checkId)).not.toBe(checkId.replaceAll("_", " "));
    }
    expect(settingsCheckLabel("api_rate_limiting")).toBe("API rate limiting");
    expect(settingsCheckLabel("new_oidc_https_probe")).toBe("New OIDC HTTPS probe");
  });

  it("links checks to an in-console destination only where one exists", () => {
    expect(settingsCheckAction("oidc_enterprise_sso")).toEqual({
      href: "/settings?tab=identity",
      label: strings.settings.checkActions.identityTab,
    });
    expect(settingsCheckAction("api_rate_limiting")).toBeNull();
    expect(settingsCheckAction("oidc_enterprise_sso", stringsIt)).toEqual({
      href: "/settings?tab=identity",
      label: stringsIt.settings.checkActions.identityTab,
    });
    expect(settingsCheckGuidance("https_issuer", stringsIt)).toBe(
      stringsIt.settings.guidance.https_issuer,
    );
  });

  it("sorts failing checks first, required before recommended, stably", () => {
    const sorted = sortSettingsChecks([
      { check_id: "a", status: "ready", detail: "", production_required: true },
      { check_id: "b", status: "action_required", detail: "", production_required: false },
      { check_id: "c", status: "action_required", detail: "", production_required: true },
      { check_id: "d", status: "action_required", detail: "" },
      { check_id: "e", status: "ready", detail: "", production_required: false },
    ]);
    expect(sorted.map((check) => check.check_id)).toEqual(["c", "d", "b", "a", "e"]);
  });
});
