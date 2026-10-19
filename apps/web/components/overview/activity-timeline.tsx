"use client";

import { useRef, useState } from "react";
import { Disclosure } from "@/components/ui/disclosure";
import type { AuditLedgerEvent } from "@/lib/audit-demo";
import type { ConsoleStrings } from "@/lib/i18n";
import { useStrings } from "@/providers/locale-provider";

type TimelineInput = Pick<AuditLedgerEvent, "occurred_at"> & { severity: string };

export type ActivityDateBin = {
  date: string;
  count: number;
  attention: number;
  unknownSeverity: number;
  attentionShare: number | null;
};

function utcDate(timestamp: string): string | null {
  // Require an explicit timezone: browser-local parsing must not move a bin.
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.exec(timestamp);
  if (!parts) return null;
  const [, year, month, day, hour, minute, second] = parts.map(Number);
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  if (calendar.getUTCFullYear() !== year || calendar.getUTCMonth() !== month - 1 || calendar.getUTCDate() !== day || hour > 23 || minute > 59 || second > 59) return null;
  const instant = new Date(timestamp);
  return Number.isFinite(instant.getTime()) ? instant.toISOString().slice(0, 10) : null;
}

/** Only observed dates are binned; missing days never become invented zeroes. */
export function aggregateAuditTimeline(events: readonly TimelineInput[]) {
  const dates = new Map<string, ActivityDateBin>();
  let invalidTimestamps = 0;
  for (const event of events) {
    const date = utcDate(event.occurred_at);
    if (!date) { invalidTimestamps += 1; continue; }
    const bin = dates.get(date) ?? { date, count: 0, attention: 0, unknownSeverity: 0, attentionShare: null };
    bin.count += 1;
    if (event.severity === "watch" || event.severity === "action_required") bin.attention += 1;
    else if (event.severity !== "ready") bin.unknownSeverity += 1;
    dates.set(date, bin);
  }
  const bins = [...dates.values()].sort((a, b) => a.date.localeCompare(b.date));
  for (const bin of bins) bin.attentionShare = bin.unknownSeverity ? null : bin.attention / bin.count;
  return { bins, invalidTimestamps };
}

const percent = new Intl.NumberFormat("en", { style: "percent", maximumFractionDigits: 1 });
const month = new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" });
const rangeDate = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" });
const dateInstant = (date: string) => new Date(`${date}T00:00:00Z`);
const ZONE = "UTC";
const attentionValue = (bin: ActivityDateBin, copy: ConsoleStrings["ui"]["overviewActivityTimeline"]) => bin.attentionShare === null
  ? copy.attentionUnavailable(bin.unknownSeverity)
  : copy.attentionValue(percent.format(bin.attentionShare), bin.attention, bin.count);

