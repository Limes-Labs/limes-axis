import { afterEach, describe, expect, it, vi } from "vitest";

import { probeApi } from "./console-provider";

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
