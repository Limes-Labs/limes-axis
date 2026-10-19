import { DEFAULT_LOCALE, matchLocale, type Locale } from "@/lib/locale";

/**
 * The locale value formatters (`lib/format.ts`) should use.
 *
 * In the browser it reads `<html lang>`, which the root layout stamps from
 * the same cookie/`Accept-Language` resolution that picked the message
 * catalogue, so dates and copy always agree. A locale change reloads the
 * page, so the value is stable for the lifetime of a document. On the server
 * there is no request-neutral answer, so it returns the default; the console
 * formats API timestamps on the client, after data has loaded.
 */
export function getConsoleLocale(): Locale {
  if (typeof document === "undefined") {
    return DEFAULT_LOCALE;
  }

  return matchLocale(document.documentElement.lang) ?? DEFAULT_LOCALE;
}

/** Zone used before the browser's is known: the server render and tests. */
export const FALLBACK_TIME_ZONE = "UTC";

/**
 * The one time zone every console date uses — record lists, detail panels and
 * the audit heatmap alike — so a heatmap bin labelled 06:00–12:00 holds exactly
 * the events the list prints between 06:00 and 12:00. It is the browser's
 * zone; on the server it is UTC, which never reaches the screen for the same
 * reason as above. Label times with it wherever a reader compares them.
 */
export function getConsoleTimeZone(): string {
  if (typeof window === "undefined") {
    return FALLBACK_TIME_ZONE;
  }

  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || FALLBACK_TIME_ZONE;
  } catch {
    return FALLBACK_TIME_ZONE;
  }
}
