import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  axisFetchParsedJson: vi.fn(),
  routerPush: vi.fn(),
  setTheme: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.routerPush }),
  usePathname: () => "/",
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetchParsedJson: mocks.axisFetchParsedJson,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

vi.mock("@/providers/theme-provider", () => ({
  useTheme: () => ({ theme: "system", resolvedTheme: "light", setTheme: mocks.setTheme }),
}));

import { ConsoleCommandMenu } from "./console-command-menu";

function mockEntityEndpoints() {
  mocks.axisFetchParsedJson.mockImplementation((path: string) => {
    if (path === "/demo/manufacturing/workflows") {
      return Promise.resolve({
        workflow_runs: [{ workflow_id: "wf_line2_changeover", name: "Line 2 changeover" }],
      });
    }
    if (path === "/demo/manufacturing/agents") {
      return Promise.resolve({
        agents: [{ agent_id: "agent_maintenance", name: "Maintenance planner" }],
      });
    }
    if (path === "/platform/policies") {
      return Promise.resolve({
        policies: [{ policy_id: "policy_egress", display_name: "Egress lockdown" }],
      });
    }
    if (path === "/demo/manufacturing/connectors") {
      return Promise.resolve({
        connectors: [
          {
            manifest: { connector_id: "conn_mes_csv", display_name: "MES shift export" },
          },
        ],
      });
    }
    return Promise.reject(new Error(`Unexpected path ${path}`));
  });
}

function renderMenu(overrides: Partial<Parameters<typeof ConsoleCommandMenu>[0]> = {}) {
  const props = {
    apiLabel: "Online",
    onClose: vi.fn(),
    onRefresh: vi.fn(),
    open: true,
    ...overrides,
  };

  render(<ConsoleCommandMenu {...props} />);
  return props;
}

beforeEach(() => {
  mocks.axisFetchParsedJson.mockReset();
  mocks.routerPush.mockReset();
  mocks.setTheme.mockReset();
  mocks.axisFetchParsedJson.mockRejectedValue(new Error("unavailable"));
});

describe("ConsoleCommandMenu", () => {
  it("filters page items as the operator types", async () => {
    const user = userEvent.setup();
    renderMenu();

    expect(screen.getByText("Agents")).toBeInTheDocument();

    await user.keyboard("audit");

    expect(screen.getByText("Audit")).toBeInTheDocument();
    expect(screen.queryByText("Agents")).not.toBeInTheDocument();
  });

  it("navigates with ArrowDown and Enter", async () => {
    const user = userEvent.setup();
    const props = renderMenu();

    await user.keyboard("{ArrowDown}{Enter}");

    await waitFor(() => expect(mocks.routerPush).toHaveBeenCalledWith("/approvals"));
    expect(props.onClose).toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const props = renderMenu();

    await user.keyboard("{Escape}");

    expect(props.onClose).toHaveBeenCalled();
  });

  it("runs the refresh action", async () => {
    const user = userEvent.setup();
    const props = renderMenu();

    await user.click(screen.getByText("Refresh live state"));

    expect(props.onRefresh).toHaveBeenCalled();
    expect(props.onClose).toHaveBeenCalled();
  });

  it("toggles the theme from the actions group", async () => {
    const user = userEvent.setup();
    renderMenu();

    await user.click(screen.getByText("Toggle color theme"));

    expect(mocks.setTheme).toHaveBeenCalledWith("dark");
  });

  it("lists entities fetched when the menu opens and navigates to their page", async () => {
    mockEntityEndpoints();
    const user = userEvent.setup();
    renderMenu();

    expect(await screen.findByText("Line 2 changeover")).toBeInTheDocument();
    expect(screen.getByText("Maintenance planner")).toBeInTheDocument();
    expect(screen.getByText("Egress lockdown")).toBeInTheDocument();
    expect(screen.getByText("MES shift export")).toBeInTheDocument();

    await user.click(screen.getByText("Line 2 changeover"));

    expect(mocks.routerPush).toHaveBeenCalledWith("/workflows");
  });

  it("silently omits entities when every registry fetch fails", async () => {
    renderMenu();

    await waitFor(() => expect(mocks.axisFetchParsedJson).toHaveBeenCalledTimes(4));
    expect(screen.queryByText("Entities")).not.toBeInTheDocument();
  });
});
