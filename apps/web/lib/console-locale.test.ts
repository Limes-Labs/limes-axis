import { describe, expect, it } from "vitest";

import { FALLBACK_TIME_ZONE, getConsoleLocale, getConsoleTimeZone } from "./console-locale";
import { consoleDateTimeFormat, formatTimestamp } from "./format";

describe("console locale and time zone on the server", () => {
  it("renders with a stable locale and zone, so markup cannot depend on the request's browser", () => {
    // This suite runs in Node: no document, no window — the server render.
    expect(getConsoleLocale()).toBe("en");
    expect(getConsoleTimeZone()).toBe(FALLBACK_TIME_ZONE);
    expect(formatTimestamp("2026-06-21T16:30:00Z")).toBe("Jun 21, 2026, 16:30");
  });

  it("adds a 24-hour clock only to formatters that show a time, and caches them", () => {
    const withTime = consoleDateTimeFormat({ hour: "2-digit", minute: "2-digit" });
    expect(withTime.resolvedOptions().hourCycle).toBe("h23");
    expect(withTime.resolvedOptions().timeZone).toBe("UTC");
    expect(consoleDateTimeFormat({ hour: "2-digit", minute: "2-digit" })).toBe(withTime);

    const dateOnly = consoleDateTimeFormat({ month: "short", day: "numeric" });
    expect(dateOnly.resolvedOptions().hourCycle).toBeUndefined();
    // An explicit zone wins over the console zone.
    expect(consoleDateTimeFormat({ hour: "numeric", timeZone: "Europe/Rome" }).resolvedOptions().timeZone)
      .toBe("Europe/Rome");
  });
});
