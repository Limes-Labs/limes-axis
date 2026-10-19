import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AccountPanel } from "./account-panel";

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({
    session: null,
    saveAccessToken: vi.fn(),
    clearSession: vi.fn(),
  }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    apiBaseUrl: "http://localhost:8000",
    apiStatus: { state: "online", label: "Online", detail: "API reachable" },
    refreshNonce: 0,
    triggerRefresh: vi.fn(),
  }),
}));

describe("AccountPanel", () => {
  it("renders the SSO sign-in button when unauthenticated", () => {
    render(<AccountPanel identitySession={null} identitySessionUnavailable={false} />);

    const signIn = screen.getByRole("link", { name: /Sign in with SSO/ });
    expect(signIn).toHaveAttribute(
      "href",
      expect.stringContaining("/identity/oidc/authorize"),
    );
  });

  it("hides the bearer-token form until Developer access is expanded", async () => {
    const user = userEvent.setup();
    render(<AccountPanel identitySession={null} identitySessionUnavailable={false} />);

    expect(screen.queryByPlaceholderText("Paste JWT access token")).not.toBeInTheDocument();
    expect(
      screen.queryByText("For local development against a non-SSO API."),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Developer access" }));

    expect(screen.getByPlaceholderText("Paste JWT access token")).toBeInTheDocument();
    expect(
      screen.getByText("For local development against a non-SSO API."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Attach bearer bridge/ }),
    ).toBeInTheDocument();
  });

  it("collapses the bearer-token form again on a second click", async () => {
    const user = userEvent.setup();
    render(<AccountPanel identitySession={null} identitySessionUnavailable={false} />);

    const trigger = screen.getByRole("button", { name: "Developer access" });
    await user.click(trigger);
    expect(screen.getByPlaceholderText("Paste JWT access token")).toBeInTheDocument();

    await user.click(trigger);
    expect(screen.queryByPlaceholderText("Paste JWT access token")).not.toBeInTheDocument();
  });

  it("announces a rejected bearer bridge submission with role=alert", async () => {
    const user = userEvent.setup();
    render(<AccountPanel identitySession={null} identitySessionUnavailable={false} />);

    await user.click(screen.getByRole("button", { name: "Developer access" }));
    await user.click(screen.getByRole("button", { name: /Attach bearer bridge/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Paste a JWT bearer token to bridge an OIDC session.",
    );
  });

  it("names the tenant and keeps raw scopes behind an Inspect disclosure", async () => {
    const user = userEvent.setup();
    render(
      <AccountPanel
        identitySession={{
          authenticated: true,
          mode: "secure_oidc_cookie",
          actor_id: "plant.operator",
          tenant_id: "tenant_demo_manufacturing",
          scopes: ["approvals:supply:decide", "tenant:read"],
          expires_at: null,
          api_auth_required: true,
          enterprise_sso_ready: true,
          readiness_status: "ready",
          issuer: "https://issuer.example",
          audience: "limes-axis-api",
          jwks_source: "remote",
          session_boundary: "cookie",
          capabilities: [],
          limitations: [],
          notes: [],
          unauthenticated_reason: null,
        }}
        identitySessionUnavailable={false}
      />,
    );

    expect(screen.getByText("Demo manufacturing")).toHaveAttribute(
      "title",
      "tenant_demo_manufacturing",
    );
    const scopes = screen.getByText(/2 permissions/).closest("details");
    expect(scopes).not.toHaveAttribute("open");
    expect(screen.getByText("approvals:supply:decide")).not.toBeVisible();

    await user.click(screen.getByText(/2 permissions/));
    expect(scopes).toHaveAttribute("open");
    expect(scopes).toHaveTextContent("Approvals · supply · decide");
  });
});
