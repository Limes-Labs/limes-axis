import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import {
  enumUrlField,
  stringUrlField,
  useConsoleUrlState,
} from "./console-url-state";

const schema = {
  itemId: stringUrlField("item_id"),
  tab: enumUrlField("tab", ["overview", "evidence"] as const, "overview"),
};

function Fixture() {
  const [state, setState] = useConsoleUrlState(schema);

  return (
    <div>
      <output>{`${state.itemId}:${state.tab}`}</output>
      <button onClick={() => setState({ itemId: "item_2" })} type="button">Select</button>
      <button onClick={() => setState({ itemId: "", tab: "overview" })} type="button">
        Reset
      </button>
    </div>
  );
}

beforeEach(() => {
  window.history.replaceState(null, "", "/console");
});

describe("useConsoleUrlState", () => {
  it("restores valid state and degrades invalid enum values to the default", () => {
    window.history.replaceState(null, "", "/console?item_id=item_1&tab=unknown");
    render(<Fixture />);

    expect(screen.getByText("item_1:overview")).toBeInTheDocument();
  });

  it("uses replace semantics and omits default values from the URL", async () => {
    const user = userEvent.setup();
    const initialHistoryLength = window.history.length;
    render(<Fixture />);

    await user.click(screen.getByRole("button", { name: "Select" }));
    expect(window.location.search).toBe("?item_id=item_2");
    expect(window.history.length).toBe(initialHistoryLength);

    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(window.location.search).toBe("");
    expect(window.history.length).toBe(initialHistoryLength);
  });
});
