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
