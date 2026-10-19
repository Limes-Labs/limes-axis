"use client";

import type { OidcReadinessReport } from "./platform-settings";
import { parseOidcReadinessReport } from "./runtime-contracts/identity";
import type { AxisQuerySource } from "./use-axis-query";
import { useAxisQuery } from "./use-axis-query";

/** Public, unauthenticated OIDC readiness report owned by the API. */
export const OIDC_READINESS_ENDPOINT = "/identity/oidc/readiness";

/**
 * The readiness checks `GET /identity/oidc/authorize` depends on. When either
 * is not ready the API answers the redirect with a raw `503` JSON body
 * ("OIDC authorization-code login is not configured"), so a sign-in link must
 * not send the browser there.
 */
export const BROWSER_SSO_REQUIRED_CHECKS = [
  "authorization_code_client",
  "session_cookie_signing",
] as const;

/**
 * `not_configured` is the only state that disables sign-in. While the report
 * is loading, or when it cannot be read (`unknown`), the link stays usable:
 * a flaky readiness probe must never lock an operator out of SSO.
 */
export type BrowserSsoAvailability = "checking" | "available" | "not_configured" | "unknown";

export function browserSsoAvailability(
  report: Pick<OidcReadinessReport, "checks"> | null,
  source: AxisQuerySource,
): BrowserSsoAvailability {
  if (report) {
    const ready = BROWSER_SSO_REQUIRED_CHECKS.every((checkId) =>
      report.checks.some((check) => check.check_id === checkId && check.status === "ready"),
    );
    return ready ? "available" : "not_configured";
  }
  return source === "loading" ? "checking" : "unknown";
}

export function useBrowserSsoAvailability(): BrowserSsoAvailability {
  const readiness = useAxisQuery<OidcReadinessReport>(OIDC_READINESS_ENDPOINT, {
    parse: parseOidcReadinessReport,
  });
  return browserSsoAvailability(readiness.data, readiness.source);
}
