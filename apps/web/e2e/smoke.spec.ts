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
});
