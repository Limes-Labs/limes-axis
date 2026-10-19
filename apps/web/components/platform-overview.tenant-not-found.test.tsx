import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";

/*
 * Regression for #945: the empty-tenant onboarding never rendered because the
 * overview only recognised `source: "unavailable"`, while the real query hook
 * classifies the API's `TENANT_NOT_FOUND` 404 as `tenant_not_found`. This
 * suite deliberately runs the real useAxisQuery and useIdentitySession so the
 * classification under test is the production one, fed the API's real body.
 */

const mocks = vi.hoisted(() => ({
  axisFetchParsedJson: vi.fn(),
}));

vi.mock("@/lib/axis-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/axis-api")>()),
  axisFetchParsedJson: mocks.axisFetchParsedJson,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null, hydrated: true }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    apiBaseUrl: "http://localhost:8000",
    apiStatus: { state: "online", label: "Online", detail: "" },
    refreshNonce: 0,
    triggerRefresh: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import { PlatformOverview } from "./platform-overview";
import { identitySessionFixture, policyRegistryFixture } from "./overview/overview-fixtures";
import { AxisApiError } from "@/lib/axis-api";
import { resetIdentitySessionStore } from "@/lib/use-identity-session";

function tenantNotFound(path: string) {
  // The exact body `manufacturing_tenant_not_found_handler` sends.
  return new AxisApiError(path, 404, {
    body: {
      detail: {
        code: "TENANT_NOT_FOUND",
        message: "The manufacturing tenant is unknown.",
        tenant_id: "tenant_demo_manufacturing",
      },
    },
    requestId: "req-tenant-not-found",
  });
}

beforeEach(() => {
  resetIdentitySessionStore();
  mocks.axisFetchParsedJson.mockReset();
  mocks.axisFetchParsedJson.mockImplementation(async (path: string) => {
    if (path === "/identity/session") {
      return identitySessionFixture;
    }
    if (path.startsWith("/platform/policies")) {
      return { ...policyRegistryFixture, policy_count: 0, active_policy_count: 0 };
    }
    throw tenantNotFound(path);
  });
});

describe("PlatformOverview on a tenant the API has never bootstrapped", () => {
  it("renders guided setup instead of error panels for TENANT_NOT_FOUND", async () => {
    render(
      <ToastProvider>
        <PlatformOverview />
      </ToastProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Set up your governed platform" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Operations data could not be loaded" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/API unavailable/)).not.toBeInTheDocument();
  });
});
