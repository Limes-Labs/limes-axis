import { describe, expect, it } from "vitest";

import {
  AXIS_OIDC_SESSION_STORAGE_KEY,
  buildOidcAuthorizeUrl,
  buildAxisAuthInit,
  clearStoredOidcSession,
  createOidcSessionFromAccessToken,
  normalizeOidcReturnTo,
  readStoredOidcSession,
  writeStoredOidcSession,
} from "./oidc-session";

function unsignedToken(claims: Record<string, unknown>): string {
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return `axis.${payload}.signature`;
}

class MemoryStorage implements Storage {
  private values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

describe("OIDC console session bridge", () => {
  it("builds safe browser SSO authorize URLs for local API-owned sessions", () => {
    expect(buildOidcAuthorizeUrl("http://127.0.0.1:8000", "/connectors?snapshot_id=abc")).toBe(
      "http://127.0.0.1:8000/identity/oidc/authorize?return_to=%2Fconnectors%3Fsnapshot_id%3Dabc",
    );
    expect(buildOidcAuthorizeUrl("http://127.0.0.1:8000/", "https://evil.example/")).toBe(
      "http://127.0.0.1:8000/identity/oidc/authorize?return_to=%2F",
    );
  });

  it("normalizes OIDC return targets to same-origin paths only", () => {
    expect(normalizeOidcReturnTo("/")).toBe("/");
    expect(normalizeOidcReturnTo("/audit?event_id=evt_1")).toBe("/audit?event_id=evt_1");
    expect(normalizeOidcReturnTo("")).toBe("/");
    expect(normalizeOidcReturnTo("settings")).toBe("/");
    expect(normalizeOidcReturnTo("//evil.example/path")).toBe("/");
    expect(normalizeOidcReturnTo("https://evil.example/path")).toBe("/");
  });

  it("derives actor, tenant and scopes from bearer token claims", () => {
    const token = unsignedToken({
      sub: "plant-operations-owner-role",
      axis_tenant: "tenant_demo_manufacturing",
      scope: "approvals:supply:decide audit:read",
      scp: ["workflows:read"],
      realm_access: { roles: ["operations-owner"] },
      resource_access: {
        "limes-axis-api": { roles: ["approvals:maintenance:decide"] },
      },
      exp: 4102444800,
    });

    expect(createOidcSessionFromAccessToken(token)).toMatchObject({
      accessToken: token,
      actorId: "plant-operations-owner-role",
      tenantId: "tenant_demo_manufacturing",
      scopes: [
        "approvals:maintenance:decide",
        "approvals:supply:decide",
        "audit:read",
        "operations-owner",
        "workflows:read",
      ],
      expiresAt: 4102444800,
    });
  });

  it("stores and clears the session through a storage boundary", () => {
    const storage = new MemoryStorage();
    const session = createOidcSessionFromAccessToken(
      unsignedToken({
        sub: "agent_supply_risk",
        axis_tenant: "tenant_demo_manufacturing",
        scope: "supply:read",
      }),
    );

    writeStoredOidcSession(storage, session);
    expect(storage.getItem(AXIS_OIDC_SESSION_STORAGE_KEY)).toContain("agent_supply_risk");
    expect(readStoredOidcSession(storage)).toEqual(session);

    clearStoredOidcSession(storage);
    expect(readStoredOidcSession(storage)).toBeNull();
  });

  it("adds Authorization while preserving existing request headers", () => {
    const session = createOidcSessionFromAccessToken(
      unsignedToken({
        sub: "agent_supply_risk",
        axis_tenant: "tenant_demo_manufacturing",
        scope: "supply:read",
      }),
    );

    const init = buildAxisAuthInit(
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
      session,
    );
    const headers = new Headers(init.headers);

    expect(init.method).toBe("POST");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Authorization")).toBe(`Bearer ${session.accessToken}`);
  });
});
