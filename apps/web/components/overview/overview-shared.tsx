import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, CircleAlert, CircleCheck, Clock3 } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { platformStatusLabel, type PlatformStatus } from "@/lib/platform-overview";
import type { AxisQuerySource } from "@/lib/use-axis-query";

/*
 * Small shared pieces for the overview control-room sections. Each section
 * receives the raw `useAxisQuery` result for the endpoints it depends on so
 * a failing endpoint degrades only that section.
 */

/** The subset of a `useAxisQuery` result the overview sections consume. */
export type OverviewQuery<T> = {
  data: T | null;
  errorRequestId?: string | null;
  source: AxisQuerySource;
  /** Re-run this query only; wired to the section's ErrorPanel retry. */
  refetch?: () => void;
};

/** Combine request ids when a section depends on more than one failed query. */
export function overviewErrorReference(
  ...queries: Array<OverviewQuery<unknown>>
): string | undefined {
  const requestIds = Array.from(
    new Set(queries.flatMap((query) => query.errorRequestId ? [query.errorRequestId] : [])),
  );
  return requestIds.length > 0 ? requestIds.join(", ") : undefined;
}

export function normalizeLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replaceAll(".", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function shortTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function StatusDot({ status }: { status: PlatformStatus }) {
  const Icon = status === "ready"
    ? CircleCheck
    : status === "watch"
      ? Clock3
      : CircleAlert;

  return (
    <Icon
      aria-label={`Status: ${platformStatusLabel(status)}`}
      className={cn(
        "size-3.5 shrink-0",
        status === "ready" && "text-positive",
        status === "watch" && "text-warning",
        status === "action_required" && "text-danger",
      )}
      data-status={status}
      role="img"
    />
  );
}

export function PanelLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      className={buttonVariants({ size: "sm", variant: "link", className: "mt-auto w-fit" })}
      href={href}
    >
      {children}
      <ArrowRight aria-hidden="true" size={13} />
    </Link>
  );
}

export function PanelHeader({
  eyebrow,
  title,
  aside,
}: {
  eyebrow: string;
  title?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="grid gap-1">
        <h2 className="font-display m-0 text-lg text-ink">{title ?? eyebrow}</h2>
      </div>
      {aside}
    </div>
  );
}
