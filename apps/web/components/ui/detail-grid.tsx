import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Two-column definition grid for record details. */
export function DetailGrid({ children }: { children: ReactNode }) {
  return <dl className="m-0 grid min-w-0 gap-x-6 gap-y-3.5 sm:grid-cols-2">{children}</dl>;
}

export interface KeyValueRowProps {
  label: ReactNode;
  children: ReactNode;
  /** Render the value in mono (identifiers, hashes, scopes). */
  mono?: boolean;
}

export function KeyValueRow({ label, children, mono = false }: KeyValueRowProps) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="m-0 font-mono text-[10.5px] font-medium tracking-[0.16em] text-muted uppercase">
        {label}
      </dt>
      <dd className={cn("m-0 min-w-0 text-sm break-words text-ink", mono && "font-mono text-xs")}>
        {children}
      </dd>
    </div>
  );
}
