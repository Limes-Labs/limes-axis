import { createElement, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface SectionHeadingProps {
  /** Leading word(s) rendered in Signal Blue — the two-tone device. */
  lead?: string;
  children: ReactNode;
  className?: string;
  as?: "h1" | "h2" | "h3";
}

export function SectionHeading({
  lead,
  children,
  className,
  as = "h2",
}: SectionHeadingProps) {
  return createElement(
    as,
    { className: cn("font-display text-balance text-2xl text-ink sm:text-3xl", className) },
    lead ? <span className="text-signal">{lead} </span> : null,
    children,
  );
}
