/*
 * Console locale model. The operator's explicit choice lives in a cookie so
 * the server render, `<html lang>` and the client hydrate in the same
 * language; without a choice the browser's `Accept-Language` decides, then
 * English. This module is environment-neutral: the server reads the cookie
 * and header in `lib/locale-server.ts`, the client writes the cookie from the
 * locale switch.
 */

export const SUPPORTED_LOCALES = ["en", "it"] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "en";

/** Cookie holding the operator's explicit locale choice. */
export const LOCALE_COOKIE = "axis-locale";

/** One year: the choice is a preference, not a session artefact. */
const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

/** Each locale's name in its own language, as the switch lists it. */
export const LOCALE_NAMES: Record<Locale, string> = {
  en: "English",
  it: "Italiano",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

/** Map a BCP 47 tag ("it-IT", "en_GB", "IT") to a supported locale, if any. */
export function matchLocale(tag: string | null | undefined): Locale | null {
  if (!tag) {
    return null;
  }

  const primary = tag.trim().toLowerCase().split(/[-_]/)[0];
  return isLocale(primary) ? primary : null;
}

/**
 * Pick the best supported locale from an `Accept-Language` header, honouring
 * q-values. Ties keep header order; `q=0` means "not acceptable".
 */
export function localeFromAcceptLanguage(header: string | null | undefined): Locale | null {
  if (!header) {
    return null;
  }

  const ranges = header
    .split(",")
    .map((part, index) => {
      const [tag, ...params] = part.trim().split(";");
      const qParam = params.map((param) => param.trim()).find((param) => param.startsWith("q="));
      const quality = qParam ? Number.parseFloat(qParam.slice(2)) : 1;
      return { index, locale: matchLocale(tag), quality: Number.isFinite(quality) ? quality : 0 };
    })
    .filter((range) => range.locale !== null && range.quality > 0)
    .sort((left, right) => right.quality - left.quality || left.index - right.index);

  return ranges[0]?.locale ?? null;
}

/** Cookie beats `Accept-Language` beats the English default. */
export function resolveLocale({
  cookie,
  acceptLanguage,
}: {
  cookie?: string | null;
  acceptLanguage?: string | null;
}): Locale {
  return (isLocale(cookie) ? cookie : null) ?? localeFromAcceptLanguage(acceptLanguage) ?? DEFAULT_LOCALE;
}

/** `document.cookie` assignment that persists an explicit choice. */
export function serializeLocaleCookie(locale: Locale, { secure = false } = {}): string {
  return [
    `${LOCALE_COOKIE}=${locale}`,
    "Path=/",
    `Max-Age=${LOCALE_COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
    ...(secure ? ["Secure"] : []),
  ].join("; ");
}
