import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  identitySession: null as null | {
    data: Record<string, unknown> | null;
    source: "loading" | "api" | "unavailable";
  },
  useAxisQuery: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/approvals",
}));

vi.mock("@/lib/use-identity-session", () => ({
  useIdentitySession: () => mocks.identitySession,
  startIdentitySessionHeartbeat: () => () => {},
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

// The gate test cares about shell gating, not chrome internals.
vi.mock("@/components/mobile-navigation", () => ({
  MobileNavigation: () => null,
}));
vi.mock("@/components/sidebar-account", () => ({
  SidebarAccount: () => null,
}));
vi.mock("@/providers/tenant-vocabulary-provider", async (importOriginal) => ({
  ...(await importOriginal<
    typeof import("@/providers/tenant-vocabulary-provider")
  >()),
  TenantVocabularyProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { AppShell } from "./app-shell";

function sessionFixture(overrides: Record<string, unknown> = {}) {
  return {
    authenticated: false,
    mode: "public_evaluation",
    actor_id: null,
    tenant_id: null,
    scopes: [],
    expires_at: null,
    api_auth_required: false,
    enterprise_sso_ready: false,
    readiness_status: "ready",
    issuer: "",
    audience: "",
    jwks_source: "disabled",
    session_boundary: "no_authenticated_api_actor",
    capabilities: [],
    limitations: [],
    notes: [],
    unauthenticated_reason: null,
    ...overrides,
  };
}

function Probe() {
  return <div data-testid="probe">tenant surface mounted</div>;
}

function renderShell() {
  return render(
    <AppShell>
      <Probe />
    </AppShell>,
  );
}

beforeEach(() => {
  mocks.useAxisQuery.mockReset();
  mocks.useAxisQuery.mockReturnValue({ data: null, source: "loading" });
});

describe("AppShell enforced-SSO gate", () => {
  it("mounts no tenant surface while auth is required and no session verified", () => {
    mocks.identitySession = {
      data: sessionFixture({
        api_auth_required: true,
        issuer: "https://idp.example.com/realms/axis",
        unauthenticated_reason: "expired_session_cookie",
      }),
      source: "api",
    };

    renderShell();

    expect(screen.getByLabelText("Sign in to Limes Axis")).toBeInTheDocument();
    expect(screen.queryByTestId("probe")).not.toBeInTheDocument();
    expect(screen.getByRole("status").textContent).toContain("session expired");
  });

  it("renders surfaces in public demo mode without a gate", () => {
    mocks.identitySession = { data: sessionFixture(), source: "api" };

    renderShell();

    expect(screen.getByTestId("probe")).toBeInTheDocument();
    expect(screen.queryByLabelText("Sign in to Limes Axis")).not.toBeInTheDocument();
  });

  it("renders surfaces for an authenticated operator", () => {
    mocks.identitySession = {
      data: sessionFixture({
        authenticated: true,
        mode: "secure_oidc_cookie",
        actor_id: "plant-operations-owner-role",
        tenant_id: "tenant_demo_manufacturing",
        api_auth_required: true,
      }),
      source: "api",
    };

    renderShell();

    expect(screen.getByTestId("probe")).toBeInTheDocument();
    expect(screen.queryByLabelText("Sign in to Limes Axis")).not.toBeInTheDocument();
  });

  it("keeps the pre-existing surface behavior while identity is loading or unavailable", () => {
    mocks.identitySession = { data: null, source: "loading" };
    const { unmount } = renderShell();
    expect(screen.getByTestId("probe")).toBeInTheDocument();
    unmount();

    mocks.identitySession = { data: null, source: "unavailable" };
    renderShell();
    expect(screen.getByTestId("probe")).toBeInTheDocument();
    expect(screen.queryByLabelText("Sign in to Limes Axis")).not.toBeInTheDocument();
  });
});

describe("AppShell sidebar navigation overflow", () => {
  it("cues hidden nav items below the fold and above once scrolled", () => {
    mocks.identitySession = { data: sessionFixture(), source: "api" };
    renderShell();

    const nav = screen.getByRole("navigation", { name: "Axis sections" });
    const frame = nav.parentElement as HTMLElement;
    Object.defineProperty(nav, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(nav, "scrollHeight", { configurable: true, value: 700 });

    fireEvent.scroll(nav);
    expect(frame).toHaveAttribute("data-nav-overflow-below");
    expect(frame).not.toHaveAttribute("data-nav-overflow-above");

    nav.scrollTop = 300;
    fireEvent.scroll(nav);
    expect(frame).toHaveAttribute("data-nav-overflow-above");
    expect(frame).not.toHaveAttribute("data-nav-overflow-below");
    // Every rail item stays in the DOM and reachable; only the cue changes.
    expect(screen.getByRole("link", { name: /Tenants/ })).toBeInTheDocument();
  });

  it("scrolls the current section into the rail's view", () => {
    const scrollIntoView = vi.fn();
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    try {
      mocks.identitySession = { data: sessionFixture(), source: "api" };
      renderShell();

      const nav = screen.getByRole("navigation", { name: "Axis sections" });
      const current = nav.querySelector("[aria-current='page']");
      expect(current).toHaveAttribute("href", "/approvals");
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
      expect(scrollIntoView.mock.contexts).toContain(current);
    } finally {
      Element.prototype.scrollIntoView = original;
    }
  });
});
