import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TenantRecord } from "@/lib/platform-tenants";

const mocks = vi.hoisted(() => ({
  fetchTenantDetail: vi.fn(),
}));

vi.mock("@/lib/platform-tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/platform-tenants")>()),
  fetchTenantDetail: mocks.fetchTenantDetail,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({ refreshNonce: 0 }),
}));

// The lifecycle, usage, quota and vocabulary panels own their own queries.
vi.mock("@/components/tenant-lifecycle-actions", () => ({ TenantLifecycleActions: () => null }));
vi.mock("@/components/tenant-usage-panel", () => ({ TenantUsagePanel: () => null }));
vi.mock("@/components/tenant-quota-editor", () => ({ TenantQuotaEditor: () => null }));
vi.mock("@/components/tenant-vocabulary-editor", () => ({ TenantVocabularyEditor: () => null }));

import { TenantDetail } from "./tenant-detail";

const tenant: TenantRecord = {
  tenant_id: "tenant_acme_plant",
  display_name: "Acme Plant",
  description: "Pilot plant.",
  status: "active",
  created_by: "platform-admin",
  bootstrap_admin_actor_id: null,
  audit_event_id: null,
  audit_event_type: "tenant.provisioned",
  created_at: "2026-10-01T09:00:00Z",
  updated_at: "2026-10-01T09:00:00Z",
};

describe("TenantDetail", () => {
  it.each([null, "None", "null", "undefined"])(
    "shows 'Not recorded' instead of a literal missing value for bootstrap admin %s",
    async (bootstrapAdmin) => {
      mocks.fetchTenantDetail.mockResolvedValue({
        kind: "found",
        record: { ...tenant, bootstrap_admin_actor_id: bootstrapAdmin },
      });
      render(<TenantDetail tenantId="tenant_acme_plant" />);

      expect(await screen.findByRole("heading", { name: "Acme Plant" })).toBeInTheDocument();
      expect(document.querySelector("[data-bootstrap-admin-missing]")).toHaveTextContent(
        "Not recorded",
      );
      expect(document.body.textContent).not.toMatch(/\b(None|null|undefined)\b/);
    },
  );
});
