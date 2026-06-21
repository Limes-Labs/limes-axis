import { expect, test, type Page } from "@playwright/test";

async function expectNoHorizontalOverflow(page: Page) {
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );

  expect(hasOverflow).toBe(false);
}

test.describe("Axis console smoke", () => {
  test("loads the overview with API status fallback", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Operations control plane" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ravenna Works" })).toBeVisible();
    await expect(page.getByText("Plant Operations Cockpit")).toBeVisible();
    await expect(page.getByText("Supplier Delay Review")).toBeVisible();
    await expect(page.getByText("Fallback demo seed")).toBeVisible();
    await expect(page.getByText("API Status")).toBeVisible();
    await expect(page.getByText("Control API")).toBeVisible();
    await expect(page.getByText("Unavailable")).toBeVisible();
    await expect(page.getByText("http://localhost:8000")).toBeVisible();

    await page.getByRole("button", { name: "Refresh state" }).click();
    await expect(page.getByText("Unavailable")).toBeVisible();

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("keeps navigation and agent registry usable on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const mobileNav = page.locator(".topnav");
    await expect(mobileNav).toBeVisible();
    await mobileNav.getByRole("link", { name: "Agents" }).click();
    await expect(page).toHaveURL(/\/agents$/);

    await expect(
      page.getByRole("heading", { name: "Autonomy and action registry" }),
    ).toBeVisible();
    await expect(page.getByText("Fallback agent seed")).toBeVisible();
    await expect(page.getByRole("button", { name: /Supply Risk Agent/ })).toBeVisible();

    await page.getByLabel("Domain").first().selectOption("Supply");

    await expect(page.getByRole("heading", { name: "1 visible" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Supply Risk Agent" })).toBeVisible();
    await expect(page.getByText("approvals:supply:request").first()).toBeVisible();
    await expect(page.getByText("appr_expedite_supplier_batch", { exact: true }).first())
      .toBeVisible();
    await expect(page.getByText("no-external-egress")).toBeVisible();
    await expect(page.getByText("Fallback action seed")).toBeVisible();

    await page.getByLabel("Risk").selectOption("high");
    await page.getByRole("button", { name: /Request supplier expedite/ }).click();

    await expect(page.getByRole("heading", { name: "Request supplier expedite" })).toBeVisible();
    await expect(page.getByText("supplier_batch_id: string (required)")).toBeVisible();
    await expect(page.getByText("Approval Gated Dry Run")).toBeVisible();
    await expect(page.getByText("approvals:supply:request").first()).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });

  test("renders the read-only ontology explorer", async ({ page }) => {
    await page.goto("/ontology");

    await expect(page.getByRole("heading", { name: "Operational knowledge model" })).toBeVisible();
    await expect(page.getByText("Fallback ontology seed")).toBeVisible();
    await expect(page.getByRole("row", { name: "Line 2 Packaging Packaging" })).toBeVisible();
    await expect(
      page.getByRole("row", { name: "requires_approval Workflow cannot execute" }),
    ).toBeVisible();
    expect(await page.getByRole("cell", { name: "operations:read" }).count()).toBeGreaterThan(0);

    await page.getByRole("link", { name: "Line 2 Packaging" }).click();
    await expect(page).toHaveURL(/\/ontology\/asset_line_2_packaging$/);

    await expect(page.getByRole("heading", { name: "Entity detail" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Line 2 Packaging" })).toBeVisible();
    await expect(page.getByText("Fallback entity seed")).toBeVisible();
    await expect(page.getByText("supplier delay risk relationship")).toBeVisible();
    await expect(page.getByText("risk_supplier_delay").first()).toBeVisible();
    await expect(page.getByText("supply:read").first()).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });

  test("renders model routing and cost observability", async ({ page }) => {
    await page.goto("/model-routing");

    await expect(page.getByRole("heading", { name: "Model routing and spend" })).toBeVisible();
    await expect(page.getByText("Fallback routing seed")).toBeVisible();
    await expect(page.getByRole("button", { name: /Quality Risk Agent/ })).toBeVisible();
    await expect(page.getByText("EUR 0.76").first()).toBeVisible();

    await page.getByLabel("Decision").selectOption("blocked_by_default");

    await expect(page.getByRole("heading", { name: "1 visible" })).toBeVisible();
    await page.getByRole("button", { name: /Quality Risk Agent/ }).click();

    await expect(page.getByRole("heading", { name: "Quality Risk Agent" })).toBeVisible();
    await expect(page.getByText("model.egress.blocked")).toBeVisible();
    await expect(page.getByText("audit_20260621_133900_egress_blocked").first()).toBeVisible();
    await expect(page.getByText("no-external-egress").first()).toBeVisible();
    await expect(page.getByText("EUR 0.00").first()).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });

  test("renders the approval inbox with persisted decision fallback", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/approvals");

    await expect(page.getByRole("heading", { name: "Policy gate queue" })).toBeVisible();
    await expect(page.getByText("Fallback approval seed")).toBeVisible();
    await expect(page.getByRole("button", { name: /Expedite supplier batch/ })).toBeVisible();

    await page.getByRole("button", { name: /Place Batch Q-1842 on quality hold/ }).click();

    await expect(page.getByRole("heading", { name: "Place Batch Q-1842 on quality hold" }))
      .toBeVisible();
    await expect(page.getByText("approvals:quality:decide")).toBeVisible();

    await page.getByRole("button", { name: "Approve" }).click();

    await expect(page.getByRole("heading", { name: "Approved" })).toBeVisible();
    await expect(page.getByText("Local preview", { exact: true })).toBeVisible();
    await expect(page.getByText("approved_preview")).toBeVisible();
    await expect(page.getByText("Local preview only; API persistence is unavailable."))
      .toBeVisible();

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("renders the read-only workflow console", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/workflows");

    await expect(page.getByRole("heading", { name: "Runtime adapter track" })).toBeVisible();
    await expect(page.getByText("Fallback workflow seed")).toBeVisible();
    await expect(page.getByRole("button", { name: /Supplier Delay Review/ })).toBeVisible();
    await expect(page.getByText("axis-temporal-adapter", { exact: true })).toBeVisible();
    await expect(page.getByText("approval.decision")).toBeVisible();

    await page.getByRole("button", { name: /Maintenance Reschedule/ }).click();

    await expect(page.getByRole("heading", { name: "Maintenance Reschedule" })).toBeVisible();
    await expect(page.getByText("maintenance.owner.review")).toBeVisible();
    await expect(page.getByText("service-window-policy")).toBeVisible();
    await expect(page.getByText("Replay preview only")).toBeVisible();

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("renders the read-only audit explorer with filters", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/audit");

    await expect(page.getByRole("heading", { name: "Append-only evidence" })).toBeVisible();
    await expect(page.getByText("Fallback audit seed")).toBeVisible();
    await expect(page.getByRole("button", { name: /workflow.started/ })).toBeVisible();
    await page.getByLabel("Tenant").selectOption("tenant_demo_manufacturing");
    await expect(page.getByLabel("Tenant")).toHaveValue("tenant_demo_manufacturing");

    await page.getByLabel("Event").selectOption("policy.egress.blocked");

    await expect(page.getByRole("heading", { name: "1 visible" })).toBeVisible();
    await expect(page.getByRole("button", { name: /policy.egress.blocked/ })).toBeVisible();
    await expect(page.getByText("blocked_by_default").first()).toBeVisible();
    await expect(page.getByText("no-external-egress")).toBeVisible();

    await page.getByRole("button", { name: "Reset filters" }).click();

    await expect(page.getByRole("heading", { name: "9 visible" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });
});
