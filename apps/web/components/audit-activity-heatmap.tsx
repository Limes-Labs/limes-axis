"use client";

import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { FALLBACK_TIME_ZONE, getConsoleTimeZone } from "@/lib/console-locale";
import { consoleDateTimeFormat } from "@/lib/format";
import { useStrings } from "@/providers/locale-provider";

type TimedEvent = { occurred_at: string };
export type AuditTimeInterval = { start: number; end: number; label: string };
const DAY = 86_400_000;
const hours = ["00:00–06:00", "06:00–12:00", "12:00–18:00", "18:00–24:00"];

function timestamp(value: string) {
  // Require an explicit zone: a timestamp without one names no instant.
  if (!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return NaN;
  const date = value.slice(0, 10);
  const midnight = new Date(`${date}T00:00:00Z`);
  // Date.parse normalizes some impossible dates, such as 30 February.
  if (!Number.isFinite(midnight.getTime()) || midnight.toISOString().slice(0, 10) !== date) return NaN;
  return Date.parse(value);
}

type WallClock = { year: number; month: number; day: number; hour: number; minute: number; second: number };

const wallClockFormats = new Map<string, Intl.DateTimeFormat>();

/** The calendar date and clock time an instant shows in `timeZone`. */
function wallClock(instant: number, timeZone: string): WallClock {
  let format = wallClockFormats.get(timeZone);
  if (!format) {
    format = new Intl.DateTimeFormat("en-US", {
      timeZone, hourCycle: "h23",
      year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric",
    });
    wallClockFormats.set(timeZone, format);
  }
  const parts = Object.fromEntries(format.formatToParts(instant).map((part) => [part.type, Number(part.value)]));
  return { year: parts.year, month: parts.month, day: parts.day, hour: parts.hour, minute: parts.minute, second: parts.second };
}

/** Midnight UTC of the instant's calendar date in `timeZone`: a zone-free day number. */
function civilDay(instant: number, timeZone: string): number {
  const clock = wallClock(instant, timeZone);
  return Date.UTC(clock.year, clock.month - 1, clock.day);
}

/**
 * The instant at which `timeZone` shows `hour`:00 on the civil day `day`
 * (a `civilDay` value). Two passes settle the zone offset across a DST change;
 * hour 24 is the next day's midnight.
 */
function zonedInstant(day: number, hour: number, timeZone: string): number {
  const target = day + hour * 3_600_000;
  const offset = (instant: number) => {
    const clock = wallClock(instant, timeZone);
    const shown = Date.UTC(clock.year, clock.month - 1, clock.day, clock.hour, clock.minute, clock.second);
    return shown - (instant - (((instant % 1000) + 1000) % 1000));
  };
  const first = target - offset(target);
  const second = target - offset(first);
  return second;
}

export function filterAuditTimeInterval<T extends TimedEvent>(events: T[], interval: AuditTimeInterval | null): T[] {
  if (!interval) return events;
  return events.filter((event) => {
    const at = timestamp(event.occurred_at);
    return Number.isFinite(at) && at >= interval.start && at < interval.end;
  });
}

/**
 * Seven calendar days of six-hour bins in `timeZone`, ending on the date of
 * the newest returned event. Each day carries the instant it starts; a bin is
 * a half-open [start, end) interval of real instants, so filtering a list by
 * a bin and counting the bin always agree.
 */
export function buildAuditActivity(
  events: TimedEvent[],
  returnedEvents: TimedEvent[],
  timeZone: string = FALLBACK_TIME_ZONE,
) {
  const validReturned = returnedEvents.map((event) => timestamp(event.occurred_at)).filter(Number.isFinite);
  const latest = validReturned.length ? Math.max(...validReturned) : null;
  const lastDay = latest === null ? null : civilDay(latest, timeZone);
  const firstDay = lastDay === null ? null : lastDay - 6 * DAY;
  const days = firstDay === null ? [] : Array.from({ length: 7 }, (_, day) => ({
    timestamp: zonedInstant(firstDay + day * DAY, 0, timeZone),
    bins: [0, 0, 0, 0],
  }));
  let invalid = 0;
  let inRange = 0;
  for (const event of events) {
    const at = timestamp(event.occurred_at);
    if (!Number.isFinite(at)) { invalid += 1; continue; }
    if (firstDay === null) continue;
    const clock = wallClock(at, timeZone);
    const index = (Date.UTC(clock.year, clock.month - 1, clock.day) - firstDay) / DAY;
    if (index < 0 || index > 6) continue;
    days[index].bins[Math.floor(clock.hour / 6)] += 1;
    inRange += 1;
  }
  return { days, inRange, invalid, outsideRange: events.length - invalid - inRange,
    filteredCount: events.length, returnedCount: returnedEvents.length,
    maximum: Math.max(0, ...days.flatMap((day) => day.bins)) };
}

/** The [start, end) instants of a day's six-hour bin in `timeZone`. */
export function auditBinInterval(dayStart: number, bin: number, timeZone: string = FALLBACK_TIME_ZONE) {
  const day = civilDay(dayStart, timeZone);
  return { start: zonedInstant(day, bin * 6, timeZone), end: zonedInstant(day, bin * 6 + 6, timeZone) };
}

function intensity(count: number, maximum: number) {
  if (count === 0) return "bg-ink/4 text-muted dark:bg-white/5";
  const fraction = count / maximum;
  if (fraction > 0.75) return "bg-signal text-white";
  if (fraction > 0.5) return "bg-signal/25 text-ink dark:bg-signal/30";
  if (fraction > 0.25) return "bg-signal/15 text-ink dark:bg-signal/20";
  return "bg-signal/8 text-ink dark:bg-signal/10";
}

export function AuditActivityHeatmap({ events, returnedEvents, selectedInterval = null, onSelectInterval, controlsId, timeZone }: {
  events: TimedEvent[];
  returnedEvents: TimedEvent[];
  selectedInterval?: AuditTimeInterval | null;
  onSelectInterval?: (interval: AuditTimeInterval | null) => void;
  controlsId?: string;
  /** Defaults to the console time zone, which the audit list also prints in. */
  timeZone?: string;
}) {
  const strings = useStrings();
  const id = useId();
  const [inspected, setInspected] = useState<string | null>(null);
  const zone = timeZone ?? getConsoleTimeZone();
  const dateLabel = consoleDateTimeFormat({ day: "numeric", month: "short", year: "numeric", timeZone: zone });
  const weekdayLabel = consoleDateTimeFormat({ weekday: "short", timeZone: zone });
  const dayNumber = consoleDateTimeFormat({ day: "numeric", timeZone: zone });
  const activity = buildAuditActivity(events, returnedEvents, zone);
  const cells = activity.days.flatMap((day) => day.bins.map((count, bin) => ({
    key: `${day.timestamp}-${bin}`, count,
    start: auditBinInterval(day.timestamp, bin, zone).start,
    label: `${dateLabel.format(day.timestamp)}, ${hours[bin]} ${zone}`,
  })));
  const selected = cells.find((cell) => cell.key === inspected)
    ?? cells.find((cell) => cell.start === selectedInterval?.start)
    ?? cells.find((cell) => cell.count === activity.maximum);
  const completeWindow = activity.inRange === activity.filteredCount
    && activity.filteredCount === activity.returnedCount;
  const range = activity.days.length > 0
    ? `${dateLabel.formatRange(activity.days[0].timestamp, activity.days[6].timestamp)} ${zone}`
    : strings.ui.auditActivityHeatmap.noValidDatedEvents;

  return (
    <section aria-labelledby={`${id}-title`} className="min-w-0 rounded-2xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id={`${id}-title`} className="font-display m-0 text-lg text-ink">{strings.ui.auditActivityHeatmap.activityByTime}</h2>
        <span className="rounded-full bg-ink/4 px-2.5 py-1 text-xs tabular-nums text-muted dark:bg-white/5">{strings.ui.auditActivityHeatmap.zoneSixHourBins(zone)}</span>
      </div>
      <p className="mb-2 mt-2 text-xs leading-relaxed text-muted">
        {completeWindow ? (
          <><strong className="font-medium text-ink">{strings.ui.auditActivityHeatmap.eventCount(activity.inRange)}</strong> · {range}</>
        ) : (
          <><strong className="font-medium text-ink">{strings.ui.auditActivityHeatmap.filteredInRange(activity.inRange, activity.filteredCount)}</strong>{" "}{strings.ui.auditActivityHeatmap.inRangeReturned(activity.returnedCount, range)}</>
        )}
      </p>
      {activity.days.length > 0 ? (
        <>
          <table className="w-full table-fixed border-separate border-spacing-1" aria-label={strings.ui.auditActivityHeatmap.auditEventsByZonedDate(zone)}>
            <thead>
              <tr>
                <th scope="col" className="w-12 text-left text-[11px] font-normal break-words text-muted" title={zone}>{zone.split("/").pop()?.replaceAll("_", " ")}</th>
                {activity.days.map((day) => (
                  <th scope="col" key={day.timestamp} className="pb-1 text-center text-xs font-normal text-muted" aria-label={dateLabel.format(day.timestamp)}>
                    <span className="block">{weekdayLabel.format(day.timestamp)}</span>
                    <span className="mt-0.5 block tabular-nums text-ink">{dayNumber.format(day.timestamp)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hours.map((hour, bin) => (
                <tr key={hour}>
                  <th scope="row" className="text-left text-[11px] font-normal tabular-nums text-muted">{hour.replaceAll(":00", "")}</th>
                  {activity.days.map((day) => {
                    const count = day.bins[bin];
                    const key = `${day.timestamp}-${bin}`;
                    const { start, end } = auditBinInterval(day.timestamp, bin, zone);
                    const isActive = selectedInterval?.start === start;
                    return (
                      <td key={key} className="p-0">
                        <button type="button"
                          aria-label={strings.ui.auditActivityHeatmap.cellLabel(`${dateLabel.format(day.timestamp)}, ${hour} ${zone}`, count)}
                          aria-describedby={`${id}-detail`}
                          aria-pressed={onSelectInterval ? isActive : undefined}
                          aria-controls={controlsId}
                          onFocus={() => setInspected(key)} onClick={() => {
                            setInspected(key);
                            onSelectInterval?.(isActive ? null : {
                              start, end,
                              label: `${dateLabel.format(day.timestamp)}, ${hour} ${zone}`,
                            });
                          }}
                          className={`min-h-8 w-full cursor-pointer rounded-md border-0 px-0.5 text-xs font-medium tabular-nums focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal active:scale-[0.97] ${intensity(count, activity.maximum)} ${isActive ? "ring-2 ring-ink ring-offset-1 ring-offset-surface" : ""}`}>
                          {count}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 text-xs">
            <p id={`${id}-detail`} role="status" className="m-0 min-w-0 leading-relaxed text-ink">
              {selected ? `${strings.ui.auditActivityHeatmap.eventCount(selected.count)} · ${selected.label}` : null}
            </p>
            <div className="flex items-center gap-1.5 text-muted" aria-label={strings.ui.auditActivityHeatmap.colorScale(activity.maximum)}>
              <span>0</span>
              <span aria-hidden="true" className="flex gap-0.5">
                {["bg-ink/4 dark:bg-white/5", "bg-signal/15", "bg-signal/25", "bg-signal"].map((color) => <span key={color} className={`h-2.5 w-3 rounded-sm ${activity.maximum ? color : "bg-ink/4 dark:bg-white/5"}`} />)}
              </span>
              <span>{strings.ui.auditActivityHeatmap.maximumCount(activity.maximum)}</span>
            </div>
          </div>
          {selectedInterval && onSelectInterval ? (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-3 dark:border-white/10">
              <p className="m-0 text-xs font-medium text-ink">{strings.ui.auditActivityHeatmap.timeFilter(selectedInterval.label)}</p>
              <Button aria-controls={controlsId} onClick={() => onSelectInterval(null)} size="sm" variant="secondary">
                {strings.ui.auditActivityHeatmap.clearTimeFilter}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
      <p className="mb-0 mt-2 text-[11px] leading-relaxed text-muted">
        {strings.ui.auditActivityHeatmap.footnote(Boolean(onSelectInterval), activity.outsideRange, activity.invalid)}
      </p>
    </section>
  );
}
