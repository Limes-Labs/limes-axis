import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  useAxisQuery: vi.fn(),
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

import { ModelRoutingConsole } from "./model-routing-console";

describe("ModelRoutingConsole tabs", () => {
  beforeEach(() => {
    mocks.useAxisQuery.mockReset();
    mocks.useAxisQuery.mockReturnValue({
      data: null,
      source: "unavailable",
      error: "Axis API request failed.",
      isLoading: false,
      isRefreshing: false,
      isUnavailable: true,
    });
  });

  it("shows one header strip with the reference-vs-live explanation and tabs", () => {
    render(<ModelRoutingConsole />);

    expect(
      screen.getByText(
        "Reference routing shows the governed routing design; live invocations are the calls the platform actually executed.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Reference routing" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Live invocations" })).toBeInTheDocument();
  });

  it("renders the reference tab by default and switches to live invocations", async () => {
    const user = userEvent.setup();
    render(<ModelRoutingConsole />);

    // Reference tab active: its error panel renders, live panels do not.
    expect(
      screen.getByRole("heading", { name: "Routing API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Model invocation API unavailable" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Live invocations" }));

    expect(
      screen.getByRole("heading", { name: "Model invocation API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Model endpoint API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Routing API unavailable" }),
    ).not.toBeInTheDocument();
  });
});
