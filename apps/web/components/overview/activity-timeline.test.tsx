import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ActivityTimeline, activityDateInterval, aggregateAuditTimeline } from "./activity-timeline";
import { auditEventsFixture } from "./overview-fixtures";

describe("UTC audit activity aggregation", () => {
  it("bins offset timestamps by their UTC date, sorts dates and uses each date's denominator", () => {
    const result = aggregateAuditTimeline([
      { occurred_at: "2026-09-09T12:00:00Z", severity: "watch" },
      { occurred_at: "2026-09-09T00:30:00+02:00", severity: "ready" },
      { occurred_at: "2026-09-08T22:40:00Z", severity: "action_required" },
      { occurred_at: "2026-09-09T08:00:00-04:00", severity: "ready" },
      { occurred_at: "2026-09-09T12:30:00Z", severity: "watch" },
    ]);
    expect(result.invalidTimestamps).toBe(0);
    expect(result.bins).toEqual([
      { date: "2026-09-08", count: 2, attention: 1, unknownSeverity: 0, attentionShare: 0.5 },
      { date: "2026-09-09", count: 3, attention: 2, unknownSeverity: 0, attentionShare: 2 / 3 },
    ]);
  });

  it("excludes malformed, impossible and timezone-free dates rather than silently normalizing them", () => {
    const result = aggregateAuditTimeline([
      "invalid", "2026-02-30T12:00:00Z", "2026-09-08T12:00:00", "2026-09-08T25:00:00Z",
    ].map((occurred_at) => ({ occurred_at, severity: "ready" })));
    expect(result).toEqual({ bins: [], invalidTimestamps: 4 });
  });

  it("keeps unknown severities in event counts but withholds that date's attention share", () => {
    const result = aggregateAuditTimeline([
      { occurred_at: "2026-09-08T12:00:00Z", severity: "watch" },
      { occurred_at: "2026-09-08T12:30:00Z", severity: "unrecognized" },
    ]);
    expect(result.bins[0]).toEqual({ date: "2026-09-08", count: 2, attention: 1, unknownSeverity: 1, attentionShare: null });
  });

  it("does not fabricate missing days or a zero denominator", () => {
    expect(aggregateAuditTimeline([])).toEqual({ bins: [], invalidTimestamps: 0 });
    const result = aggregateAuditTimeline([
      { occurred_at: "2026-09-01T12:00:00Z", severity: "ready" },
      { occurred_at: "2026-09-08T12:00:00Z", severity: "ready" },
    ]);
    expect(result.bins.map((bin) => [bin.date, bin.attentionShare])).toEqual([["2026-09-01", 0], ["2026-09-08", 0]]);
  });
});

describe("console time zone audit activity aggregation", () => {
  it("bins by the calendar date of the given zone, not UTC", () => {
    // 22:30Z on the 7th is already 00:30 on the 8th in Rome (UTC+2 in September).
    const events = [
      { occurred_at: "2026-09-07T22:30:00Z", severity: "ready" },
      { occurred_at: "2026-09-08T12:00:00Z", severity: "watch" },
    ];
    expect(aggregateAuditTimeline(events, "Europe/Rome").bins.map((bin) => [bin.date, bin.count])).toEqual([
      ["2026-09-08", 2],
    ]);
    expect(aggregateAuditTimeline(events, "UTC").bins.map((bin) => [bin.date, bin.count])).toEqual([
      ["2026-09-07", 1],
      ["2026-09-08", 1],
    ]);
  });

  it("gives a DST day its real length, as the audit heatmap does", () => {
    // Rome leaves summer time on 25 Oct 2026, so that date spans 25 hours.
    const events = [
      { occurred_at: "2026-10-24T22:30:00Z", severity: "ready" }, // 00:30 CEST on the 25th
      { occurred_at: "2026-10-25T01:30:00Z", severity: "ready" }, // 02:30 CET, the repeated hour
      { occurred_at: "2026-10-25T22:30:00Z", severity: "ready" }, // 23:30 CET on the 25th
      { occurred_at: "2026-10-25T23:30:00Z", severity: "ready" }, // 00:30 CET on the 26th
    ];
    const { bins } = aggregateAuditTimeline(events, "Europe/Rome");
    expect(bins.map((bin) => [bin.date, bin.count])).toEqual([["2026-10-25", 3], ["2026-10-26", 1]]);

    const day = activityDateInterval("2026-10-25", "Europe/Rome");
    expect(day).toEqual({ start: Date.parse("2026-10-24T22:00:00Z"), end: Date.parse("2026-10-25T23:00:00Z") });
    expect(day.end - day.start).toBe(25 * 3_600_000);
    expect(events.filter(({ occurred_at }) => {
      const at = Date.parse(occurred_at);
      return at >= day.start && at < day.end;
    })).toHaveLength(bins[0].count);
  });

  it("labels the zone it bins in", () => {
    render(<ActivityTimeline
      events={[
        { ...auditEventsFixture.events[0], occurred_at: "2026-09-07T22:30:00Z", severity: "watch" as const },
        { ...auditEventsFixture.events[1], occurred_at: "2026-09-08T13:00:00Z", severity: "ready" as const },
      ]}
      timeZone="Europe/Rome"
    />);
    expect(screen.getByRole("status")).toHaveTextContent("2 returned events · 1 Europe/Rome date");
    expect(screen.getByText(/Only one Europe\/Rome date in this window/)).toBeInTheDocument();
    expect(screen.getByText("2026-09-08 Europe/Rome")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^2026-09-08 Europe\/Rome: 2 events/ })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /^Choose a Europe\/Rome date/ })).toBeInTheDocument();
  });
});

