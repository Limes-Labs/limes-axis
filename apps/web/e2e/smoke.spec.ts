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

  test("keeps navigation and autonomy levels usable on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    await page.getByRole("link", { name: "Agents" }).first().click();

    await expect(
      page.getByRole("heading", { name: "Autonomy and action registry" }),
    ).toBeVisible();
    await expect(page.getByRole("cell", { name: "L0" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "L4" })).toBeVisible();

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

    await expectNoHorizontalOverflow(page);
  });

  test("renders the approval inbox with local decision preview", async ({ page }) => {
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
    await expect(page.getByText("approved_preview")).toBeVisible();

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });
});
