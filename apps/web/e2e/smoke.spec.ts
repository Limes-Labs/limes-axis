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
    await expect(
      notificationsPanel.getByText("Live notification data requires `/demo/manufacturing/notifications`."),
    ).toBeVisible();
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
    await expect(page.getByText("Session API unavailable")).toBeVisible();
    await expect(
      page.getByText("The account panel needs `/identity/session` before it can display an API-verified actor."),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign in with SSO" })).toHaveAttribute(
      "href",
      "http://127.0.0.1:65534/identity/oidc/authorize?return_to=%2F",
    );
    await expect(page.getByRole("link", { name: "Open SSO setup" })).toHaveAttribute(
      "href",
      "http://127.0.0.1:65534/identity/oidc/onboarding",
    );
    await expect(page.getByRole("button", { name: "Connect bearer token" })).toBeVisible();
    const accountTopbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    expect(accountTopbarHeight).toBe(topbarHeight);

    await expect(page.getByRole("combobox", { name: "Environment" })).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: "Evidence window" })).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
  });

  test("routes verified cookie sessions through the real federated logout endpoint", async ({
    page,
  }) => {
    await page.route("http://127.0.0.1:65534/identity/session", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          authenticated: true,
          mode: "secure_oidc_cookie",
          actor_id: "plant-operations-owner-role",
          tenant_id: "tenant_demo_manufacturing",
          scopes: ["audit:read"],
          expires_at: 4102444800,
          api_auth_required: true,
          enterprise_sso_ready: true,
          readiness_status: "ready",
          issuer: "https://idp.example/realms/axis",
          audience: "limes-axis-api",
          jwks_source: "configured",
          session_boundary: "http_only_cookie_verified_by_axis_api",
          capabilities: ["Browser session verified by the Axis API."],
          limitations: [],
          notes: [],
        },
        status: 200,
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "Open operator account" }).click();

    await expect(page.locator('[aria-label="Operator account"]')).toBeVisible();
    await expect(page.getByText("plant-operations-owner-role")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Sign out with identity provider" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Open operator account" })).toHaveText("PO");

    const [logoutRequest] = await Promise.all([
      page.waitForRequest("http://127.0.0.1:65534/identity/oidc/logout?return_to=%2F"),
      page.getByRole("button", { name: "Sign out with identity provider" }).click(),
    ]);
    expect(logoutRequest.method()).toBe("GET");
  });

  test("keeps the desktop sidebar complete on short enterprise screens", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 420 });
    await page.goto("/");

    const sidebarState = await page.evaluate(() => {
      const sidebar = document.querySelector<HTMLElement>("[data-console-sidebar]");
      const nav = document.querySelector<HTMLElement>(".nav-list");
      const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".nav-list a")).map(
        (link) => link.textContent?.trim() ?? "",
      );

      return {
        links,
        nav: nav
          ? {
              clientHeight: nav.clientHeight,
              flexGrow: window.getComputedStyle(nav).flexGrow,
              overflowY: window.getComputedStyle(nav).overflowY,
              scrollHeight: nav.scrollHeight,
            }
          : null,
        sidebar: sidebar
          ? {
              clientHeight: sidebar.clientHeight,
              overflowY: window.getComputedStyle(sidebar).overflowY,
              scrollHeight: sidebar.scrollHeight,
            }
          : null,
        viewportHeight: window.innerHeight,
      };
    });

    expect(sidebarState.links).toEqual([
      "Operations",
      "Ontology",
      "Workflows",
      "Agents",
      "Models",
      "Approvals",
      "Policies",
      "Audit",
      "Simulation",
      "Connectors",
      "Tenants",
      "Settings",
    ]);
    expect(sidebarState.sidebar?.clientHeight).toBe(sidebarState.viewportHeight);
    expect(sidebarState.sidebar?.scrollHeight ?? 0).toBeLessThanOrEqual(
      (sidebarState.sidebar?.clientHeight ?? 0) + 1,
    );
    expect(sidebarState.nav?.flexGrow).toBe("1");
    expect(sidebarState.nav?.overflowY).toBe("auto");

    await page.locator(".nav-list").evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    await expect(page.getByRole("link", { name: "Connectors" })).toBeInViewport();
  });

  test("keeps topbar utility hitboxes and popovers stable", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 760 });
    await page.goto("/");

    const topbarHeight = await page.locator(".ops-topbar").evaluate((element) =>
      Math.round(element.getBoundingClientRect().height),
    );
    const utilityRects = await page
      .locator(".ops-toolbar-icons button")
      .evaluateAll((buttons) =>
        buttons.map((button) => {
          const rect = button.getBoundingClientRect();
          return {
            height: Math.round(rect.height),
            width: Math.round(rect.width),
          };
        }),
      );

    expect(utilityRects.length).toBeGreaterThanOrEqual(5);
    for (const rect of utilityRects) {
      expect(rect).toEqual({ height: 34, width: 34 });
    }

    const accountButton = page.getByRole("button", { name: "Open operator account" });
    const beforeAccountRect = await accountButton.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        height: Math.round(rect.height),
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
      };
    });

    await page.getByRole("button", { name: "Open notifications" }).click();
    await expect(page.locator('[aria-label="Notifications"]')).toBeVisible();
    await accountButton.click();
    await expect(page.locator('[aria-label="Operator account"]')).toBeVisible();
    await expect(page.locator('[aria-label="Notifications"]')).toHaveCount(0);

    const afterAccountRect = await accountButton.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        height: Math.round(rect.height),
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
      };
    });
    expect(afterAccountRect).toEqual(beforeAccountRect);

    const accountPopover = await page.locator('[aria-label="Operator account"]').evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        bottom: Math.round(rect.bottom),
        right: Math.round(rect.right),
        top: Math.round(rect.top),
      };
    });
    expect(accountPopover.top).toBeGreaterThanOrEqual(topbarHeight);
    expect(accountPopover.right).toBeLessThanOrEqual(1440 - 16);
    expect(accountPopover.bottom).toBeLessThanOrEqual(760 - 16);
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

  test("requires the platform policy API instead of local policy data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/");
    await expect(page.getByRole("link", { name: "Policies" }).first()).toHaveAttribute(
      "href",
      "/policies",
    );

    await page.goto("/policies");

    await expect(page.getByRole("heading", { name: "Platform policy rules" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Policy API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback policy records are disabled.")).toBeVisible();
    await expect(page.getByText("/platform/policies", { exact: true })).toBeVisible();
    await expect(page.getByText("Fallback policy seed")).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Deny critical actions/ })).toHaveCount(0);

    await expect(page.getByRole("form", { name: "Platform policy authoring" })).toHaveCount(0);

    await page.goto("/policies/deny_critical_actions");

    await expect(page.getByRole("heading", { name: "Policy detail" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Policy API unavailable" })).toBeVisible();
    await expect(page.getByText("/platform/policies/deny_critical_actions")).toBeVisible();
    await expect(page.getByRole("form", { name: "Policy dry-run evaluation" })).toHaveCount(0);
    await expect(page.getByRole("form", { name: "Platform policy revision" })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("authors a platform policy through the mocked policy API", async ({ context, page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await context.addCookies([
      { name: "axis_csrf", value: "csrf-e2e-token", url: "http://127.0.0.1:3100" },
    ]);

    const policyRecord = {
      tenant_id: "tenant_demo_manufacturing",
      policy_id: "deny_critical_actions",
      revision_number: 1,
      policy_version: "1.0.0",
      display_name: "Deny critical actions",
      description: "Blocks critical-risk action execution.",
      scope: "action_execution",
      effect: "deny",
      conditions: { risk_levels: ["critical"] },
      status: "active",
      notes: [],
      created_by: "platform-governance-owner-role",
      created_at: "2026-07-01T08:00:00Z",
      required_authoring_scope: "platform:policy:author",
      revises_revision_number: null,
      replaced_by_revision_number: null,
      revision_idempotency_key: null,
      idempotent_replay: false,
      audit_event_type: "platform.policy.authored",
      audit_event_id: null,
      permission_decision: { allowed: true, reason: "authoring_scope_present" },
    };

    const policyPosts: string[] = [];
    await page.route(
      (url) => url.href.startsWith("http://127.0.0.1:65534/platform/policies"),
      async (route) => {
        if (route.request().method() === "POST") {
          policyPosts.push(route.request().postData() ?? "");
          await route.fulfill({
            contentType: "application/json",
            json: {
              ...policyRecord,
              policy_id: "gate_high_spend",
              display_name: "Gate high spend",
              description: "Requires approval above the spend threshold.",
              effect: "require_approval",
              scope: "approval_requirement",
              conditions: { risk_levels: ["high"], requested_amount_at_least: 10000 },
            },
            status: 201,
          });
          return;
        }

        await route.fulfill({
          contentType: "application/json",
          json: {
            tenant_id: "tenant_demo_manufacturing",
            policy_count: 1,
            active_policy_count: 1,
            policies: [policyRecord],
            policy_notes: [],
          },
          status: 200,
        });
      },
    );

    await page.goto("/policies");

    const createForm = page.getByRole("form", { name: "Platform policy authoring" });
    await expect(createForm).toBeVisible();

    // Client-side validation blocks a policy id the API pattern rejects.
    await page.getByLabel("New policy id").fill("Bad Policy Id");
    await page.getByLabel("New policy display name").fill("Gate high spend");
    await page
      .getByLabel("New policy description")
      .fill("Requires approval above the spend threshold.");
    await createForm.getByRole("button", { name: "Author policy" }).click();
    await expect(
      page.getByText("Policy id must match ^[a-z0-9][a-z0-9_-]*$", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByText("Declare at least one condition", { exact: false }),
    ).toBeVisible();
    expect(policyPosts).toEqual([]);

    // A valid draft round-trips through the mocked create endpoint.
    await page.getByLabel("New policy id").fill("gate_high_spend");
    await page.getByLabel("New policy scope").selectOption("approval_requirement");
    await page.getByLabel("New policy effect").selectOption("require_approval");
    await page
      .getByRole("group", { name: "New policy risk levels" })
      .getByRole("button", { name: "high", exact: true })
      .click();
    await page.getByLabel("New policy amount threshold").fill("10000");

    const [createRequest] = await Promise.all([
      page.waitForRequest(
        (request) =>
          request.method() === "POST"
          && request.url() === "http://127.0.0.1:65534/platform/policies",
      ),
      createForm.getByRole("button", { name: "Author policy" }).click(),
    ]);
    expect(createRequest.headers()["x-axis-csrf-token"]).toBe("csrf-e2e-token");
    expect(createRequest.postDataJSON()).toEqual({
      tenant_id: "tenant_demo_manufacturing",
      policy_id: "gate_high_spend",
      policy_version: "1.0.0",
      display_name: "Gate high spend",
      description: "Requires approval above the spend threshold.",
      scope: "approval_requirement",
      effect: "require_approval",
      conditions: { risk_levels: ["high"], requested_amount_at_least: 10000 },
      created_by: "platform-governance-owner-role",
      actor_scopes: ["platform:policy:author"],
      notes: [],
    });

    await expect(page.getByText("Policy created as r1 / 1.0.0.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open gate_high_spend" })).toHaveAttribute(
      "href",
      "/policies/gate_high_spend",
    );

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("shows the revise form and revision compare on the mocked policy detail", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    const baseRecord = {
      tenant_id: "tenant_demo_manufacturing",
      policy_id: "deny_critical_actions",
      revision_number: 1,
      policy_version: "1.0.0",
      display_name: "Deny critical actions",
      description: "Blocks critical-risk action execution.",
      scope: "action_execution",
      effect: "require_approval",
      conditions: { risk_levels: ["high", "critical"] },
      status: "superseded",
      notes: [],
      created_by: "platform-governance-owner-role",
      created_at: "2026-07-01T08:00:00Z",
      required_authoring_scope: "platform:policy:author",
      revises_revision_number: null,
      replaced_by_revision_number: 2,
      revision_idempotency_key: null,
      idempotent_replay: false,
      audit_event_type: "platform.policy.authored",
      audit_event_id: null,
      permission_decision: { allowed: true, reason: "authoring_scope_present" },
    };
    const currentRecord = {
      ...baseRecord,
      revision_number: 2,
      policy_version: "1.1.0",
      effect: "deny",
      conditions: { risk_levels: ["critical"] },
      status: "active",
      revises_revision_number: 1,
      replaced_by_revision_number: null,
      revision_idempotency_key: "idem-key-1",
      required_authoring_scope: "platform:policy:revise",
      audit_event_type: "platform.policy.revised",
    };

    await page.route(
      "http://127.0.0.1:65534/platform/policies/deny_critical_actions",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          json: {
            tenant_id: "tenant_demo_manufacturing",
            policy_id: "deny_critical_actions",
            current_revision: currentRecord,
            revisions: [baseRecord, currentRecord],
          },
          status: 200,
        });
      },
    );

    await page.goto("/policies/deny_critical_actions");

    await expect(page.getByRole("heading", { name: "Deny critical actions" })).toBeVisible();

    // Revise form is pre-filled from the current revision with a
    // client-generated idempotency key.
    const reviseForm = page.getByRole("form", { name: "Platform policy revision" });
    await expect(reviseForm).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Append a revision to r2" }),
    ).toBeVisible();
    await expect(page.getByText(/Idempotency key [0-9a-f-]{36}/)).toBeVisible();
    await expect(page.getByLabel("Revision policy version")).toHaveValue("1.1.0");
    await expect(page.getByLabel("Revision display name")).toHaveValue("Deny critical actions");
    await expect(
      page
        .getByRole("group", { name: "Revision risk levels" })
        .getByRole("button", { name: "critical", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");

    // Revision compare renders a field-level diff against the current revision.
    await page.getByLabel("Revision to compare").selectOption("1");
    await expect(page.getByText("Comparing r1 / 1.0.0 against the current r2 / 1.1.0")).toBeVisible();
    await expect(page.getByText("Require approval → Deny")).toBeVisible();
    await expect(page.getByText("− high")).toBeVisible();

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

  test("requires the identity session APIs on the sessions view", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/settings/sessions");

    await expect(page.getByRole("heading", { name: "Session security" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Session API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback session records are disabled.")).toBeVisible();
    await expect(page.getByText("/identity/session /identity/sessions")).toBeVisible();
    await expect(page.getByRole("button", { name: "Revoke" })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("lists browser sessions and revokes with the CSRF double-submit header", async ({
    context,
    page,
  }) => {
    await context.addCookies([
      { name: "axis_csrf", value: "csrf-e2e-token", url: "http://127.0.0.1:3100" },
    ]);

    await page.route("http://127.0.0.1:65534/identity/session", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          authenticated: true,
          mode: "secure_oidc_cookie",
          actor_id: "plant-operations-owner-role",
          tenant_id: "tenant_demo_manufacturing",
          scopes: ["audit:read", "identity:sessions:admin"],
          expires_at: 4102444800,
          api_auth_required: true,
          enterprise_sso_ready: true,
          readiness_status: "ready",
          issuer: "https://idp.example/realms/axis",
          audience: "limes-axis-api",
          jwks_source: "configured",
          session_boundary: "http_only_cookie_verified_by_axis_api",
          capabilities: ["Browser session verified by the Axis API."],
          limitations: [],
          notes: [],
        },
        status: 200,
      });
    });
    await page.route("http://127.0.0.1:65534/identity/sessions*", async (route) => {
      const tenantWide = route.request().url().includes("tenant_wide=true");
      await route.fulfill({
        contentType: "application/json",
        json: {
          tenant_id: "tenant_demo_manufacturing",
          actor_id: "plant-operations-owner-role",
          tenant_wide: tenantWide,
          sessions: [
            {
              session_ref: "0b6a4e52-93d4-4f5f-8f2a-2f24c9b7a101",
              actor_id: "plant-operations-owner-role",
              status: "active",
              current: true,
              created_at: "2026-07-07T08:00:00Z",
              expires_at: "2026-07-07T16:00:00Z",
              absolute_expires_at: "2026-07-07T16:00:00Z",
              last_seen_at: "2026-07-07T09:30:00Z",
              refresh_count: 3,
              revoked_at: null,
              revocation_reason: null,
            },
            {
              session_ref: "9c1f2ad4-7a75-4d0e-b1de-6d9d0c4be202",
              actor_id: tenantWide ? "quality-auditor-role" : "plant-operations-owner-role",
              status: "active",
              current: false,
              created_at: "2026-07-06T18:00:00Z",
              expires_at: "2026-07-07T02:00:00Z",
              absolute_expires_at: null,
              last_seen_at: null,
              refresh_count: 0,
              revoked_at: null,
              revocation_reason: null,
            },
            {
              session_ref: "5d2e6bc8-1f9b-45b6-9f5c-0a8f2f6de303",
              actor_id: "plant-operations-owner-role",
              status: "revoked",
              current: false,
              created_at: "2026-07-05T18:00:00Z",
              expires_at: "2026-07-06T02:00:00Z",
              absolute_expires_at: null,
              last_seen_at: "2026-07-05T19:00:00Z",
              refresh_count: 1,
              revoked_at: "2026-07-05T20:00:00Z",
              revocation_reason: "idle_timeout",
            },
          ],
          notes: ["Session references are opaque identifiers; no token material is returned."],
        },
        status: 200,
      });
    });
    await page.route(
      "http://127.0.0.1:65534/identity/sessions/9c1f2ad4-7a75-4d0e-b1de-6d9d0c4be202/revoke",
      async (route) => {
        await route.fulfill({ status: 204 });
      },
    );

    await page.goto("/settings/sessions");

    await expect(page.getByRole("heading", { name: "Session security" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Your sessions" })).toBeVisible();
    await expect(page.getByText("3 recorded")).toBeVisible();
    await expect(page.getByText("(this browser)")).toBeVisible();
    await expect(page.getByText("Current", { exact: true })).toBeVisible();
    await expect(page.getByText("Revoked", { exact: true })).toBeVisible();
    await expect(page.getByText("idle timeout")).toBeVisible();
    await expect(page.getByRole("button", { name: "Revoke", exact: true })).toHaveCount(1);

    const signOutLinks = page.getByRole("link", { name: "Sign out" });
    await expect(signOutLinks).toHaveCount(2);
    await expect(signOutLinks.first()).toHaveAttribute(
      "href",
      "http://127.0.0.1:65534/identity/oidc/logout?return_to=%2Fsettings%2Fsessions",
    );

    const [revokeRequest] = await Promise.all([
      page.waitForRequest(
        "http://127.0.0.1:65534/identity/sessions/9c1f2ad4-7a75-4d0e-b1de-6d9d0c4be202/revoke",
      ),
      page.getByRole("button", { name: "Revoke", exact: true }).click(),
    ]);
    expect(revokeRequest.method()).toBe("POST");
    expect(revokeRequest.headers()["x-axis-csrf-token"]).toBe("csrf-e2e-token");

    await page.getByRole("button", { name: "Show tenant sessions" }).click();
    await expect(page.getByRole("heading", { name: "Tenant-wide sessions" })).toBeVisible();
    await expect(page.getByText("quality-auditor-role")).toBeVisible();

    await expectNoHorizontalOverflow(page);
  });

  test("requires the platform tenant API instead of local tenant data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/");
    await expect(page.getByRole("link", { name: "Tenants" }).first()).toHaveAttribute(
      "href",
      "/tenants",
    );

    await page.goto("/tenants");

    await expect(page.getByRole("heading", { name: "Tenant operations" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tenant API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback tenant records are disabled.")).toBeVisible();
    await expect(page.getByText("/platform/tenants", { exact: true })).toBeVisible();
    await expect(page.getByRole("form", { name: "Tenant provisioning" })).toHaveCount(0);

    await page.goto("/tenants/tenant_acme");

    await expect(page.getByRole("heading", { name: "Tenant detail" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tenant API unavailable" })).toBeVisible();
    await expect(page.getByText("/platform/tenants/tenant_acme", { exact: true })).toBeVisible();
    await expect(page.getByRole("form", { name: "Suspend tenant" })).toHaveCount(0);
    await expect(page.getByRole("form", { name: "Tenant quota update" })).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("provisions a tenant and suspends it through the mocked tenant API", async ({
    context,
    page,
  }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await context.addCookies([
      { name: "axis_csrf", value: "csrf-e2e-token", url: "http://127.0.0.1:3100" },
    ]);

    const tenantRecord = {
      tenant_id: "tenant_acme",
      display_name: "Acme Manufacturing",
      description: "Reference tenant.",
      status: "active",
      created_by: "platform-tenant-operator-role",
      bootstrap_admin_actor_id: null,
      provision_idempotency_key: "idem-key-1",
      suspended_at: null,
      suspended_by: null,
      suspension_reason: null,
      reactivated_at: null,
      reactivated_by: null,
      permission_decision: { allowed: true, reason: "operator_scope_present" },
      audit_event_id: "11111111-1111-4111-8111-111111111111",
      audit_event_type: "platform.tenant.provisioned",
      idempotent_replay: false,
      notes: [],
      created_at: "2026-07-01T08:00:00Z",
      updated_at: "2026-07-01T08:00:00Z",
    };

    const tenantPosts: string[] = [];
    // Registry list + provision POST live on the same base path.
    await page.route(
      (url) =>
        url.href === "http://127.0.0.1:65534/platform/tenants"
        || url.href.startsWith("http://127.0.0.1:65534/platform/tenants?"),
      async (route) => {
        if (route.request().method() === "POST") {
          tenantPosts.push(route.request().postData() ?? "");
          await route.fulfill({ contentType: "application/json", json: tenantRecord, status: 201 });
          return;
        }

        await route.fulfill({
          contentType: "application/json",
          json: {
            tenant_count: 1,
            active_tenant_count: 1,
            tenants: [tenantRecord],
            tenant_notes: [],
          },
          status: 200,
        });
      },
    );

    const [listRequest] = await Promise.all([
      page.waitForRequest(
        (request) =>
          request.method() === "GET"
          && request.url().startsWith("http://127.0.0.1:65534/platform/tenants"),
      ),
      page.goto("/tenants"),
    ]);
    // The list is requested at the API maximum so the ceiling is as high as
    // the API allows.
    expect(new URL(listRequest.url()).searchParams.get("limit")).toBe("200");

    await expect(page.getByRole("heading", { name: "Tenant lifecycle" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Acme Manufacturing" })).toBeVisible();
    // A short list is not capped, so no cap notice is shown.
    await expect(page.getByRole("heading", { name: /Showing the first 200 tenants/ })).toHaveCount(
      0,
    );

    const provisionForm = page.getByRole("form", { name: "Tenant provisioning" });
    await expect(provisionForm).toBeVisible();

    // Client-side validation blocks a bad tenant id with zero requests.
    await page.getByLabel("New tenant id").fill("Bad Tenant Id");
    await page.getByLabel("New tenant display name").fill("Bad Tenant");
    await provisionForm.getByRole("button", { name: "Provision tenant" }).click();
    await expect(
      page.getByText("Tenant id must match ^[a-z0-9][a-z0-9_-]*$", { exact: false }),
    ).toBeVisible();
    expect(tenantPosts).toEqual([]);

    // A valid draft round-trips through the mocked provision endpoint with CSRF.
    await page.getByLabel("New tenant id").fill("tenant_acme");
    await page.getByLabel("New tenant display name").fill("Acme Manufacturing");
    await page.getByLabel("New tenant description").fill("Reference tenant.");

    const [provisionRequest] = await Promise.all([
      page.waitForRequest(
        (request) =>
          request.method() === "POST"
          && request.url() === "http://127.0.0.1:65534/platform/tenants",
      ),
      provisionForm.getByRole("button", { name: "Provision tenant" }).click(),
    ]);
    expect(provisionRequest.headers()["x-axis-csrf-token"]).toBe("csrf-e2e-token");
    const provisionBody = provisionRequest.postDataJSON();
    expect(provisionBody.tenant_id).toBe("tenant_acme");
    expect(provisionBody.display_name).toBe("Acme Manufacturing");
    expect(provisionBody.actor_scopes).toEqual([
      "platform:tenant:operator",
      "platform:tenant:provision",
    ]);
    expect(typeof provisionBody.idempotency_key).toBe("string");
    await expect(page.getByText("Tenant provisioned.")).toBeVisible();
    // The provision success triggers a console refresh that reloads the tenant
    // registry. The registry must stay mounted (stale-while-revalidate) rather
    // than flashing to the API-unavailable state, otherwise the provision form
    // and this confirmation would be torn down mid-refresh.
    await expect(page.getByRole("heading", { name: "Tenant lifecycle" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tenant API unavailable" })).toHaveCount(0);

    // Suspend the tenant from the detail view; the action posts the reason.
    await page.route(
      "http://127.0.0.1:65534/platform/tenants/tenant_acme/quotas",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          json: { tenant_id: "tenant_acme", quotas: {}, quota_notes: [] },
          status: 200,
        });
      },
    );
    await page.route(
      "http://127.0.0.1:65534/platform/tenants/tenant_acme/suspend",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          json: { ...tenantRecord, status: "suspended", suspended_by: "operator" },
          status: 200,
        });
      },
    );

    // The detail view reads the dedicated single-tenant route rather than
    // deriving the record from the registry list.
    await page.route(
      "http://127.0.0.1:65534/platform/tenants/tenant_acme",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          json: tenantRecord,
          status: 200,
        });
      },
    );

    await page.goto("/tenants/tenant_acme");
    await expect(page.getByRole("heading", { name: "Acme Manufacturing" })).toBeVisible();
    await expect(page.getByText("Provisioned", { exact: true })).toBeVisible();

    const suspendForm = page.getByRole("form", { name: "Suspend tenant" });
    await expect(suspendForm).toBeVisible();
    await page.getByLabel("Suspension reason").fill("Contract paused");

    const [suspendRequest] = await Promise.all([
      page.waitForRequest("http://127.0.0.1:65534/platform/tenants/tenant_acme/suspend"),
      suspendForm.getByRole("button", { name: "Suspend tenant" }).click(),
    ]);
    expect(suspendRequest.method()).toBe("POST");
    expect(suspendRequest.headers()["x-axis-csrf-token"]).toBe("csrf-e2e-token");
    expect(suspendRequest.postDataJSON()).toMatchObject({
      reason: "Contract paused",
      actor_scopes: ["platform:tenant:operator", "platform:tenant:suspend"],
    });
    await expect(page.getByText(/Tenant suspended\./)).toBeVisible();

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });

  test("requires the settings readiness APIs instead of local settings data", async ({ page }) => {
    const pageErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await page.goto("/settings");

    await expect(page.getByRole("heading", { name: "Platform settings" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Settings API unavailable" })).toBeVisible();
    await expect(page.getByText("Local fallback settings records are disabled.")).toBeVisible();
    await expect(page.getByText("/ready")).toBeVisible();
    await expect(page.getByText("/deployment/readiness")).toBeVisible();
    await expect(page.getByText("/support/diagnostics")).toBeVisible();
    await expect(page.getByText("Fallback settings seed")).toHaveCount(0);

    await expectNoHorizontalOverflow(page);
    expect(pageErrors).toEqual([]);
  });
});
