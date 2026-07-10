"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { FileText, RefreshCw, Search, X } from "lucide-react";

import { navigationItems } from "@/lib/foundation";

type CommandMenuProps = {
  apiLabel: string;
  onClose: () => void;
  onRefresh: () => void;
  open: boolean;
};

const supportLinks = [
  {
    description: "Append-only events, decisions and connector evidence.",
    href: "/audit",
    label: "Open audit stream",
  },
  {
    description: "Public architecture, platform and acceptance documentation.",
    href: "https://github.com/Limes-Labs/limes-axis/tree/main/docs",
    label: "Open product docs",
  },
];

function isExternalHref(href: string): boolean {
  return href.startsWith("http");
}

export function ConsoleCommandMenu({
  apiLabel,
  onClose,
  onRefresh,
  open,
}: CommandMenuProps) {
  const pathname = usePathname();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose, open]);

  const normalizedQuery = query.trim().toLowerCase();
  const results = useMemo(() => {
    const allResults = [
      ...navigationItems.map((item) => ({
        description: item.href === pathname ? "Current console section." : "Navigate to console section.",
        href: item.href,
        label: item.label,
      })),
      ...supportLinks,
    ];

    if (!normalizedQuery) {
      return allResults;
    }

    return allResults.filter((item) =>
      `${item.label} ${item.description}`.toLowerCase().includes(normalizedQuery),
    );
  }, [normalizedQuery, pathname]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-80 grid place-items-start justify-items-center bg-navy/40 px-4 pt-[min(12vh,96px)] pb-4 backdrop-blur-[2px]" role="presentation" onMouseDown={onClose}>
      <section
        aria-label="Console command menu"
        aria-modal="true"
        className="grid w-[min(680px,100%)] gap-2.5 rounded-3xl border border-mist bg-surface p-3.5 shadow-[0_30px_90px_rgb(4_18_46/0.24)] dark:border-white/12"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="grid min-h-[46px] grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[14px] border border-line bg-ink/4 py-1 pr-2 pl-3 text-muted dark:border-white/10 dark:bg-white/5">
          <Search size={18} />
          <input
            className="w-full border-0 bg-transparent text-ink outline-0 placeholder:text-muted/75"
            aria-label="Search console commands"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search pages, evidence, docs"
            ref={inputRef}
            value={query}
          />
          <button
            aria-label="Close command menu"
            className="icon-button"
            onClick={onClose}
            title="Close"
            type="button"
          >
            <X size={17} />
          </button>
        </div>

        <div className="flex justify-between gap-3 rounded-[14px] border border-line/60 bg-ink/3 px-3 py-2.5 text-xs text-muted dark:border-white/10 dark:bg-white/4 [&>span]:font-mono [&>span]:text-[10.5px] [&>span]:font-medium [&>span]:tracking-[0.16em] [&>span]:uppercase [&>span]:text-signal [&>strong]:text-positive" aria-label="Current API status">
          <span>API status</span>
          <strong>{apiLabel}</strong>
        </div>

        <button
          className={`cursor-pointer grid w-full grid-cols-[24px_minmax(0,1fr)] items-center gap-2.5 rounded-[14px] border border-line/60 bg-ink/3 p-3 text-left text-ink/80 transition-colors dark:border-white/10 dark:bg-white/4 [&_strong]:block [&_strong]:text-[13px] [&_strong]:text-ink [&_small]:mt-0.5 [&_small]:block [&_small]:text-xs [&_small]:leading-snug [&_small]:text-muted hover:border-signal/45 hover:bg-signal/10`}
          onClick={() => {
            onRefresh();
            onClose();
          }}
          type="button"
        >
          <RefreshCw size={17} />
          <span>
            <strong>Refresh live state</strong>
            <small>Re-fetch every API-backed console.</small>
          </span>
        </button>

        <div className="grid max-h-[min(48vh,420px)] gap-2 overflow-y-auto" role="list">
          {results.length > 0 ? (
            results.map((item) => {
              const external = isExternalHref(item.href);
              const content = (
                <>
                  <FileText size={17} />
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </span>
                </>
              );

              return external ? (
                <a
                  className={`grid w-full grid-cols-[24px_minmax(0,1fr)] items-center gap-2.5 rounded-[14px] border border-line/60 bg-ink/3 p-3 text-left text-ink/80 transition-colors dark:border-white/10 dark:bg-white/4 [&_strong]:block [&_strong]:text-[13px] [&_strong]:text-ink [&_small]:mt-0.5 [&_small]:block [&_small]:text-xs [&_small]:leading-snug [&_small]:text-muted hover:border-signal/45 hover:bg-signal/10`}
                  href={item.href}
                  key={item.href}
                  onClick={onClose}
                  rel="noreferrer"
                  target="_blank"
                >
                  {content}
                </a>
              ) : (
                <Link
                  className={`grid w-full grid-cols-[24px_minmax(0,1fr)] items-center gap-2.5 rounded-[14px] border border-line/60 bg-ink/3 p-3 text-left text-ink/80 transition-colors dark:border-white/10 dark:bg-white/4 [&_strong]:block [&_strong]:text-[13px] [&_strong]:text-ink [&_small]:mt-0.5 [&_small]:block [&_small]:text-xs [&_small]:leading-snug [&_small]:text-muted hover:border-signal/45 hover:bg-signal/10`}
                  href={item.href}
                  key={item.href}
                  onClick={onClose}
                >
                  {content}
                </Link>
              );
            })
          ) : (
            <p className="m-0 p-3 text-xs leading-snug text-muted">No matching console command.</p>
          )}
        </div>
      </section>
    </div>
  );
}
