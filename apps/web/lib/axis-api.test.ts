import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT,
  AxisApiError,
  axisFetch,
  axisFetchJson,
} from "./axis-api";
import type { OidcConsoleSession } from "./oidc-session";

const BEARER_SESSION: OidcConsoleSession = {
  accessToken: "bearer-token",
  actorId: "actor-1",
  tenantId: "tenant-1",
  scopes: [],
};

function stubBrowserDocument(cookie: string) {
  vi.stubGlobal("document", { cookie });
}

function stubBrowserWindow() {
  const dispatchEvent = vi.fn();
  vi.stubGlobal("window", { dispatchEvent });
  return dispatchEvent;
}

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

  it("attaches the CSRF header to cookie-mode mutations from the readable cookie", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("axis_csrf=csrf-token-1");
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await axisFetch("/identity/sessions/ref-1/revoke", { method: "POST" });

    const [, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    const headers = new Headers(init?.headers);
    expect(headers.get("X-Axis-Csrf-Token")).toBe("csrf-token-1");
  });

  it("does not attach the CSRF header to safe methods or when no cookie exists", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("axis_csrf=csrf-token-1");
    const fetchMock = vi.fn<typeof fetch>(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await axisFetch("/identity/session");
    stubBrowserDocument("");
    await axisFetch("/identity/sessions/ref-1/revoke", { method: "POST" });

    for (const call of fetchMock.mock.calls) {
      const [, init] = call as [RequestInfo | URL, RequestInit];
      expect(new Headers(init?.headers).has("X-Axis-Csrf-Token")).toBe(false);
    }
  });

  it("keeps bearer-mode mutations CSRF-free because they are exempt server-side", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("axis_csrf=csrf-token-1");
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await axisFetch("/identity/sessions/ref-1/revoke", {
      method: "POST",
      session: BEARER_SESSION,
    });

    const [, init] = fetchMock.mock.calls[0] as [RequestInfo | URL, RequestInit];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer bearer-token");
    expect(headers.has("X-Axis-Csrf-Token")).toBe(false);
  });

  it("refreshes the browser session once on a cookie-mode 401 and retries the request", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("axis_csrf=stale-token");
    stubBrowserWindow();

    let protectedCalls = 0;
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.endsWith("/identity/session/refresh")) {
        stubBrowserDocument("axis_csrf=rotated-token");
        return new Response(null, { status: 204 });
      }
      protectedCalls += 1;
      if (protectedCalls === 1) {
        return new Response("{}", { status: 401 });
      }
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const payload = await axisFetchJson<{ ok: boolean }>("/identity/sessions", {
      method: "POST",
      body: {},
    });

    expect(payload).toEqual({ ok: true });
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls).toEqual([
      "http://axis-api.test/identity/sessions",
      "http://axis-api.test/identity/session/refresh",
      "http://axis-api.test/identity/sessions",
    ]);

    const refreshHeaders = new Headers(
      (fetchMock.mock.calls[1] as [RequestInfo | URL, RequestInit])[1]?.headers,
    );
    expect(refreshHeaders.get("X-Axis-Csrf-Token")).toBe("stale-token");

    const retryHeaders = new Headers(
      (fetchMock.mock.calls[2] as [RequestInfo | URL, RequestInit])[1]?.headers,
    );
    expect(retryHeaders.get("X-Axis-Csrf-Token")).toBe("rotated-token");
  });

  it("surfaces the signed-out state when the refresh fails, without retry loops", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("axis_csrf=stale-token");
    const dispatchEvent = stubBrowserWindow();

    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.endsWith("/identity/session/refresh")) {
        return new Response("{}", { status: 401 });
      }
      return new Response("{}", { status: 401 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(axisFetchJson("/identity/sessions")).rejects.toBeInstanceOf(AxisApiError);

    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(urls).toEqual([
      "http://axis-api.test/identity/sessions",
      "http://axis-api.test/identity/session/refresh",
    ]);
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    const [event] = dispatchEvent.mock.calls[0] as [Event];
    expect(event.type).toBe(AXIS_BROWSER_SESSION_SIGNED_OUT_EVENT);
  });

  it("does not attempt a refresh for anonymous or bearer-mode 401s", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("");
    stubBrowserWindow();
    const fetchMock = vi.fn<typeof fetch>(async () => new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    const anonymous = await axisFetch("/identity/sessions");
    expect(anonymous.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    stubBrowserDocument("axis_csrf=csrf-token-1");
    const bearer = await axisFetch("/identity/sessions", { session: BEARER_SESSION });
    expect(bearer.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("deduplicates concurrent 401 refreshes into a single rotation call", async () => {
    process.env.NEXT_PUBLIC_AXIS_API_BASE_URL = "http://axis-api.test";
    stubBrowserDocument("axis_csrf=stale-token");
    stubBrowserWindow();

    let refreshCalls = 0;
    let releaseRefresh: (response: Response) => void = () => {};
    const refreshGate = new Promise<Response>((resolve) => {
      releaseRefresh = resolve;
    });
    const firstAttempts = new Set<string>();
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.endsWith("/identity/session/refresh")) {
        refreshCalls += 1;
        return refreshGate;
      }
      if (!firstAttempts.has(url)) {
        firstAttempts.add(url);
        return new Response("{}", { status: 401 });
      }
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const pending = Promise.all([
      axisFetchJson<{ ok: boolean }>("/identity/sessions"),
      axisFetchJson<{ ok: boolean }>("/identity/session"),
    ]);
    await vi.waitFor(() => {
      expect(firstAttempts.size).toBe(2);
      expect(refreshCalls).toBe(1);
    });
    releaseRefresh(new Response(null, { status: 204 }));

    await expect(pending).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(refreshCalls).toBe(1);
  });
});
