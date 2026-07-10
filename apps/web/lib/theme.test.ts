import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME_PREFERENCE,
  THEME_STORAGE_KEY,
  isThemePreference,
  parseThemePreference,
  resolveTheme,
} from "./theme";

describe("theme resolution", () => {
  it("keeps a stable storage key for the no-FOUC script and provider", () => {
    expect(THEME_STORAGE_KEY).toBe("axis-theme");
    expect(DEFAULT_THEME_PREFERENCE).toBe("system");
  });

  it("validates persisted preferences", () => {
    expect(isThemePreference("light")).toBe(true);
    expect(isThemePreference("dark")).toBe(true);
    expect(isThemePreference("system")).toBe(true);
    expect(isThemePreference("midnight")).toBe(false);
    expect(isThemePreference(null)).toBe(false);
  });

  it("falls back to system for unknown stored values", () => {
    expect(parseThemePreference(null)).toBe("system");
    expect(parseThemePreference("")).toBe("system");
    expect(parseThemePreference("blue")).toBe("system");
    expect(parseThemePreference("dark")).toBe("dark");
    expect(parseThemePreference("light")).toBe("light");
  });

  it("honours explicit preferences regardless of the system scheme", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("light", false)).toBe("light");
    expect(resolveTheme("dark", true)).toBe("dark");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("resolves system and invalid preferences from matchMedia", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme(null, true)).toBe("dark");
    expect(resolveTheme("garbage", false)).toBe("light");
  });
});
