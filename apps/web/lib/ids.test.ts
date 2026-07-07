import { afterEach, describe, expect, it, vi } from "vitest";

import { safeRandomUuid } from "./ids";

const UUID_V4_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe("safeRandomUuid", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns a well-formed, unique id from the native crypto.randomUUID", () => {
    const ids = new Set(Array.from({ length: 100 }, () => safeRandomUuid()));

    expect(ids.size).toBe(100);
    for (const id of ids) {
      expect(id).toMatch(UUID_V4_PATTERN);
    }
  });

  it("falls back to getRandomValues without throwing when randomUUID is absent", () => {
    vi.stubGlobal("crypto", {
      getRandomValues: (bytes: Uint8Array) => {
        for (let index = 0; index < bytes.length; index += 1) {
          bytes[index] = index * 7;
        }
        return bytes;
      },
    });

    const id = safeRandomUuid();

    expect(id).toMatch(UUID_V4_PATTERN);
  });

  it("falls back to Math.random when the crypto object is unavailable", () => {
    vi.stubGlobal("crypto", undefined);

    const ids = new Set(Array.from({ length: 50 }, () => safeRandomUuid()));

    expect(ids.size).toBe(50);
    for (const id of ids) {
      expect(id).toMatch(UUID_V4_PATTERN);
    }
  });
});
