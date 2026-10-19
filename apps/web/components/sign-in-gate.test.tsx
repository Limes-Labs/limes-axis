import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiBaseUrl: "http://localhost:8000",
  ssoAvailability: "available" as "checking" | "available" | "not_configured" | "unknown",
}));

vi.mock("@/lib/use-browser-sso", () => ({
  useBrowserSsoAvailability: () => mocks.ssoAvailability,
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    apiBaseUrl: mocks.apiBaseUrl,
    apiStatus: { state: "online", label: "Online", detail: "" },
    refreshNonce: 0,
    triggerRefresh: vi.fn(),
  }),
}));

import { SignInGate } from "./sign-in-gate";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";

function gateSession(
  overrides: Partial<IdentitySessionReadModel> = {},
): IdentitySessionReadModel {
  return {
    authenticated: false,
    mode: "public_evaluation",
    actor_id: null,
    tenant_id: null,
    scopes: [],
    expires_at: null,
    api_auth_required: true,
    enterprise_sso_ready: true,
    readiness_status: "ready",
    issuer: "https://idp.example.com/realms/axis",
    audience: "limes-axis-api",
    jwks_source: "explicit_jwks_url",
    session_boundary: "no_authenticated_api_actor",
    capabilities: [],
    limitations: [],
    notes: [],
    unauthenticated_reason: "missing_authorization",
    ...overrides,
  };
}

beforeEach(() => {
  window.history.replaceState(null, "", "/approvals");
  mocks.ssoAvailability = "available";
});

describe("SignInGate", () => {
  it("renders one sign-in action pointing at the API authorize URL with return_to", () => {
    render(<SignInGate identitySession={gateSession()} />);

    const signIn = screen.getByRole("link", { name: /Sign in with SSO/i });
    expect(signIn.getAttribute("href")).toBe(
      "http://localhost:8000/identity/oidc/authorize?return_to=%2Fapprovals",
    );
  });

  it("names the missing-session reason for a first visit", () => {
    render(<SignInGate identitySession={gateSession()} />);

    expect(screen.getByRole("status").textContent).toContain(
      "No active session was found",
    );
  });

  it("tells expired and revoked sessions apart from a first visit", () => {
    const { unmount } = render(
      <SignInGate
        identitySession={gateSession({ unauthenticated_reason: "expired_session_cookie" })}
      />,
    );
    expect(screen.getByRole("status").textContent).toContain("session expired");
    unmount();

    render(
      <SignInGate
        identitySession={gateSession({ unauthenticated_reason: "revoked_session_cookie" })}
      />,
    );
    expect(screen.getByRole("status").textContent).toContain("session was revoked");
  });

  it("falls back to generic verification copy for unknown reason classes", () => {
    render(
      <SignInGate identitySession={gateSession({ unauthenticated_reason: "jwks_fetch_failed" })} />,
    );

    expect(screen.getByRole("status").textContent).toContain(
      "could not be verified",
    );
  });

  it("never renders actor or tenant facts", () => {
    const { container } = render(
      <SignInGate
        identitySession={gateSession({
          actor_id: "operator_acme",
          tenant_id: "tenant_acme",
        })}
      />,
    );

    expect(container.textContent).not.toContain("operator_acme");
    expect(container.textContent).not.toContain("tenant_acme");
  });

  it("shows the IdP host from the issuer without leaking the full URL", () => {
    const { container } = render(<SignInGate identitySession={gateSession()} />);

    expect(container.textContent).toContain("idp.example.com");
  });

  it("moves keyboard focus onto the gate when a live session is lost", () => {
    const { container } = render(<SignInGate identitySession={gateSession()} />);

    const gate = container.querySelector<HTMLElement>("[data-signin-gate]");
    expect(gate).toHaveFocus();
  });

  it("disables sign-in and explains why when the API has no browser SSO configured", () => {
    mocks.ssoAvailability = "not_configured";
    const { container } = render(<SignInGate identitySession={gateSession()} />);

    // No link to /identity/oidc/authorize, which would only answer a raw 503.
    expect(screen.queryByRole("link", { name: /Sign in with SSO/i })).not.toBeInTheDocument();
    const signIn = screen.getByRole("button", { name: /Sign in with SSO/i });
    expect(signIn).toBeDisabled();
    expect(signIn).toHaveAccessibleDescription(
      expect.stringContaining(strings.identityGate.ssoNotConfigured.title),
    );
    expect(container.querySelector("[data-gate-sign-in]")).toBe(signIn);
  });

  it("keeps the sign-in link when SSO readiness cannot be read", () => {
    mocks.ssoAvailability = "unknown";
    render(<SignInGate identitySession={gateSession()} />);

    expect(screen.getByRole("link", { name: /Sign in with SSO/i })).toBeInTheDocument();
  });
});
