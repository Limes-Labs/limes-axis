"use client";

import { BookOpenText } from "lucide-react";

import type { SourceState } from "@/lib/source-state";
import { useStrings } from "@/providers/locale-provider";

export type OverviewSource = { subject: string; state: SourceState };

/** The overview sections whose data is a reference scenario, in page order. */
export function exampleSubjects(sources: readonly OverviewSource[]): string[] {
  return Array.from(
    new Set(sources.filter((source) => source.state === "reference").map((source) => source.subject)),
  );
}

/**
 * One page-level "Example scenario" notice. The overview used to carry about a
 * dozen provenance chips, one per panel; they now live in each panel's tooltip
 * and this banner says once, up front, that some of what follows is example
 * data. Live, empty and loading data need no banner, and a failed endpoint is
 * already explained by its own section error.
 */
export function ScenarioBanner({
  demoScenario,
  sources,
}: {
  /** The tenant runs the bootstrapped demo scenario (same signal as the topbar badge). */
  demoScenario: boolean;
  sources: readonly OverviewSource[];
}) {
  const strings = useStrings();
  const subjects = exampleSubjects(sources);
  if (!demoScenario && subjects.length === 0) {
    return null;
  }

  const copy = strings.overview.scenarioBanner;

  return (
    <section
      aria-label={copy.title}
      className="flex min-w-0 items-start gap-3 rounded-2xl border border-signal/30 bg-tint-50 px-4 py-3 dark:bg-signal/10"
      data-scenario-banner
    >
      <BookOpenText aria-hidden="true" className="mt-0.5 shrink-0 text-signal" size={17} />
      <div className="grid min-w-0 gap-0.5">
        <h2 className="m-0 text-sm font-medium text-ink">{copy.title}</h2>
        <p className="m-0 text-xs leading-snug text-muted">
          {/* On a phone the section list alone carries the message. */}
          {subjects.length > 0 ? <span className="max-sm:hidden">{copy.detail} </span> : copy.demoDetail}
          {subjects.length > 0 ? copy.sections(subjects) : null}
        </p>
      </div>
    </section>
  );
}
