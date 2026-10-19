/*
 * Calendar arithmetic in an IANA time zone, shared by the audit heatmap and
 * the overview "Activity by date" chart so both bin an instant into the same
 * civil day — the day the console prints for it (`getConsoleTimeZone`).
 * Days are not assumed to be 24 hours long: a DST change gives a 23- or
 * 25-hour day, and every boundary is computed from the zone's own offset.
 */

export const DAY_MS = 86_400_000;

type WallClock = { year: number; month: number; day: number; hour: number; minute: number; second: number };

const wallClockFormats = new Map<string, Intl.DateTimeFormat>();

/** The calendar date and clock time an instant shows in `timeZone`. */
export function wallClock(instant: number, timeZone: string): WallClock {
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
export function civilDay(instant: number, timeZone: string): number {
  const clock = wallClock(instant, timeZone);
  return Date.UTC(clock.year, clock.month - 1, clock.day);
}

/**
 * The instant at which `timeZone` shows `hour`:00 on the civil day `day`
 * (a `civilDay` value). Two passes settle the zone offset across a DST change;
 * hour 24 is the next day's midnight.
 */
export function zonedInstant(day: number, hour: number, timeZone: string): number {
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
