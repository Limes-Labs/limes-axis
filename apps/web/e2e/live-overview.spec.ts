import { expect, test, type Page } from "@playwright/test";

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const root = document.documentElement;
    const clientWidth = root.clientWidth;
    const offenders = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          className: element.className.toString(),
          left: Math.floor(rect.left),
          right: Math.ceil(rect.right),
          tagName: element.tagName.toLowerCase(),
          text: element.textContent?.trim().replace(/\s+/g, " ").slice(0, 90) ?? "",
          width: Math.ceil(rect.width),
        };
      })
      .filter((entry) => entry.right > clientWidth || entry.left < 0 || entry.width > clientWidth)
      .slice(0, 8);

    return {
      clientWidth,
      hasOverflow: root.scrollWidth > clientWidth,
      offenders,
      scrollWidth: root.scrollWidth,
    };
  });

  expect(overflow.hasOverflow, JSON.stringify(overflow, null, 2)).toBe(false);
}

test.describe("Axis live overview demo", () => {
  test.skip(
    process.env.AXIS_E2E_LIVE_API !== "1",
    "Set AXIS_E2E_LIVE_API=1 when the local Axis API is running.",
  );

  test("renders the persisted operations snapshot on the overview page", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Ravenna Works" })).toBeVisible();
    await expect(page.getByText("API-backed control plane")).toBeVisible();
    await expect(
      page.locator(".overview-meta").getByText("Operations snapshot", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Persisted plant state" })).toBeVisible();
    await expect(page.getByText("Generated Artifacts")).toBeVisible();
    await expect(page.getByText("Pending Gates")).toBeVisible();
    await expect(page.getByText("Local fallback overview records are disabled.")).toHaveCount(0);
    await expect(page.getByText("Overview API unavailable")).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });
});
