import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { formatClockTime, formatDateTime } from "@/lib/format";

import {
  AuditActivityHeatmap,
  auditBinInterval,
  buildAuditActivity,
  filterAuditTimeInterval,
} from "./audit-activity-heatmap";

const event = (occurred_at: string) => ({ occurred_at });

afterEach(() => {
  document.documentElement.lang = "";
});

describe("audit heatmap time zone", () => {
  it("bins by the wall clock of the given zone, not UTC", () => {
    // 05:30Z is 07:30 in Rome (UTC+2 in September): the 06:00–12:00 bin.
    // 23:30Z on the 7th is already 01:30 on the 8th in Rome.
    const events = [event("2026-09-08T05:30:00Z"), event("2026-09-07T23:30:00Z")];
    const rome = buildAuditActivity(events, events, "Europe/Rome");
    const utc = buildAuditActivity(events, events, "UTC");

    expect(rome.days[6].bins).toEqual([1, 1, 0, 0]);
    expect(utc.days[6].bins).toEqual([1, 0, 0, 0]);
    expect(utc.days[5].bins).toEqual([0, 0, 0, 1]);
    // Each day starts at local midnight.
    expect(rome.days[6].timestamp).toBe(Date.parse("2026-09-07T22:00:00Z"));
  });

  it("keeps a bin's count and the list it filters in agreement across a DST change", () => {
    // Rome leaves summer time on 25 Oct 2026: that day has 25 hours.
    const events = [
      event("2026-10-24T22:30:00Z"), // 00:30 CEST, bin 0
      event("2026-10-25T00:30:00Z"), // 02:30 CEST, bin 0
      event("2026-10-25T01:30:00Z"), // 02:30 CET (repeated hour), bin 0
      event("2026-10-25T04:30:00Z"), // 05:30 CET, bin 0
      event("2026-10-25T05:30:00Z"), // 06:30 CET, bin 1
      event("2026-10-25T22:30:00Z"), // 23:30 CET, bin 3
    ];
    const activity = buildAuditActivity(events, events, "Europe/Rome");
    const day = activity.days[6];
    expect(day.bins).toEqual([4, 1, 0, 1]);

    const first = auditBinInterval(day.timestamp, 0, "Europe/Rome");
    expect(first).toEqual({ start: Date.parse("2026-10-24T22:00:00Z"), end: Date.parse("2026-10-25T05:00:00Z") });
    const last = auditBinInterval(day.timestamp, 3, "Europe/Rome");
    expect(last.end).toBe(Date.parse("2026-10-25T23:00:00Z"));

    day.bins.forEach((count, bin) => {
      const interval = { ...auditBinInterval(day.timestamp, bin, "Europe/Rome"), label: "bin" };
      expect(filterAuditTimeInterval(events, interval)).toHaveLength(count);
    });
  });

  it("labels the zone it bins in", () => {
    const events = [event("2026-09-08T05:30:00Z")];
    render(<AuditActivityHeatmap events={events} returnedEvents={events} timeZone="Europe/Rome" />);

    expect(screen.getByText("Europe/Rome · 6-hour bins")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /Europe\/Rome time/ })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sep 8, 2026, 06:00–12:00 Europe/Rome: 1 event in returned window" }),
    ).toBeInTheDocument();
  });

  it("uses the console zone by default, the same one the list's times are printed in", () => {
    // Vitest pins TZ=UTC, so the console (browser) zone is UTC here.
    const events = [event("2026-09-08T18:45:00Z")];
    render(<AuditActivityHeatmap events={events} returnedEvents={events} />);

    expect(screen.getByText("UTC · 6-hour bins")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /18:00–24:00 UTC: 1 event/ })).toBeInTheDocument();
    expect(formatClockTime("2026-09-08T18:45:00Z")).toBe("18:45");
  });
});

describe("locale-aware 24-hour formatting", () => {
  it("prints a 24-hour clock in English and Italian", () => {
    const instant = "2026-06-21T16:30:00Z";
    document.documentElement.lang = "en";
    expect(formatDateTime(instant)).toBe("Jun 21, 16:30");
    expect(formatClockTime(instant)).toBe("16:30");

    document.documentElement.lang = "it";
    expect(formatDateTime(instant)).toBe("21 giu, 16:30");
    expect(formatClockTime(instant)).toBe("16:30");
  });
});
