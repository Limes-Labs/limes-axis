import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, buttonVariants } from "./button";
import { Disclosure } from "./disclosure";
import { MetricStrip } from "./metric-strip";
import { StatCard } from "./stat-card";

function componentSources(): Array<{ path: string; source: string }> {
  const roots = [join(process.cwd(), "components"), join(process.cwd(), "app")];
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) walk(path);
      else if (path.endsWith(".tsx") && !path.includes(".test.")) files.push(path);
    }
  };
  roots.forEach(walk);
  return files.map((path) => ({
    path: relative(process.cwd(), path),
    source: readFileSync(path, "utf8"),
  }));
}

describe("one call-to-action vocabulary", () => {
  it("exposes the Button variants as classes for links and shared constants", () => {
    render(
      <>
        <Button>Save</Button>
        <a className={buttonVariants({ variant: "secondary" })} href="https://idp.example/logout">Policies</a>
      </>,
    );

    // A link styled as a CTA and a real button share the same base and size.
    const button = screen.getByRole("button", { name: "Save" });
    const link = screen.getByRole("link", { name: "Policies" });
    for (const element of [button, link]) {
      expect(element).toHaveClass("inline-flex", "rounded-lg", "h-9", "font-medium");
    }
    expect(button).toHaveClass("bg-navy");
    expect(link).toHaveClass("border-line");
  });

  it("renders the text CTA without the control box", () => {
    render(<a className={buttonVariants({ size: "sm", variant: "link" })} href="/agents">Open agents</a>);

    const link = screen.getByRole("link", { name: "Open agents" });
    expect(link).toHaveClass("text-signal", "min-h-6");
    expect(link).not.toHaveClass("h-8");
    expect(link).not.toHaveClass("px-2.5");
  });

  it("keeps a disabled control hoverable so its title can explain why", () => {
    render(<Button disabled title="Sign in to run this">Run</Button>);

    const button = screen.getByRole("button", { name: "Run" });
    expect(button).toBeDisabled();
    expect(button).toHaveClass("disabled:cursor-not-allowed");
    expect(button.className).not.toContain("pointer-events-none");
    expect(button).toHaveAttribute("title", "Sign in to run this");
  });

  it("leaves no hand-rolled pill CTA in the console", () => {
    const offenders = componentSources()
      .filter(({ source }) =>
        /rounded-full bg-navy|rounded-full border border-mist|rounded-xl bg-signal px-4|tracking-\[0\.12em\] text-signal uppercase/
          .test(source))
      .map(({ path }) => path);

    expect(offenders).toEqual([]);
  });
});

describe("one disclosure pattern", () => {
  it("announces a button with aria-expanded and keeps a draft mounted by default", () => {
    render(
      <Disclosure title="Create policy">
        <label>
          Policy name
          <input defaultValue="" />
        </label>
      </Disclosure>,
    );

    const trigger = screen.getByRole("button", { name: "Create policy" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    // Mounted but hidden, as a native <details> kept it.
    expect(screen.queryByRole("textbox", { name: "Policy name" })).not.toBeInTheDocument();
    expect(document.querySelector("input")).not.toBeNull();

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const input = screen.getByRole("textbox", { name: "Policy name" });
    fireEvent.change(input, { target: { value: "Expedite cap" } });

    fireEvent.click(trigger);
    fireEvent.click(trigger);
    expect(screen.getByRole("textbox", { name: "Policy name" })).toHaveValue("Expedite cap");
  });

  it("can unmount read-only detail while closed", () => {
    render(
      <Disclosure keepMounted={false} size="sm" title="Technical details" variant="plain">
        <p>Endpoint /operations/overview</p>
      </Disclosure>,
    );

    expect(screen.queryByText("Endpoint /operations/overview")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Technical details" }));
    expect(screen.getByText("Endpoint /operations/overview")).toBeVisible();
  });

  it("leaves no native <details> disclosure in the console", () => {
    const offenders = componentSources()
      // A backtick-quoted `<details>` in a comment is prose, not markup.
      .filter(({ source }) => /[^`]<details[\s>]/.test(source))
      .map(({ path }) => path);

    expect(offenders).toEqual([]);
  });
});

describe("one stat card", () => {
  it("renders label, value, detail, aside and footer as a list item", () => {
    render(
      <div role="list">
        <StatCard
          aside={<span>watch</span>}
          detail="Persisted operations snapshot"
          label="Open workflows"
          value="3"
          valueTestId="open-workflows"
        >
          <a href="/workflows">Open workflows</a>
        </StatCard>
      </div>,
    );

    const card = screen.getByRole("listitem");
    expect(within(card).getByText("Open workflows", { selector: "p" })).toHaveClass("eyebrow");
    expect(screen.getByTestId("open-workflows")).toHaveTextContent(/^3$/);
    expect(screen.getByTestId("open-workflows")).toHaveClass("font-display", "text-2xl");
    expect(within(card).getByText("Persisted operations snapshot")).toBeInTheDocument();
    expect(within(card).getByText("watch")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Open workflows" })).toBeInTheDocument();
  });

  it("keeps its shape while loading and sets identifiers in mono", () => {
    const { container } = render(
      <div role="list">
        <StatCard label="Agents" value={null} />
        <StatCard label="Authored by" value="actor_ops_lead" valueVariant="mono" />
      </div>,
    );

    const [loading, mono] = screen.getAllByRole("listitem");
    expect(within(loading).queryByText(/./, { selector: "p.font-display" })).toBeNull();
    expect(container.querySelectorAll("[data-stat-card]")).toHaveLength(2);
    expect(within(mono).getByText("actor_ops_lead")).toHaveClass("font-mono");
  });

  it("is what MetricStrip renders, tone cue included", () => {
    render(<MetricStrip label="Workflow metrics" metrics={[{ label: "Blocked", value: 2, tone: "action" }]} />);

    const strip = screen.getByRole("list", { name: "Workflow metrics" });
    const card = within(strip).getByRole("listitem");
    expect(card).toHaveAttribute("data-stat-card");
    expect(card).toHaveTextContent("Action required: 2");
  });
});
