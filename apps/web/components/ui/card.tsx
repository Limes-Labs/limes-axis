import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Adds the hover lift + shadow treatment. */
  interactive?: boolean;
  children: ReactNode;
}

export function Card({ interactive = false, className, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-line bg-surface p-6",
        "dark:border-white/10 dark:bg-white/5",
        interactive &&
          "transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_20px_50px_rgb(4_18_46/0.07)] dark:hover:bg-white/8 dark:hover:shadow-none",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
