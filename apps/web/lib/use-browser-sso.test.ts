import { describe, expect, it } from "vitest";

import { browserSsoAvailability } from "./use-browser-sso";

function report(statuses: Record<string, "ready" | "action_required">) {
  return {
    checks: Object.entries(statuses).map(([check_id, status]) => ({
      check_id,
      status,
      detail: "",
    })),
  };
}

describe("browserSsoAvailability", () => {
  it("is available only when the authorize endpoint's own prerequisites are ready", () => {
    expect(
      browserSsoAvailability(
        report({
          authorization_code_client: "ready",
          session_cookie_signing: "ready",
          // Enterprise hardening checks do not gate the authorize redirect.
          authorization_endpoint: "action_required",
        }),
        "api",
      ),
    ).toBe("available");
  });

  it("is not configured when the client id or cookie signing secret is missing", () => {
    expect(
      browserSsoAvailability(
        report({ authorization_code_client: "action_required", session_cookie_signing: "ready" }),
        "api",
      ),
    ).toBe("not_configured");
    expect(
      browserSsoAvailability(report({ authorization_code_client: "ready" }), "api"),
    ).toBe("not_configured");
  });

  it("never disables sign-in while readiness is loading or unreadable", () => {
    expect(browserSsoAvailability(null, "loading")).toBe("checking");
    expect(browserSsoAvailability(null, "unavailable")).toBe("unknown");
  });
});
