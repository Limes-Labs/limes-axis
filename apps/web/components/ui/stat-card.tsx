import type { HTMLAttributes, ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

export type StatCardValueVariant = "display" | "mono";

export interface StatCardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  label: ReactNode;
  /** `null` while the number is loading; the card keeps its shape with a skeleton. */
  value: ReactNode | null;
  detail?: ReactNode;
  /** Top-right status cue (a dot or pill) beside the label. */
  aside?: ReactNode;
  /** Inline cue rendered before the value, e.g. a tone dot. */
  valueLead?: ReactNode;
  /**
   * `display` for counts and states; `mono` for identifiers such as an actor
   * or revision, which would otherwise wrap awkwardly at display size.
   */
  valueVariant?: StatCardValueVariant;
  valueTestId?: string;
  /** Footer content, such as a link to the underlying page. */
  children?: ReactNode;
}

const valueClasses: Record<StatCardValueVariant, string> = {
  display: "font-display flex items-center gap-2 text-2xl tabular-nums",
  mono: "font-mono text-sm leading-relaxed",
};

/**
 * The console's one stat card: label, one value, optional detail and footer.
 * It replaces the hero facts, the posture cards, `MetricStrip` items and the
 * registry summary tiles, which had drifted into two sizes and spacings.
 * Rendered as a list item so a grid of cards reads as one list.
 */
export function StatCard({
  label,
  value,
  detail,
  aside,
  valueLead,
  valueVariant = "display",
  valueTestId,
  children,
  className,
  ...rest
}: StatCardProps) {
  return (
    <article
      className={cn(
        "grid min-w-0 content-start gap-2 rounded-2xl border border-line bg-surface p-4",
        "dark:border-white/10 dark:bg-white/5",
        className,
      )}
      data-stat-card=""
      role="listitem"
      {...rest}
    >
      <div className="flex min-w-0 items-start justify-between gap-2">
        <p className="eyebrow m-0 min-w-0 break-words">{label}</p>
        {aside}
      </div>
      {value === null ? (
        <Skeleton className="h-8 w-2/5" />
      ) : (
        <p
          className={cn("m-0 min-w-0 break-words text-ink", valueClasses[valueVariant])}
          data-testid={valueTestId}
        >
          {valueLead}
          {value}
        </p>
      )}
      {detail ? (
        <p className="m-0 text-xs leading-snug break-words text-muted">{detail}</p>
      ) : null}
      {children}
    </article>
  );
}
