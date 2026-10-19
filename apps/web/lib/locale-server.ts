import { cookies, headers } from "next/headers";
import { cache } from "react";

import { getCatalogue } from "@/lib/i18n";
import { LOCALE_COOKIE, resolveLocale, type Locale } from "@/lib/locale";

/**
 * Server-only: resolve the request's locale from the `axis-locale` cookie,
 * then `Accept-Language`, then English. Memoised per request so the layout,
 * pages and metadata agree.
 */
export const getRequestLocale = cache(async (): Promise<Locale> => {
  const [cookieStore, headerStore] = await Promise.all([cookies(), headers()]);
  return resolveLocale({
    cookie: cookieStore.get(LOCALE_COOKIE)?.value,
    acceptLanguage: headerStore.get("accept-language"),
  });
});

/** The request locale's message catalogue, for server components and metadata. */
export async function getServerStrings() {
  return getCatalogue(await getRequestLocale()).strings;
}
