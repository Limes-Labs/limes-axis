"use client";

import { useId } from "react";

import { Select } from "@/components/ui/select";
import { cn } from "@/lib/cn";
import {
  LOCALE_NAMES,
  SUPPORTED_LOCALES,
  isLocale,
  serializeLocaleCookie,
  type Locale,
} from "@/lib/locale";
import { useLocale, useStrings } from "@/providers/locale-provider";

function reloadDocument() {
  window.location.reload();
}

/**
 * English/Italiano switch. The choice is written to the `axis-locale` cookie
 * and the document reloads, so the server renders `<html lang>`, the message
 * catalogue and formatted dates in the new language and hydration never sees
 * two languages at once.
 */
export function LocaleSwitch({
  className,
  reload = reloadDocument,
}: {
  className?: string;
  /** Injected in tests; defaults to a full document reload. */
  reload?: () => void;
}) {
  const locale = useLocale();
  const copy = useStrings().shell.locale;
  const id = useId();
  const detailId = `${id}-detail`;

  function changeLocale(next: Locale) {
    if (next === locale) {
      return;
    }

    document.cookie = serializeLocaleCookie(next, {
      secure: window.location.protocol === "https:",
    });
    reload();
  }

  return (
    <div className={cn("grid min-w-[10rem] gap-1", className)}>
      <label className="text-xs font-semibold text-muted" htmlFor={id}>
        {copy.label}
      </label>
      <Select
        aria-describedby={detailId}
        id={id}
        onChange={(event) => {
          if (isLocale(event.target.value)) {
            changeLocale(event.target.value);
          }
        }}
        value={locale}
      >
        {SUPPORTED_LOCALES.map((option) => (
          <option key={option} lang={option} value={option}>
            {LOCALE_NAMES[option]}
          </option>
        ))}
      </Select>
      <span className="sr-only" id={detailId}>
        {copy.detail}
      </span>
    </div>
  );
}
