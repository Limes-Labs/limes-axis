import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, buttonVariants } from "./button";
import { Disclosure, MobileDisclosure } from "./disclosure";
import { PageHeader } from "./page-header";
import { TabsList, Tabs, TabsTrigger } from "./tabs";

describe("MobileDisclosure", () => {
  it("collapses a section below md only, through CSS, so markup never depends on the viewport", () => {
    render(
      <MobileDisclosure title="Platform posture">
        <p>Posture cards</p>
      </MobileDisclosure>,
    );

    const trigger = screen.getByRole("button", { name: "Platform posture" });
    const content = screen.getByText("Posture cards").parentElement as HTMLElement;
    // The trigger exists only below md; from md the section is always shown.
    expect(trigger).toHaveClass("md:hidden", "min-h-11");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveAttribute("aria-controls", content.id);
    expect(content).toHaveClass("max-md:hidden");
    expect(content).not.toHaveAttribute("hidden");

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(content).not.toHaveClass("max-md:hidden");
  });
});

describe("touch targets on coarse pointers", () => {
  it("raises every Button variant and size to 44px without changing desktop height", () => {
    render(<Button size="sm">Retry</Button>);
    const button = screen.getByRole("button", { name: "Retry" });
    expect(button).toHaveClass("h-8", "pointer-coarse:min-h-11");
    expect(buttonVariants({ size: "sm", variant: "link" })).toContain("pointer-coarse:min-h-11");
  });

  it("raises disclosure and tab triggers", () => {
    render(
      <>
        <Disclosure title="Technical details">detail</Disclosure>
        <Tabs defaultValue="a">
          <TabsList aria-label="Views">
            <TabsTrigger value="a">Category</TabsTrigger>
          </TabsList>
        </Tabs>
      </>,
    );
    expect(screen.getByRole("button", { name: "Technical details" })).toHaveClass("pointer-coarse:min-h-11");
    expect(screen.getByRole("tab", { name: "Category" })).toHaveClass("pointer-coarse:min-h-11");
  });

  it("sizes the shared icon button to 44px under a coarse pointer", () => {
    const css = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8");
    const rule = css.match(/@media \(pointer: coarse\) \{\s*\.icon-button \{([^}]+)\}/);
    expect(rule?.[1]).toContain("width: 44px");
    expect(rule?.[1]).toContain("height: 44px");
  });
});

describe("compact page header on phones", () => {
  it("keeps the title and drops the description below sm", () => {
    render(<PageHeader description="Turn connected business data into actions." title="Overview" />);
    expect(screen.getByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("Turn connected business data into actions.")).toHaveClass("max-sm:hidden");
  });
});
