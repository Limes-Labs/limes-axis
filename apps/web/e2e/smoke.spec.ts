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

async function expectAxisDarkShell(page: Page) {
  const shell = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    const brandDiamond = document.querySelector<HTMLElement>(".brand-diamond");

    return {
      axisBlack: root.getPropertyValue("--axis-black").trim(),
      colorScheme: root.colorScheme,
      signalBlue: root.getPropertyValue("--signal-blue").trim(),
      brandDiamondColor: brandDiamond ? getComputedStyle(brandDiamond).backgroundColor : null,
    };
  });

  expect(shell).toEqual({
    axisBlack: "#070b10",
    colorScheme: "dark",
    signalBlue: "#3e6bff",
    brandDiamondColor: "rgb(62, 107, 255)",
  });
}

test.describe("Axis console smoke", () => {
  test("requires the overview API instead of local overview data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Operations API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback overview records are disabled.")).toBeVisible();
    await expect(page.getByText("/demo/manufacturing/overview")).toBeVisible();
    await expect(page.getByText("/demo/manufacturing/model-routing")).toBeVisible();
    await expect(page.getByText("Fallback demo seed")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Ravenna Works" })).toHaveCount(0);
    await expect(page.getByText("Live API")).toHaveCount(0);
    await expect(page.getByText("API unavailable", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Refresh state" }).click();
    await expect(page.getByText("API unavailable", { exact: true })).toBeVisible();

    await expectAxisDarkShell(page);
    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("keeps shell utilities actionable without mock controls", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("button", { name: "Open notifications" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open platform help" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open operator account" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Connect OIDC bearer token" })).toHaveCount(0);

    await page.getByRole("button", { name: "Search console" }).click();
    await expect(page.getByRole("dialog", { name: "Console command menu" })).toBeVisible();
    await page.getByLabel("Search console commands").fill("audit");
    await expect(page.getByRole("link", { name: /Open audit stream/ })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Console command menu" })).toHaveCount(0);

    const topbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    expect(topbarHeight).toBeLessThanOrEqual(80);

    await page.getByRole("button", { name: "Open notifications" }).click();
    const notificationsPanel = page.locator('[aria-label="Notifications"]');
    await expect(notificationsPanel).toBeVisible();
    await expect(notificationsPanel.getByText("API required", { exact: true })).toBeVisible();
    const notificationsTopbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    expect(notificationsTopbarHeight).toBe(topbarHeight);
    await page.keyboard.press("Escape");
    await expect(page.locator('[aria-label="Notifications"]')).toHaveCount(0);

    await page.getByRole("button", { name: "Open platform help" }).click();
    await expect(page.locator('[aria-label="Platform help"]')).toBeVisible();
    await expect(page.getByRole("link", { name: /Architecture docs/ })).toHaveAttribute(
      "href",
      "https://github.com/Limes-Labs/limes-axis/blob/main/docs/architecture.md",
    );
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: "Open operator account" }).click();
    await expect(page.locator('[aria-label="Operator account"]')).toBeVisible();
    await expect(page.getByRole("button", { name: "Connect session" })).toBeVisible();
    const accountTopbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    expect(accountTopbarHeight).toBe(topbarHeight);

    await expect(page.getByRole("combobox", { name: "Environment" })).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: "Evidence window" })).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
  });

  test("keeps navigation and requires agent/action APIs on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    const mobileNav = page.locator(".topnav");
    await expect(mobileNav).toBeVisible();
    await expect(mobileNav.getByRole("link", { name: "Agents" })).toHaveAttribute(
      "href",
      "/agents",
    );
    await page.goto("/agents");

    await expect(
      page.getByRole("heading", { name: "Autonomy and action registry" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Agent API unavailable" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Action API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback agent records are disabled.")).toBeVisible();
    await expect(page.getByText("Local fallback action records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback agent seed")).toHaveCount(0);
    await expect(page.getByText("Fallback action seed")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Supply Risk Agent/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Request supplier expedite/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
  });

  test("requires the ontology APIs instead of local graph data", async ({ page }) => {
    await page.goto("/ontology");

    await expect(page.getByRole("heading", { name: "Operational knowledge model" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ontology API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback ontology records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback ontology seed")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Line 2 Packaging" })).toHaveCount(0);

    await page.goto("/ontology/asset_line_2_packaging");

    await expect(page.getByRole("heading", { name: "Entity detail" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Entity API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback entity records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback entity seed")).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
  });

  test("requires the model routing API instead of local routing data", async ({ page }) => {
    await page.goto("/model-routing");

    await expect(page.getByRole("heading", { name: "Model routing and spend" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Routing API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback routing records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback routing seed")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Quality Risk Agent/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
  });

  test("requires the approval API instead of local approval decisions", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/approvals");

    await expect(page.getByRole("heading", { name: "Policy gate queue" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Approval API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback approval records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback approval seed")).toHaveCount(0);
    await expect(page.getByText("Local preview")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Expedite supplier batch/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("requires the workflow API instead of local workflow data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/workflows");

    await expect(page.getByRole("heading", { name: "Runtime adapter track" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflow API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback workflow records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback workflow seed")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Supplier Delay Review/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("requires the audit API instead of local audit data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/audit");

    await expect(page.getByRole("heading", { name: "Append-only evidence" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Audit API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback audit records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback audit seed")).toHaveCount(0);
    await expect(page.getByText("audit-export-local-seed")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /workflow.started/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("requires the replay API instead of local replay artifacts", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/simulation");

    await expect(page.getByRole("heading", { name: "Replay and simulation" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Replay API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback replay records are disabled.")).toBeVisible();
    await expect(page.getByText("Fallback replay seed")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Supplier Delay Review/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("requires the connector API instead of local connector fallback data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/connectors");

    await expect(page.getByRole("heading", { name: "Connector intake" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Connector API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback connector records are disabled.")).toBeVisible();
    await expect(page.getByText("API required")).toBeVisible();
    await expect(page.getByText("Fallback connector seed")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /Manufacturing assets CSV/ })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });
});
