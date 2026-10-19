import { glossary, strings } from "@/lib/strings";
import { glossaryIt, stringsIt } from "@/lib/strings.it";
import type { Locale } from "@/lib/locale";

/**
 * The shape every translation must match: the English catalogue with its
 * literal string types widened to `string`. Keys, nesting, tuple lengths and
 * function signatures are kept, so a missing key, an extra key or a template
 * function with the wrong parameters fails typecheck.
 */
export type Catalogue<T> = T extends string
  ? string
  : T extends (...args: infer Args) => infer Result
    ? (...args: Args) => Catalogue<Result>
    : T extends object
      ? { readonly [Key in keyof T]: Catalogue<T[Key]> }
      : T;

export type ConsoleStrings = Catalogue<typeof strings>;
export type ConsoleGlossary = Catalogue<typeof glossary>;

export type LocaleCatalogue = {
  strings: ConsoleStrings;
  glossary: ConsoleGlossary;
};

const catalogues: Record<Locale, LocaleCatalogue> = {
  en: { strings, glossary },
  it: { strings: stringsIt, glossary: glossaryIt },
};

export function getCatalogue(locale: Locale): LocaleCatalogue {
  return catalogues[locale];
}
