import type { CSSProperties } from "react";

import { StatCard } from "@/components/ui/stat-card";
import { cn } from "@/lib/cn";

export type Metric = {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "ready" | "watch" | "action";
};

const MAX_METRICS = 5;

const toneClasses: Record<NonNullable<Metric["tone"]>, string> = {
  ready: "text-positive",
  watch: "text-warning",
  action: "text-danger",
};

/** Tone must never be conveyed by the dot's color alone. */
const toneText: Record<NonNullable<Metric["tone"]>, string> = {
  ready: "Ready:",
  watch: "Needs watching:",
  action: "Action required:",
};

/**
 * Horizontal strip of page metrics. Hard cap: renders the first five and
 * warns in development if given more — metrics must describe user-relevant
 * state, not enumerate internal invariants.
 */
export function MetricStrip({ metrics, label }: { metrics: Metric[]; label?: string }) {
  if (process.env.NODE_ENV !== "production" && metrics.length > MAX_METRICS) {
    console.warn(
      `MetricStrip renders at most ${MAX_METRICS} metrics; received ${metrics.length}. Extra metrics are dropped — move detail into the page body or an Inspect drawer.`,
    );
  }

  const visible = metrics.slice(0, MAX_METRICS);

  return (
    <div role="list" aria-label={label} className="grid min-w-0 grid-cols-1 gap-3 min-[380px]:grid-cols-2 lg:grid-cols-[repeat(var(--metric-count),minmax(0,1fr))]" style={{ "--metric-count": Math.max(1, visible.length) } as CSSProperties}>
      {visible.map((metric) => (
        <StatCard
          detail={metric.detail}
          key={metric.label}
          label={metric.label}
          value={metric.value}
          valueLead={metric.tone ? (
            <>
              <span aria-hidden="true" className={cn("status-dot", toneClasses[metric.tone])} />
              <span className="sr-only">{toneText[metric.tone]} </span>
            </>
          ) : null}
        />
      ))}
    </div>
  );
}
