"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, TriangleAlert, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getApiBaseUrl, isDefaultApiBaseUrl } from "@/lib/api-status";
import { cn } from "@/lib/cn";

/*
 * Unified state system: LoadingPanel / ErrorPanel / EmptyPanel are the only
 * loading, error, and empty visuals in the console. Loading never shows text
 * (so it can never be mistaken for an error), errors carry a danger tint with
 * technical details demoted behind an expander, and empty states are neutral
 * dashed panels with a single call to action.
 */

type LoadingLayout = "list" | "detail" | "metrics";

type LoadingPanelProps = {
  rows?: number;
  layout?: LoadingLayout;
};

export function LoadingPanel({ rows, layout = "list" }: LoadingPanelProps) {
  if (layout === "metrics") {
    const count = rows ?? 4;
    return (
      <div aria-busy="true" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="status">
        {Array.from({ length: count }, (_, index) => (
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
    );
  }

  if (layout === "detail") {
    return (
      <div aria-busy="true" className="flex min-w-0 flex-col gap-3" role="status">
        <Skeleton className="h-7 w-2/5" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  const count = rows ?? 5;
  return (
    <div aria-busy="true" className="flex min-w-0 flex-col gap-2.5" role="status">
      {Array.from({ length: count }, (_, index) => (
        <Skeleton key={index} className="h-11" />
      ))}
    </div>
  );
}

type ErrorPanelProps = {
  title: string;
  detail?: string;
  endpoint?: string;
  onRetry?: () => void;
};

export function ErrorPanel({ title, detail, endpoint, onRetry }: ErrorPanelProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const DetailsChevron = detailsOpen ? ChevronDown : ChevronRight;

  return (
    <section className="min-w-0 rounded-2xl border border-danger/35 bg-danger/5 p-4.5 dark:border-danger/40 dark:bg-danger/10">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display m-0 flex items-center gap-2 text-lg text-ink">
            <TriangleAlert aria-hidden="true" className="shrink-0 text-danger" size={17} />
            {title}
          </h2>
          {detail ? (
            <p className="mx-0 mt-1.5 mb-0 max-w-2xl text-sm leading-snug text-muted">{detail}</p>
          ) : null}
        </div>
        {onRetry ? (
          <Button className="px-4 py-2 text-sm" variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </div>
      <button
        aria-expanded={detailsOpen}
        className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-ink"
        type="button"
        onClick={() => setDetailsOpen((open) => !open)}
      >
        <DetailsChevron aria-hidden="true" size={13} />
        Technical details
      </button>
      {detailsOpen ? (
        <dl className="mx-0 mt-2 mb-0 flex min-w-0 flex-col gap-1.5 rounded-xl border border-line bg-surface/70 p-3 text-xs dark:border-white/10 dark:bg-white/4">
          {endpoint ? (
            <div className="flex min-w-0 flex-wrap gap-x-2">
              <dt className="m-0 font-medium text-muted">Endpoint</dt>
              <dd className="m-0 font-mono break-words text-ink">{endpoint}</dd>
            </div>
          ) : null}
          <div className="flex min-w-0 flex-wrap gap-x-2">
            <dt className="m-0 font-medium text-muted">API base URL</dt>
            <dd className="m-0 font-mono break-words text-ink">{getApiBaseUrl()}</dd>
          </div>
          {isDefaultApiBaseUrl() ? (
            <p className="m-0 leading-snug text-muted">
              {"Console is using the default http://localhost:8000 — set NEXT_PUBLIC_AXIS_API_BASE_URL if your API runs elsewhere."}
            </p>
          ) : null}
        </dl>
      ) : null}
    </section>
  );
}

type EmptyPanelAction = {
  label: string;
  href?: string;
  onClick?: () => void;
};

type EmptyPanelProps = {
  icon?: LucideIcon;
  title: string;
  detail: string;
  action?: EmptyPanelAction;
};

export function EmptyPanel({ icon: Icon, title, detail, action }: EmptyPanelProps) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col items-center gap-2 rounded-2xl border border-dashed border-slate/45",
        "bg-surface/55 p-8 text-center dark:border-white/20 dark:bg-white/4",
      )}
    >
      {Icon ? <Icon aria-hidden="true" className="text-muted" size={22} /> : null}
      <h2 className="font-display m-0 text-lg text-ink">{title}</h2>
      <p className="m-0 max-w-md text-sm leading-snug text-muted">{detail}</p>
      {action?.href ? (
        <Link
          className="mt-2 inline-flex items-center rounded-full border border-mist bg-surface px-5 py-2.5 text-sm font-medium text-ink transition-all duration-300 hover:border-signal/50 hover:text-signal dark:border-white/20 dark:hover:border-signal/60"
          href={action.href}
        >
          {action.label}
        </Link>
      ) : action?.onClick ? (
        <Button className="mt-2 px-5 py-2.5 text-sm" variant="secondary" onClick={action.onClick}>
          {action.label}
        </Button>
      ) : null}
    </section>
  );
}