describe("ActivityTimeline evidence", () => {
  const interactiveEvents = [
    { ...auditEventsFixture.events[0], occurred_at: "2026-09-08T12:00:00Z", severity: "watch" as const },
    { ...auditEventsFixture.events[1], occurred_at: "2026-09-08T13:00:00Z", severity: "ready" as const },
    { ...auditEventsFixture.events[2], occurred_at: "2026-09-09T12:00:00Z", severity: "action_required" as const },
  ];

  it("previews a hovered date, pins a clicked date and resets to the unchanged returned window", async () => {
    const user = userEvent.setup();
    render(<ActivityTimeline events={interactiveEvents} />);
    const first = screen.getByRole("button", { name: /2026-09-08 UTC: 2 events; 50% attention/ });
    const second = screen.getByRole("button", { name: /2026-09-09 UTC: 1 event; 100% attention/ });
    expect(screen.getByRole("status")).toHaveTextContent("3 returned events · 2 UTC dates");
    await user.hover(first);
    expect(screen.getByRole("status")).toHaveTextContent("2 events · 50% attention · 1/2");
    await user.unhover(first);
    expect(screen.getByRole("status")).toHaveTextContent("3 returned events · 2 UTC dates");
    await user.click(second);
    expect(second).toHaveAttribute("aria-pressed", "true");
    await user.hover(first);
    expect(screen.getByRole("status")).toHaveTextContent("2 events · 50% attention · 1/2");
    await user.unhover(first);
    expect(screen.getByRole("status")).toHaveTextContent("1 event · 100% attention · 1/1");
    await user.click(screen.getByRole("button", { name: "Reset" }));
    expect(second).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("status")).toHaveTextContent("3 returned events · 2 UTC dates");
  });

  it("supports arrow navigation, keyboard selection and clearing without hover", async () => {
    const user = userEvent.setup();
    render(<ActivityTimeline events={interactiveEvents} />);
    const first = screen.getByRole("button", { name: /2026-09-08 UTC: 2 events/ });
    const second = screen.getByRole("button", { name: /2026-09-09 UTC: 1 event/ });
    await user.tab();
    expect(first).toHaveFocus();
    await user.keyboard("{ArrowRight}{Enter}");
    expect(second).toHaveFocus();
    expect(second).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("100% attention · 1/1");
    await user.keyboard("{Escape}");
    expect(second).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("status")).toHaveTextContent("3 returned events");
    await user.keyboard("{Home} ");
    expect(first).toHaveFocus();
    expect(first).toHaveAttribute("aria-pressed", "true");
  });

  it("selects and deselects a date with touch taps", async () => {
    const user = userEvent.setup();
    render(<ActivityTimeline events={interactiveEvents} />);
    const date = screen.getByRole("button", { name: /2026-09-08 UTC: 2 events/ });
    const tap = () => user.pointer([{ keys: "[TouchA>]", target: date }, { keys: "[/TouchA]", target: date }]);
    await tap();
    expect(date).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("50% attention · 1/2");
    await tap();
    expect(date).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("status")).toHaveTextContent("3 returned events");
  });

  it("shows the single observed date, denominator and share without relying on hover", () => {
    render(<ActivityTimeline events={auditEventsFixture.events.map((event, index) => ({ ...event, occurred_at: "2026-09-08T12:00:00Z", severity: index === 0 ? "watch" : "ready" }))} />);
    expect(screen.getByText(/Only one UTC date in this window/)).toBeInTheDocument();
    expect(screen.getByText("Daily values")).toBeInTheDocument();
    expect(screen.getByText("2026-09-08 UTC")).toBeInTheDocument();
    expect(screen.getByText("4 events")).toBeInTheDocument();
    expect(screen.getByText("1/4 attention · 25%")).toBeInTheDocument();
  });

  it("reports excluded timestamps visibly instead of presenting an empty chart as zero activity", () => {
    render(<ActivityTimeline events={[{ ...auditEventsFixture.events[0], occurred_at: "invalid" }]} />);
    expect(screen.getByText("No valid timestamps to plot.")).toBeInTheDocument();
    expect(screen.getByText(/1 event has an invalid timestamp/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Daily activity values")).not.toBeInTheDocument();
  });
});
