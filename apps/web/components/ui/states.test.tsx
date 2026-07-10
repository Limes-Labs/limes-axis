import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("component test harness", () => {
  it("renders a placeholder element in jsdom", () => {
    render(<p>harness ready</p>);

    expect(screen.getByText("harness ready")).toBeInTheDocument();
  });
});
