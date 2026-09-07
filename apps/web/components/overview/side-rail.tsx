"use client";

import { Card } from "@/components/ui/card";
import { SourcePill } from "@/components/ui/source-pill";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import type { ManufacturingAuditExplorer } from "@/lib/audit-demo";
import { strings } from "@/lib/strings";
import { deriveSourceState } from "@/lib/source-state";

import { normalizeLabel, type OverviewQuery } from "./overview-shared";

/** Each bar uses the same denominator: the returned audit window, not all activity. */
export function SideRail({ auditEvents }: { auditEvents: OverviewQuery<ManufacturingAuditExplorer> }) {
  const copy = strings.clarity.activity;
  if (!auditEvents.data) {
    return auditEvents.source === "loading" ? <LoadingPanel layout="detail" /> : (
      <ErrorPanel title={copy.errorTitle} detail={copy.errorDetail}
        reference={auditEvents.errorRequestId ?? undefined} />
    );
  }
  const events = auditEvents.data.events;
  if (events.length === 0) {
    return <EmptyPanel title={copy.emptyTitle} detail={copy.emptyDetail} />;
  }
  const counts = new Map<string, number>();
  for (const event of events) counts.set(event.category, (counts.get(event.category) ?? 0) + 1);
  const categories = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));

  return (
    <Card as="section" aria-label={copy.title} className="grid content-start gap-4">
      <div className="grid gap-1">
        <h2 className="m-0 font-display text-lg text-ink">{copy.title}</h2>
        <p className="m-0 text-xs text-muted">{copy.window(events.length)}</p>
      </div>
      <dl className="m-0 grid gap-4">
        {categories.map(([category, count]) => (
          <div key={category} className="grid gap-2">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <dt className="min-w-0 break-words text-ink">{normalizeLabel(category)}</dt>
              <dd className="m-0 shrink-0 tabular-nums text-muted">{count} · {new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(count / events.length * 100)}%</dd>
            </div>
            <div aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-signal/10">
              <div className="h-full rounded-full bg-signal" style={{ width: `${count / events.length * 100}%` }} />
            </div>
          </div>
        ))}
      </dl>
      <SourcePill state={deriveSourceState(auditEvents.source, true, auditEvents.data.provenance)} subject="audit window" />
    </Card>
  );
}
