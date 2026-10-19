import { describe, expect, it } from "vitest";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  isLocale,
  localeFromAcceptLanguage,
  matchLocale,
  resolveLocale,
  serializeLocaleCookie,
} from "./locale";

describe("resolveLocale", () => {
  it("prefers the cookie over Accept-Language", () => {
    expect(resolveLocale({ cookie: "en", acceptLanguage: "it-IT,it;q=0.9" })).toBe("en");
    expect(resolveLocale({ cookie: "it", acceptLanguage: "en-US,en;q=0.9" })).toBe("it");
  });

  it("falls back to Accept-Language when no valid cookie is set", () => {
    expect(resolveLocale({ cookie: undefined, acceptLanguage: "it-IT,it;q=0.9,en;q=0.8" })).toBe("it");
    expect(resolveLocale({ cookie: "fr", acceptLanguage: "it" })).toBe("it");
    expect(resolveLocale({ cookie: "", acceptLanguage: "en-GB" })).toBe("en");
  });

  it("defaults to English when neither names a supported locale", () => {
    expect(resolveLocale({})).toBe(DEFAULT_LOCALE);
    expect(resolveLocale({ cookie: "de", acceptLanguage: "de-DE,fr;q=0.5" })).toBe("en");
    expect(resolveLocale({ cookie: null, acceptLanguage: null })).toBe("en");
  });
});

describe("localeFromAcceptLanguage", () => {
  it("honours q-values rather than header order", () => {
    expect(localeFromAcceptLanguage("en;q=0.4, it;q=0.8")).toBe("it");
    expect(localeFromAcceptLanguage("de-DE, en;q=0.7, it;q=0.9")).toBe("it");
  });

  it("keeps header order for equal quality and skips q=0", () => {
    expect(localeFromAcceptLanguage("it, en")).toBe("it");
    expect(localeFromAcceptLanguage("it;q=0, en;q=0.1")).toBe("en");
  });

  it("returns null for absent or unsupported headers", () => {
    expect(localeFromAcceptLanguage(undefined)).toBeNull();
    expect(localeFromAcceptLanguage("*")).toBeNull();
    expect(localeFromAcceptLanguage("fr-FR,de;q=0.9")).toBeNull();
  });
});

describe("matchLocale and isLocale", () => {
  it("maps regional and differently cased tags to a supported locale", () => {
    expect(matchLocale("it-IT")).toBe("it");
    expect(matchLocale("EN_gb")).toBe("en");
    expect(matchLocale("pt-BR")).toBeNull();
    expect(matchLocale("")).toBeNull();
  });

  it("accepts only exact supported codes", () => {
    expect(isLocale("it")).toBe(true);
    expect(isLocale("it-IT")).toBe(false);
    expect(isLocale(42)).toBe(false);
  });
});

describe("serializeLocaleCookie", () => {
  it("persists the choice site-wide for a year", () => {
    expect(serializeLocaleCookie("it")).toBe(
      `${LOCALE_COOKIE}=it; Path=/; Max-Age=31536000; SameSite=Lax`,
    );
    expect(serializeLocaleCookie("en", { secure: true })).toMatch(/; Secure$/);
  });
});
