"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

import { getCatalogue, type ConsoleGlossary, type ConsoleStrings } from "@/lib/i18n";
import { DEFAULT_LOCALE, type Locale } from "@/lib/locale";

type LocaleContextValue = {
  locale: Locale;
  strings: ConsoleStrings;
  glossary: ConsoleGlossary;
};

/*
 * Defaults to English so components rendered outside the root layout (unit
 * tests, the global error boundary) keep the source-of-truth copy.
 */
const LocaleContext = createContext<LocaleContextValue>({
  locale: DEFAULT_LOCALE,
  ...getCatalogue(DEFAULT_LOCALE),
});

/**
 * Supplies the locale the root layout resolved on the server, so server
 * markup and hydration read the same catalogue.
 */
export function LocaleProvider({ locale, children }: { locale: Locale; children: ReactNode }) {
  const value = useMemo(() => ({ locale, ...getCatalogue(locale) }), [locale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): Locale {
  return useContext(LocaleContext).locale;
}

/** The active locale's console copy; same shape as `strings` in lib/strings.ts. */
export function useStrings(): ConsoleStrings {
  return useContext(LocaleContext).strings;
}

/** The active locale's glossary definitions for `<Term />`. */
export function useGlossary(): ConsoleGlossary {
  return useContext(LocaleContext).glossary;
}
