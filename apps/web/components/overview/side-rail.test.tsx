import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SideRail } from "./side-rail";
import { auditEventsFixture } from "./overview-fixtures";

describe("Activity breakdown", () => {
  it("uses the whole returned window as denominator and exposes counts without the graphic", () => {
    const events = auditEventsFixture.events.map((event, index) => ({ ...event, category: index < 3 ? "connector" : "approval" }));
    render(<SideRail auditEvents={{ source: "api", data: { ...auditEventsFixture, events } }} />);
    const chart = screen.getByRole("region", { name: "Activity by category" });
    expect(within(chart).getByText("Share of 4 events in the latest window (up to 25).")).toBeInTheDocument();
    expect(within(chart).getByText("3 · 75%")).toBeInTheDocument();
    expect(within(chart).getByText("1 · 25%")).toBeInTheDocument();
    expect(within(chart).getByText("audit window: live")).toBeInTheDocument();
    expect(within(chart).getAllByRole("term").map((term) => term.textContent)).toEqual(["Connector", "Approval"]);
  });

  it("preserves reference provenance instead of calling example records live", () => {
    render(<SideRail auditEvents={{ source: "api", data: { ...auditEventsFixture, provenance: "reference_scenario" } }} />);
    expect(screen.getByText("audit window: reference scenario")).toBeInTheDocument();
    expect(screen.queryByText("audit window: live")).not.toBeInTheDocument();
  });

  it("does not draw a zero-denominator chart for an empty window", () => {
    render(<SideRail auditEvents={{ source: "api", data: { ...auditEventsFixture, events: [] } }} />);
    expect(screen.getByRole("heading", { name: "No activity to compare" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Activity by category" })).not.toBeInTheDocument();
  });

  it("distinguishes unavailable data from no activity", () => {
    render(<SideRail auditEvents={{ source: "unavailable", data: null, errorRequestId: "request-chart" }} />);
    expect(screen.getByRole("heading", { name: "Activity breakdown unavailable" })).toBeInTheDocument();
    expect(screen.queryByText("No activity to compare")).not.toBeInTheDocument();
  });
});
