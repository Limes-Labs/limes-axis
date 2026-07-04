import { afterEach, describe, expect, it, vi } from "vitest";

import { axisFetch, axisFetchJson } from "./axis-api";

describe("Axis API fetch layer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.NEXT_PUBLIC_AXIS_API_BASE_URL;
  });

  it("includes browser credentials so API-owned OIDC cookies can authenticate requests", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    const fetchMock = vi.fn<typeof fetch>(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await axisFetch("/identity/session");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://axis-api.test/identity/session",
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
        method: "GET",
      }),
    );
  });

  it("sets JSON content type on POST bodies without dropping credentials", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    const fetchMock = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await axisFetchJson<{ ok: boolean }>("/demo/manufacturing/operations/daily-brief", {
      method: "POST",
      body: { tenant_id: "tenant_demo_manufacturing" },
    });

    const [, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    const headers = new Headers(init?.headers);

    expect(init?.credentials).toBe("include");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init?.body).toBe('{"tenant_id":"tenant_demo_manufacturing"}');
  });
});
