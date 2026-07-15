import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  axisFetchJson: vi.fn(),
  axisFetchParsedJson: vi.fn(),
  refreshNonce: 0,
}));

vi.mock("@/lib/axis-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./axis-api")>()),
  axisFetchJson: mocks.axisFetchJson,
  axisFetchParsedJson: mocks.axisFetchParsedJson,
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    apiBaseUrl: "http://localhost:8000",
    apiStatus: { state: "online", label: "Online", detail: "" },
    refreshNonce: mocks.refreshNonce,
    triggerRefresh: vi.fn(),
  }),
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

import { AxisApiError } from "./axis-api";
import { useAxisQuery } from "./use-axis-query";

type Registry = { items: string[] };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  mocks.axisFetchJson.mockReset();
  mocks.axisFetchParsedJson.mockReset();
  mocks.refreshNonce = 0;
});

describe("useAxisQuery", () => {
  it("moves from loading to api on initial success", async () => {
    mocks.axisFetchJson.mockResolvedValue({ items: ["a"] });

    const { result } = renderHook(() => useAxisQuery<Registry>("/demo/registry"));

    expect(result.current.source).toBe("loading");
    expect(result.current.data).toBeNull();
    expect(result.current.isRefreshing).toBe(false);

    await waitFor(() => expect(result.current.source).toBe("api"));
    expect(result.current.data).toEqual({ items: ["a"] });
    expect(result.current.error).toBeNull();
    expect(result.current.isRefreshing).toBe(false);
  });

  it("keeps previous data and toggles isRefreshing across a refresh", async () => {
    mocks.axisFetchJson.mockResolvedValueOnce({ items: ["a"] });

    const { result, rerender } = renderHook(() => useAxisQuery<Registry>("/demo/registry"));
    await waitFor(() => expect(result.current.source).toBe("api"));

    const second = deferred<Registry>();
    mocks.axisFetchJson.mockReturnValueOnce(second.promise);
    mocks.refreshNonce = 1;
    rerender();

    await waitFor(() => expect(result.current.isRefreshing).toBe(true));
    expect(result.current.data).toEqual({ items: ["a"] });
    expect(result.current.source).toBe("api");

    second.resolve({ items: ["a", "b"] });

    await waitFor(() => expect(result.current.isRefreshing).toBe(false));
    expect(result.current.data).toEqual({ items: ["a", "b"] });
    expect(result.current.source).toBe("api");
  });

  it("keeps data but flips source to unavailable when a refresh fails", async () => {
    mocks.axisFetchJson.mockResolvedValueOnce({ items: ["a"] });

    const { result, rerender } = renderHook(() => useAxisQuery<Registry>("/demo/registry"));
    await waitFor(() => expect(result.current.source).toBe("api"));

    mocks.axisFetchJson.mockRejectedValueOnce(new Error("Axis API request failed with 503"));
    mocks.refreshNonce = 1;
    rerender();

    await waitFor(() => expect(result.current.source).toBe("unavailable"));
    expect(result.current.data).toEqual({ items: ["a"] });
    expect(result.current.error).toBe("Axis API request failed with 503");
    expect(result.current.isRefreshing).toBe(false);
  });

  it("exposes the HTTP status of a failed request as errorStatus", async () => {
    mocks.axisFetchJson.mockRejectedValueOnce(new AxisApiError("/demo/registry", 404));

    const { result } = renderHook(() => useAxisQuery<Registry>("/demo/registry"));

    await waitFor(() => expect(result.current.source).toBe("unavailable"));
    expect(result.current.errorStatus).toBe(404);
    expect(result.current.data).toBeNull();
  });

  it("keeps errorStatus null for non-HTTP failures and clears it on success", async () => {
    mocks.axisFetchJson.mockRejectedValueOnce(new TypeError("fetch failed"));

    const { result, rerender } = renderHook(() => useAxisQuery<Registry>("/demo/registry"));
    await waitFor(() => expect(result.current.source).toBe("unavailable"));
    expect(result.current.errorStatus).toBeNull();

    mocks.axisFetchJson.mockResolvedValueOnce({ items: ["a"] });
    mocks.refreshNonce = 1;
    rerender();

    await waitFor(() => expect(result.current.source).toBe("api"));
    expect(result.current.errorStatus).toBeNull();
  });

  it("resets to loading and drops data when the path changes", async () => {
    mocks.axisFetchJson.mockResolvedValueOnce({ items: ["a"] });

    const { result, rerender } = renderHook(
      ({ path }: { path: string }) => useAxisQuery<Registry>(path),
      { initialProps: { path: "/demo/registry" } },
    );
    await waitFor(() => expect(result.current.source).toBe("api"));

    const second = deferred<Registry>();
    mocks.axisFetchJson.mockReturnValueOnce(second.promise);
    rerender({ path: "/demo/other" });

    await waitFor(() => expect(result.current.source).toBe("loading"));
    expect(result.current.data).toBeNull();
    expect(result.current.isRefreshing).toBe(false);

    second.resolve({ items: ["z"] });
    await waitFor(() => expect(result.current.source).toBe("api"));
    expect(result.current.data).toEqual({ items: ["z"] });
  });

  it("uses the supplied runtime decoder and surfaces contract failures", async () => {
    const parse = (value: unknown): Registry => {
      if (typeof value !== "object" || value === null || !("items" in value)) {
        throw new TypeError("items missing");
      }
      return value as Registry;
    };
    mocks.axisFetchParsedJson.mockRejectedValueOnce(
      new Error("Axis API response did not match the expected contract."),
    );

    const { result } = renderHook(() =>
      useAxisQuery<Registry>("/demo/registry", { parse }),
    );

    await waitFor(() => expect(result.current.source).toBe("unavailable"));
    expect(mocks.axisFetchParsedJson).toHaveBeenCalledWith(
      "/demo/registry",
      parse,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(result.current.error).toBe(
      "Axis API response did not match the expected contract.",
    );
    expect(result.current.errorStatus).toBeNull();
  });
});
