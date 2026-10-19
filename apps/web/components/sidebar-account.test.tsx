import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SidebarAccount } from "@/components/sidebar-account";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";

// The footer hosts AccountPanel, which reads the OIDC session and console
// context; both are stubbed here so these tests stay about the footer itself.
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

const identity = {
  authenticated: true,
  mode: "secure_oidc_cookie",
  actor_id: "plant.operator",
  tenant_id: "tenant_demo_manufacturing",
  scopes: ["tenant:read"],
  expires_at: 4102444800,
  api_auth_required: true,
  enterprise_sso_ready: true,
  readiness_status: "watch",
  issuer: "https://idp.example/realms/axis",
  audience: "limes-axis-api",
  jwks_source: "configured",
  session_boundary: "http_only_cookie_verified_by_axis_api",
  capabilities: [],
  limitations: [],
  notes: [],
} as unknown as IdentitySessionReadModel;

function renderFooter(overrides: Partial<Parameters<typeof SidebarAccount>[0]> = {}) {
  return render(
    <SidebarAccount
      identitySession={identity}
      identitySessionUnavailable={false}
      settingsActive={false}
      {...overrides}
    />,
  );
}

describe("SidebarAccount", () => {
  it("names the signed-in actor and tenant instead of only initials", () => {
    renderFooter();

    expect(screen.getByText("plant.operator")).toBeInTheDocument();
    expect(screen.getByText("tenant_demo_manufacturing")).toBeInTheDocument();
  });

  it("falls back to explicit copy rather than blank lines when identity is absent", () => {
    renderFooter({ identitySession: null, identitySessionUnavailable: true });

    expect(screen.getByText(strings.nav.signedOut)).toBeInTheDocument();
    expect(screen.getByText(strings.nav.noTenant)).toBeInTheDocument();
  });

  it("opens the account panel from the footer and closes it on Escape", async () => {
    const user = userEvent.setup();
    renderFooter();
    const trigger = screen.getByRole("button", { name: "Open operator account" });

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("positions rail panels against the viewport so the clipped rail cannot cut them", async () => {
    const user = userEvent.setup();
    renderFooter();
    const trigger = screen.getByRole("button", { name: "Open platform help" });
    const footer = trigger.parentElement as HTMLElement;
    footer.getBoundingClientRect = () =>
      ({ left: 10, top: 700, right: 202, bottom: 880, width: 192, height: 180 }) as DOMRect;

    await user.click(trigger);

    const wrapper = document.querySelector<HTMLElement>("[data-sidebar-popover]");
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveClass("fixed");
    expect(wrapper?.style.left).toBe("14px");
    expect(wrapper?.style.bottom).toBe(`${window.innerHeight - 700 + 10}px`);
    expect(wrapper?.style.getPropertyValue("--sidebar-popover-max-h")).toBe("674px");
    const panel = screen.getByRole("region", { name: "Platform help" });
    expect(panel.className).not.toMatch(/\babsolute\b/);
    expect(wrapper).toContainElement(panel);
  });

  it("keeps only one footer panel open at a time", async () => {
    const user = userEvent.setup();
    renderFooter();

    await user.click(screen.getByRole("button", { name: "Open platform help" }));
    expect(screen.getByRole("button", { name: "Open platform help" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    await user.click(screen.getByRole("button", { name: "Open operator account" }));
    expect(screen.getByRole("button", { name: "Open platform help" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("marks the settings link current only on the settings route", () => {
    const { rerender } = renderFooter();
    expect(screen.getByRole("link", { name: strings.pages.settings.title })).not.toHaveAttribute(
      "aria-current",
    );

    rerender(
      <SidebarAccount
        identitySession={identity}
        identitySessionUnavailable={false}
        settingsActive
      />,
    );
    expect(screen.getByRole("link", { name: strings.pages.settings.title })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("marks the compact Settings shortcut current instead of hiding route context", () => {
    renderFooter({ settingsActive: true, variant: "compact" });

    const settings = screen.getByRole("link", { name: strings.pages.settings.title });
    expect(settings).toHaveAttribute("aria-current", "page");
    expect(settings).toHaveClass("icon-button-active");
  });
});