export function ActivityTimeline({ events }: { events: readonly AuditLedgerEvent[] }) {
  const strings = useStrings();
  const copy = strings.ui.overviewActivityTimeline;
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const [focusedDate, setFocusedDate] = useState<string | null>(null);
  const dateButtons = useRef<Array<SVGGElement | null>>([]);
  const { bins, invalidTimestamps } = aggregateAuditTimeline(events);
  const activeDate = hoveredDate ?? focusedDate ?? selectedDate;
  const active = bins.find((bin) => bin.date === activeDate);
  const focusIndex = Math.max(0, bins.findIndex((bin) => bin.date === (focusedDate ?? selectedDate)));
  const dense = bins.length > 7;
  const width = dense ? bins.length * 50 + 62 : 250;
  const plotLeft = 26;
  const plotRight = width - 36;
  const plotTop = 20;
  const plotBottom = 146;
  const plotHeight = plotBottom - plotTop;
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  const step = (plotRight - plotLeft) / Math.max(1, bins.length);
  const points = bins.map((bin, index) => ({
    x: plotLeft + step * (index + 0.5),
    y: bin.attentionShare === null ? null : plotBottom - bin.attentionShare * plotHeight,
  }));
  const clearSelection = () => {
    setSelectedDate(null);
    setHoveredDate(null);
    setFocusedDate(null);
  };
  const toggleDate = (date: string) => {
    setSelectedDate((current) => current === date ? null : date);
    setHoveredDate(null);
    setFocusedDate(null);
  };

  return (
    <div className="grid min-w-0 gap-3">
      <div className="grid gap-1">
        <div className="flex items-start justify-between gap-2">
          <p className="m-0 text-xs font-medium text-muted">{active ? copy.dateInZone(active.date, ZONE) : copy.returnedWindow}</p>
          <button type="button" disabled={!active} onClick={clearSelection} className="shrink-0 cursor-pointer border-0 bg-transparent p-0 text-xs text-signal disabled:cursor-default disabled:text-muted">{strings.ui.common.reset}</button>
        </div>
        <p role="status" className="m-0 text-sm font-medium tabular-nums text-ink">
          {active ? `${copy.eventCount(active.count)} · ${attentionValue(active, copy)}` : copy.returnedSummary(events.length, bins.length, ZONE)}
        </p>
        {bins.length > 1 ? <p className="m-0 text-xs text-muted">{copy.dateInZone(rangeDate.formatRange(dateInstant(bins[0].date), dateInstant(bins[bins.length - 1].date)), ZONE)}</p> : null}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-2 text-xs text-muted" aria-label={copy.chartLegend}>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-signal" />{copy.eventsLeftAxis}</span>
        <span className="inline-flex items-center gap-1.5"><span aria-hidden="true" className="h-0.5 w-4 bg-warning" />{copy.attentionShareRightAxis}</span>
      </div>
      {bins.length ? (
        <div className="min-w-0 overflow-x-auto rounded-xl border border-line bg-signal/[0.03] p-1 dark:border-white/10" role="region" aria-label={dense ? copy.eventsAndAttentionShareBy : copy.eventsAndAttentionShareBy2}>
          <svg role="group" aria-label={copy.chooseAUtcDateArrow} viewBox={`0 0 ${width} 194`} style={{ minWidth: dense ? width : undefined }} className="block h-auto w-full text-muted">
            {[0, 0.5, 1].map((fraction) => {
              const y = plotBottom - fraction * plotHeight;
              return <g key={fraction} aria-hidden="true" pointerEvents="none">
                <line x1={plotLeft} x2={plotRight} y1={y} y2={y} stroke="currentColor" strokeOpacity={0.15} strokeDasharray={fraction ? "3 4" : undefined} />
                {fraction !== 0.5 || maxCount % 2 === 0 ? <text x={plotLeft - 5} y={y + 4} textAnchor="end" fill="currentColor" fontSize={11}>{maxCount * fraction}</text> : null}
                <text x={plotRight + 5} y={y + 4} fill="currentColor" fontSize={11}>{fraction * 100}%</text>
              </g>;
            })}
            {bins.map((bin, index) => {
              const point = points[index];
              const barHeight = bin.count / maxCount * plotHeight;
              const highlighted = active?.date === bin.date;
              return <g key={bin.date}
                role="button"
                ref={(element) => { dateButtons.current[index] = element; }}
                tabIndex={index === focusIndex ? 0 : -1}
                aria-label={`${copy.dateInZone(bin.date, ZONE)}: ${copy.eventCount(bin.count)}; ${attentionValue(bin, copy)}`}
                aria-pressed={selectedDate === bin.date}
                className="cursor-pointer outline-none"
                onPointerEnter={(event) => { if (event.pointerType !== "touch") setHoveredDate(bin.date); }}
                onPointerLeave={() => setHoveredDate(null)}
                onFocus={() => setFocusedDate(bin.date)}
                onBlur={() => setFocusedDate(null)}
                onClick={() => toggleDate(bin.date)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggleDate(bin.date); }
                  else if (event.key === "Escape") { event.preventDefault(); clearSelection(); }
                  else if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
                    event.preventDefault();
                    const next = event.key === "Home" ? 0 : event.key === "End" ? bins.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + bins.length) % bins.length;
                    const target = dateButtons.current[next];
                    target?.focus();
                    target?.scrollIntoView({ block: "nearest", inline: "nearest" });
                  }
                }}>
                <rect x={point.x - step / 2 + 1} y={4} width={step - 2} height={184} rx={5} fill="transparent" stroke={highlighted ? "rgb(var(--signal))" : "transparent"} strokeOpacity={0.45} />
                <rect x={point.x - Math.min(14, step / 4)} y={plotBottom - barHeight} width={Math.min(28, step / 2)} height={barHeight} rx={4} className="fill-signal transition-opacity" fillOpacity={active && !highlighted ? 0.2 : highlighted ? 1 : 0.72} />
                <text x={point.x} y={plotBottom - barHeight - 6} textAnchor="middle" className="fill-ink" fontSize={12}>{bin.count}</text>
                <text x={point.x} y={168} textAnchor="middle" fill="currentColor" fontSize={12}>{Number(bin.date.slice(8))}</text>
                <text x={point.x} y={182} textAnchor="middle" fill="currentColor" fontSize={11}>{month.format(dateInstant(bin.date))}</text>
              </g>;
            })}
            {points.map((point, index) => {
              const previous = points[index - 1];
              const highlighted = active?.date === bins[index].date;
              return point.y === null ? null : <g key={bins[index].date} aria-hidden="true" pointerEvents="none">
                {previous?.y != null ? <line x1={previous.x} y1={previous.y} x2={point.x} y2={point.y} className="stroke-warning" strokeWidth={2.5} opacity={active ? 0.3 : 1} /> : null}
                <circle cx={point.x} cy={point.y} r={highlighted ? 5 : 4} className="fill-warning stroke-surface" strokeWidth={2} opacity={active && !highlighted ? 0.25 : 1} />
              </g>;
            })}
          </svg>
        </div>
      ) : <p className="m-0 text-sm text-muted">{copy.noValidTimestampsToPlot}</p>}
      <p className="m-0 text-xs leading-relaxed text-muted">
        {bins.length === 1 ? copy.onlyOneUtcDateIn : bins.length > 1 ? copy.selectADateToInspect : copy.noDatedActivityInThis}
      </p>
      {invalidTimestamps > 0 ? <p className="m-0 text-xs text-warning">{copy.invalidTimestamps(invalidTimestamps)}</p> : null}
      {bins.length > 0 ? <Disclosure className="text-xs text-muted" size="sm" title={copy.dailyValues} variant="plain">
        <p className="m-0 leading-relaxed">{copy.attentionWatchActionRequiredShare}</p>
        <div className="mt-3 grid gap-2" aria-label={copy.dailyActivityValues}>
        {bins.map((bin) => <div key={bin.date} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-2 border-b border-line/60 pb-2 text-xs last:border-0 last:pb-0">
          <time dateTime={bin.date} className="font-medium text-ink">{copy.dateInZone(bin.date, ZONE)}</time>
          <span className="tabular-nums text-ink">{copy.eventCount(bin.count)}</span>
          <span className="col-span-2 mt-1 text-muted">{bin.attentionShare === null ? copy.attentionShareUnavailable(bin.unknownSeverity) : copy.attentionDaily(bin.attention, bin.count, percent.format(bin.attentionShare))}</span>
        </div>)}
        </div>
      </Disclosure> : null}
    </div>
  );
}
