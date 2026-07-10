import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Eyebrow } from "@/components/ui/eyebrow";
import { cn } from "@/lib/cn";
import type { PlatformStatus } from "@/lib/platform-overview";
import type { AxisQuerySource } from "@/lib/use-axis-query";

/*
 * Small shared pieces for the overview control-room sections. Each section
 * receives the raw `useAxisQuery` result for the endpoints it depends on so
 * a failing endpoint degrades only that section.
 */

/** The subset of a `useAxisQuery` result the overview sections consume. */
export type OverviewQuery<T> = {
  data: T | null;
  source: AxisQuerySource;
};

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
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        status === "ready" && "bg-positive",
        status === "watch" && "bg-warning",
        status === "action_required" && "bg-danger",
      )}
    />
  );
}

export function PanelLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      className="mt-auto inline-flex items-center gap-1.5 pt-1 font-mono text-xs tracking-[0.12em] text-signal uppercase hover:underline"
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
        <Eyebrow>{eyebrow}</Eyebrow>
        {title ? <h2 className="font-display m-0 text-lg text-ink">{title}</h2> : null}
      </div>
      {aside}
    </div>
  );
}
