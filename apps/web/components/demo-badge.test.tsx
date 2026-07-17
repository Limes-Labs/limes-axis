import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useAxisQuery: vi.fn(),
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

import { DEMO_BADGE_OVERVIEW_ENDPOINT, DemoBadge } from "./demo-badge";

type Source = "loading" | "api" | "unavailable";

function queryResult(data: unknown, source: Source, errorStatus: number | null = null) {
  return {
    data,
    source,
    error: source === "unavailable" ? "Axis API request failed." : null,
    errorStatus,
    isRefreshing: false,
    isLoading: source === "loading",
    isUnavailable: source === "unavailable",
  };
}

const scenarioOverview = {
  scenario: "Plant Operations Cockpit",
  plant_name: "Ravenna Works",
};

beforeEach(() => {
  mocks.useAxisQuery.mockReset();
});

describe("DemoBadge", () => {
  it("renders the demo pill when the overview identifies the demo scenario", () => {
    mocks.useAxisQuery.mockReturnValue(queryResult(scenarioOverview, "api"));
    render(<DemoBadge />);

    expect(screen.getByText("Demo")).toBeInTheDocument();
    expect(mocks.useAxisQuery).toHaveBeenCalledWith(
      DEMO_BADGE_OVERVIEW_ENDPOINT,
      expect.objectContaining({ parse: expect.any(Function) }),
    );
  });

  it("explains the badge in a tooltip on keyboard focus", async () => {
    mocks.useAxisQuery.mockReturnValue(queryResult(scenarioOverview, "api"));
    const user = userEvent.setup();
    render(<DemoBadge />);

    await user.tab();
    const matches = await screen.findAllByText(
      "This tenant runs the demo manufacturing scenario",
    );
    expect(matches.length).toBeGreaterThan(0);
  });

  it("renders nothing while the overview is loading", () => {
    mocks.useAxisQuery.mockReturnValue(queryResult(null, "loading"));
    const { container } = render(<DemoBadge />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the tenant is not bootstrapped (overview 404)", () => {
    mocks.useAxisQuery.mockReturnValue(queryResult(null, "unavailable", 404));
    const { container } = render(<DemoBadge />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the overview request fails", () => {
    mocks.useAxisQuery.mockReturnValue(queryResult(null, "unavailable"));
    const { container } = render(<DemoBadge />);

    expect(container).toBeEmptyDOMElement();
  });
});
