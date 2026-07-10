"use client";

import type { ReactNode } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { glossary, type GlossaryKey } from "@/lib/strings";

export interface TermProps {
  /** Glossary key from `lib/strings.ts`. */
  k: GlossaryKey;
  /** Custom inline text; defaults to the glossary label. */
  children?: ReactNode;
}

/**
 * Inline glossary term: dotted underline with the plain-English definition in
 * a tooltip. Keyboard-focusable so the definition is reachable without a mouse.
 */
export function Term({ k, children }: TermProps) {
  const entry = glossary[k];

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="cursor-help underline decoration-muted/70 decoration-dotted underline-offset-3"
            tabIndex={0}
          >
            {children ?? entry.label}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <p className="m-0 font-medium text-ink">{entry.label}</p>
          <p className="mx-0 mt-1 mb-0 text-muted">{entry.definition}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
