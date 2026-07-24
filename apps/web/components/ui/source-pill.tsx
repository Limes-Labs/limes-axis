import { CircleAlert, CircleCheck, Clock, Loader2 } from "lucide-react";
import type { ComponentType } from "react";

import { cn } from "@/lib/cn";
import type { SourceState } from "@/lib/source-state";

const tones: Record<SourceState, string> = {
  loading: "status-checking",
  live: "signal-ready",
  stale: "signal-watch",
  unavailable: "signal-action-required",
};

const icons: Record<SourceState, ComponentType<{ className?: string }>> = {
  loading: Loader2,
  live: CircleCheck,
  stale: Clock,
  unavailable: CircleAlert,
};

/** Screen-reader text so the state is never conveyed by color alone. */
const assistiveText: Record<SourceState, string> = {
  loading: "Loading:",
  live: "Live data:",
  stale: "Stale data:",
  unavailable: "Unavailable:",
};

export interface SourcePillProps {
  state: SourceState;
  /**
   * What the pill is describing, e.g. "agent registry". The state word is
   * supplied by the component so the tone and the wording can never disagree.
   */
  subject: string;
  className?: string;
}

const labels: Record<SourceState, (subject: string) => string> = {
  loading: (subject) => `Loading ${subject}`,
  live: (subject) => `Live ${subject}`,
  stale: (subject) => `Stale ${subject}`,
  unavailable: (subject) => `${subject} unavailable`,
};

/**
 * Data-provenance badge. Previously each console hardcoded the green `ready`
 * tone and computed only the text, so a surface could render a green pill
 * reading "Agent API unavailable". Tone and label are derived together here.
 */
export function SourcePill({ state, subject, className }: SourcePillProps) {
  const Icon = icons[state];

  return (
    <span className={cn("status-pill", tones[state], className)}>
      <Icon aria-hidden="true" className={cn("size-3.5", state === "loading" && "animate-spin")} />
      <span className="sr-only">{assistiveText[state]} </span>
      {labels[state](subject)}
    </span>
  );
}
