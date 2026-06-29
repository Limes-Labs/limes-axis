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
    <div className="command-menu-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-label="Console command menu"
        aria-modal="true"
        className="command-menu"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="command-menu-search">
          <Search size={18} />
          <input
            aria-label="Search console commands"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search pages, evidence, docs"
            ref={inputRef}
            value={query}
          />
          <button
            aria-label="Close command menu"
            className="ops-icon-button"
            onClick={onClose}
            title="Close"
            type="button"
          >
            <X size={17} />
          </button>
        </div>

        <div className="command-menu-status" aria-label="Current API status">
          <span>API status</span>
          <strong>{apiLabel}</strong>
        </div>

        <button
          className="command-menu-action"
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

        <div className="command-menu-results" role="list">
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
                  className="command-menu-result"
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
                  className="command-menu-result"
                  href={item.href}
                  key={item.href}
                  onClick={onClose}
                >
                  {content}
                </Link>
              );
            })
          ) : (
            <p className="command-menu-empty">No matching console command.</p>
          )}
        </div>
      </section>
    </div>
  );
}
