import {
  BookOpenText,
  CircleAlert,
  CircleCheck,
  CircleMinus,
  Clock,
  Loader2,
} from "lucide-react";
import type { ComponentType } from "react";

import { cn } from "@/lib/cn";
import type { ConsoleStrings } from "@/lib/i18n";
import { strings as englishStrings } from "@/lib/strings";
import type { SourceState } from "@/lib/source-state";
import { useStrings } from "@/providers/locale-provider";

const tones: Record<SourceState, string> = {
  loading: "status-checking",
  live: "signal-ready",
  reference: "status-checking",
  empty: "status-checking",
  stale: "signal-watch",
  unavailable: "signal-action-required",
};

const icons: Record<SourceState, ComponentType<{ className?: string }>> = {
  loading: Loader2,
  live: CircleCheck,
  reference: BookOpenText,
  empty: CircleMinus,
  stale: Clock,
  unavailable: CircleAlert,
};

export interface SourcePillProps {
  state: SourceState;
  /**
   * What the pill is describing, e.g. "agent registry". The state word is
   * supplied by the component so the tone and the wording can never disagree.
   */
  subject: string;
  className?: string;
  /** Short visible labels for grouped dashboard summaries. */
  compact?: boolean;
}

/**
 * Plain-text provenance for a `title` or tooltip, e.g. "agents: live". Pages
 * that summarise provenance once (the overview banner) keep it per item here
 * instead of repeating a visible pill on every panel.
 */
export function sourceStateLabel(
  state: SourceState,
  subject: string,
  copy: ConsoleStrings = englishStrings,
): string {
  return copy.sources.states[state](subject);
}

/**
 * Data-provenance badge. Previously each console hardcoded the green `ready`
 * tone and computed only the text, so a surface could render a green pill
 * reading "Agent API unavailable". Tone and label are derived together here.
 */
export function SourcePill({ state, subject, className, compact = false }: SourcePillProps) {
  const Icon = icons[state];
  const strings = useStrings();
  const copy = strings.ui.uiSourcePill;

  return (
    <span className={cn("status-pill", tones[state], className)} data-source-state={state}>
      <Icon aria-hidden="true" className={cn("size-3.5", state === "loading" && "animate-spin")} />
      <span className="sr-only">{copy.dataSource}{" "}</span>
      {compact && state === "reference" ? copy.example(subject) : sourceStateLabel(state, subject, strings)}
    </span>
  );
}
