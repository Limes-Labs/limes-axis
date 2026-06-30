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

    await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
    await expect(page.locator(".ops-page-subtitle")).toContainText("Ravenna Works");
    await expect(page.getByText("Live API", { exact: true })).toBeVisible();
    await expect(page.getByText("Evidence present", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Domain graph" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Human-gated flow" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
    await expect(page.getByText("Risk signals")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Persisted routing posture" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Feedback environment" })).toBeVisible();
    await expect(page.getByText("SME feedback demo", { exact: true })).toBeVisible();
    await expect(page.getByText("Enterprise evaluation walkthrough", { exact: true })).toBeVisible();
    await expect(page.getByText("governed artifacts")).toBeVisible();
    await expect(page.getByText("Approval gate")).toBeVisible();
    await expect(page.getByText("Local fallback overview records are disabled.")).toHaveCount(0);
    await expect(page.getByText("Operations API unavailable")).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("opens live platform utility panels without leaving the console", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();

    const topbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    expect(topbarHeight).toBeLessThanOrEqual(80);

    await page.getByRole("button", { name: "Open notifications" }).click();
    const notificationsPanel = page.locator('[aria-label="Notifications"]');
    await expect(notificationsPanel).toBeVisible();
    await expect(notificationsPanel.getByText("API required", { exact: true })).toHaveCount(0);
    await expect(notificationsPanel.locator(".topbar-popover-header")).toContainText("live");
    expect(await notificationsPanel.locator(".notification-row").count()).toBeGreaterThan(0);
    await expect(
      notificationsPanel.getByText("Connect an OIDC session to acknowledge notifications."),
    ).toBeVisible();
    await expect(notificationsPanel.getByRole("button", { name: "Ack" }).first()).toBeDisabled();
    await expect(page.getByRole("link", { name: "Open audit evidence" })).toHaveAttribute(
      "href",
      "/audit",
    );
    const notificationsTopbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    expect(notificationsTopbarHeight).toBe(topbarHeight);

    await page.getByRole("button", { name: "Open operator account" }).click();
    await expect(page.locator('[aria-label="Operator account"]')).toBeVisible();
    await expect(page.getByText("Public evaluation operator")).toBeVisible();
    await expect(page.getByText("no_authenticated_api_actor")).toBeVisible();
    await expect(page.getByText("No authenticated API actor is attached.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Connect session" })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("keeps the enterprise navigation stable while the live dashboard scrolls", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();

    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    const navigation = await page.evaluate(() => {
      const element = document.querySelector<HTMLElement>("[data-console-sidebar]");
      const topnav = document.querySelector<HTMLElement>(".topnav");
      const viewportWidth = window.innerWidth;

      if (!element) {
        return null;
      }

      const rect = element.getBoundingClientRect();
      return {
        bottom: Math.round(rect.bottom),
        display: window.getComputedStyle(element).display,
        height: Math.round(rect.height),
        navVisible: element.textContent?.includes("Connectors") ?? false,
        top: Math.round(rect.top),
        topnavVisible: topnav ? window.getComputedStyle(topnav).display !== "none" : false,
        viewportHeight: window.innerHeight,
        viewportWidth,
      };
    });

    expect(navigation).not.toBeNull();

    if ((navigation?.viewportWidth ?? 0) <= 920) {
      expect(navigation?.display).toBe("none");
      expect(navigation?.topnavVisible).toBe(true);
      return;
    }

    expect(navigation?.display).not.toBe("none");
    expect(navigation?.top).toBe(0);
    expect(navigation?.bottom).toBe(navigation?.viewportHeight);
    expect(navigation?.height).toBe(navigation?.viewportHeight);
    expect(navigation?.navVisible).toBe(true);
  });
});
