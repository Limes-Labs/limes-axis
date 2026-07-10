import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/** Pulsing placeholder block for loading states. */
export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-xl bg-ink/8 dark:bg-white/10", className)}
      {...rest}
    />
  );
}
