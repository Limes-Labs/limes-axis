import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConsoleProvider, probeApi, useConsole } from "./console-provider";

function ConsoleProbe() {
  const { apiStatus, refreshNonce } = useConsole();
  return (
    <p data-testid="console-state">
      {apiStatus.state}:{refreshNonce}
    </p>
  );
}

describe("probeApi", () => {
  afterEach(() => vi.restoreAllMocks());

  it("preserves a healthy but degraded state when readiness is unreachable", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockRejectedValueOnce(new TypeError("ready endpoint unavailable"));

    const result = await probeApi("http://axis.test", new AbortController().signal);

    expect(result.state).toBe("degraded");
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "http://axis.test/health",
      expect.objectContaining({ cache: "no-store" }),
    );
  });
});

describe("ConsoleProvider API recovery", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("re-runs the console queries once when the API comes back after an outage", async () => {
    vi.useFakeTimers();
    let apiUp = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      if (!apiUp) {
        throw new TypeError("fetch failed");
      }
      return new Response(null, { status: 200 });
    });

    render(
      <ConsoleProvider>
        <ConsoleProbe />
      </ConsoleProvider>,
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByTestId("console-state")).toHaveTextContent("unavailable:0");

    // A probe that is still failing is not a recovery.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(screen.getByTestId("console-state")).toHaveTextContent("unavailable:0");

    apiUp = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    // Recovery bumps the refresh nonce exactly once; the re-probe it causes
    // settles online without another bump.
    expect(screen.getByTestId("console-state")).toHaveTextContent("online:1");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(screen.getByTestId("console-state")).toHaveTextContent("online:1");
  });
});
