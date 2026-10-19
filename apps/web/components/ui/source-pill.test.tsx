import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { stringsIt } from "@/lib/strings.it";
import { LocaleProvider } from "@/providers/locale-provider";

import { SourcePill, sourceStateLabel } from "./source-pill";

describe("SourcePill", () => {
  it("renders reference data without a live claim", () => {
    render(<SourcePill state="reference" subject="agent registry" />);

    const pill = screen.getByText("agent registry: reference scenario").closest(".status-pill");
    expect(pill).toHaveAttribute("data-source-state", "reference");
    expect(pill).toHaveClass("status-checking");
    expect(screen.queryByText("agent registry: live")).not.toBeInTheDocument();
  });

  it("renders stale as a warning regardless of the payload's former provenance", () => {
    render(<SourcePill state="stale" subject="workflow runs" />);

    const pill = screen.getByText("workflow runs: stale").closest(".status-pill");
    expect(pill).toHaveAttribute("data-source-state", "stale");
    expect(pill).toHaveClass("signal-watch");
  });

  it("keeps an empty response visually and verbally distinct from unavailability", () => {
    const { rerender } = render(<SourcePill state="empty" subject="audit ledger" />);

    let pill = screen.getByText("audit ledger: no records").closest(".status-pill");
    expect(pill).toHaveAttribute("data-source-state", "empty");
    expect(pill).toHaveClass("status-checking");

    rerender(<SourcePill state="unavailable" subject="audit ledger" />);
    pill = screen.getByText("audit ledger: unavailable").closest(".status-pill");
    expect(pill).toHaveAttribute("data-source-state", "unavailable");
    expect(pill).toHaveClass("signal-action-required");
  });

  it("composes subject and state from the active catalogue", () => {
    render(
      <LocaleProvider locale="it">
        <SourcePill state="live" subject={stringsIt.sources.subjects.agentRegistry} />
      </LocaleProvider>,
    );

    expect(screen.getByText("registro degli agenti: in tempo reale")).toBeInTheDocument();
    expect(screen.getByText("Origine dei dati:")).toHaveClass("sr-only");
    expect(sourceStateLabel("stale", stringsIt.sources.subjects.auditLedger, stringsIt)).toBe(
      "registro di audit: non aggiornato",
    );
  });
});
