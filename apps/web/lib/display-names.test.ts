import { describe, expect, it } from "vitest";

import { displayName, humanizeIdentifier, humanizeScope, presentText } from "./display-names";

describe("display names", () => {
  it("treats blank and literal None/null/undefined values as missing", () => {
    for (const value of [null, undefined, "", "  ", "None", "null", "undefined", "NULL"]) {
      expect(presentText(value)).toBeNull();
    }
    expect(presentText(" ops-admin ")).toBe("ops-admin");
  });

  it("humanizes slug identifiers and leaves opaque ids and free text alone", () => {
    expect(humanizeIdentifier("plant-operations-owner")).toBe("Plant operations owner");
    expect(humanizeIdentifier("wf_supplier_delay_review")).toBe("Supplier delay review");
    expect(humanizeIdentifier("tenant_demo_manufacturing")).toBe("Demo manufacturing");
    expect(humanizeIdentifier("11111111-1111-4111-8111-111111111111")).toBe(
      "11111111-1111-4111-8111-111111111111",
    );
    expect(humanizeIdentifier("Plant Operations")).toBe("Plant Operations");
    expect(humanizeIdentifier("None")).toBeNull();
  });

  it("renders scopes as plain words", () => {
    expect(humanizeScope("approvals:supply:decide")).toBe("Approvals · supply · decide");
    expect(humanizeScope("tenant:read")).toBe("Tenant · read");
    expect(humanizeScope("null")).toBeNull();
  });

  it("prefers the payload's display field, then the identifier, then the fallback", () => {
    expect(displayName("Acme Plant", "tenant_acme", "Unknown")).toBe("Acme Plant");
    expect(displayName("None", "tenant_acme", "Unknown")).toBe("Acme");
    expect(displayName(null, "undefined", "Unknown")).toBe("Unknown");
  });
});
