"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SourcePill } from "@/components/ui/source-pill";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import type { ManufacturingAuditExplorer } from "@/lib/audit-demo";
import { useStrings } from "@/providers/locale-provider";
import { deriveSourceState } from "@/lib/source-state";

import { normalizeLabel, type OverviewQuery } from "./overview-shared";
import { ActivityTimeline } from "./activity-timeline";
import { OVERVIEW_AUDIT_WINDOW } from "./evidence-feed";

/** Each bar uses the same denominator: the returned audit window, not all activity. */
export function SideRail({
  auditEvents,
  hiddenReadCount = 0,
  windowLimit = OVERVIEW_AUDIT_WINDOW,
}: {
  /** The audit window as displayed: reads are already removed unless shown. */
  auditEvents: OverviewQuery<ManufacturingAuditExplorer>;
  /** Read events filtered out of this chart by the feed's "Show reads" switch. */
  hiddenReadCount?: number;
  windowLimit?: number;
}) {
  const strings = useStrings();
  const copy = strings.clarity.activity;
  const [view, setView] = useState("category");
  if (!auditEvents.data) {
    if (auditEvents.source === "tenant_not_found") {
      return <EmptyPanel title={copy.emptyTitle} detail={copy.emptyDetail} />;
    }
    return auditEvents.source === "loading" ? <LoadingPanel layout="detail" /> : (
      <ErrorPanel title={copy.errorTitle} detail={copy.errorDetail}
        onRetry={auditEvents.refetch}
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
    <Card as="section" aria-label={view === "category" ? copy.title : "Activity by date"} className="grid min-w-0 content-start gap-4">
      <div className="grid gap-1">
        <h2 className="m-0 font-display text-lg text-ink">{view === "category" ? copy.title : "Activity by date"}</h2>
        <p className="m-0 text-xs text-muted">{view === "category" ? copy.window(events.length, windowLimit) : copy.dateWindow(events.length, windowLimit)}</p>
        {hiddenReadCount > 0 ? (
          <p className="m-0 text-xs text-muted">{strings.audit.reads.hidden(hiddenReadCount)}</p>
        ) : null}
      </div>
      <Tabs value={view} onValueChange={setView}>
        <TabsList aria-label="Activity chart view" className="w-full">
          <TabsTrigger value="category" className="flex-1 px-2.5">Category</TabsTrigger>
          <TabsTrigger value="date" className="flex-1 px-2.5">By date</TabsTrigger>
        </TabsList>
        <TabsContent value="category">
      <dl className="m-0 grid gap-4">
        {categories.map(([category, count]) => (
          // A <dl> group may hold only <dt>/<dd>, so the bar is a second,
          // decorative <dd> spanning both columns rather than a sibling <div>.
          <div key={category} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-2 text-sm">
            <dt className="min-w-0 break-words text-ink">{normalizeLabel(category)}</dt>
            <dd className="m-0 shrink-0 tabular-nums text-muted">{count} · {new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(count / events.length * 100)}%</dd>
            <dd aria-hidden="true" className="col-span-2 m-0 h-2 overflow-hidden rounded-full bg-signal/10">
              <div className="h-full rounded-full bg-signal" style={{ width: `${count / events.length * 100}%` }} />
            </dd>
          </div>
        ))}
      </dl>
        </TabsContent>
        <TabsContent value="date"><ActivityTimeline events={events} /></TabsContent>
      </Tabs>
      <SourcePill state={deriveSourceState(auditEvents.source, true, auditEvents.data.provenance)} subject="audit window" />
    </Card>
  );
}
