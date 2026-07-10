import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToastProvider, useToast } from "@/components/ui/toast";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

describe("Dialog", () => {
  it("opens via trigger and closes on Escape", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger>Open dialog</DialogTrigger>
        <DialogContent>
          <DialogTitle>Confirm decision</DialogTitle>
          <DialogDescription>This action is recorded as evidence.</DialogDescription>
        </DialogContent>
      </Dialog>,
    );

    expect(screen.queryByText("Confirm decision")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open dialog" }));
    expect(await screen.findByText("Confirm decision")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByText("Confirm decision")).not.toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("switches panels on trigger click", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="one">
        <TabsList>
          <TabsTrigger value="one">One</TabsTrigger>
          <TabsTrigger value="two">Two</TabsTrigger>
        </TabsList>
        <TabsContent value="one">First panel</TabsContent>
        <TabsContent value="two">Second panel</TabsContent>
      </Tabs>,
    );

    expect(screen.getByRole("tabpanel")).toHaveTextContent("First panel");

    await user.click(screen.getByRole("tab", { name: "Two" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Second panel");
  });
});

describe("Tooltip", () => {
  it("shows content when the trigger receives keyboard focus", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger>Autonomy level</TooltipTrigger>
          <TooltipContent>How much an agent may do on its own.</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );

    expect(screen.queryByText("How much an agent may do on its own.")).not.toBeInTheDocument();

    await user.tab();
    const matches = await screen.findAllByText("How much an agent may do on its own.");
    expect(matches.length).toBeGreaterThan(0);
  });
});

describe("Collapsible", () => {
  it("toggles its content", async () => {
    const user = userEvent.setup();
    render(
      <Collapsible>
        <CollapsibleTrigger>Technical details</CollapsibleTrigger>
        <CollapsibleContent>Hidden endpoint info</CollapsibleContent>
      </Collapsible>,
    );

    expect(screen.queryByText("Hidden endpoint info")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Technical details" }));
    expect(screen.getByText("Hidden endpoint info")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Technical details" }));
    expect(screen.queryByText("Hidden endpoint info")).not.toBeInTheDocument();
  });
});

function ToastHarness() {
  const { push } = useToast();
  return (
    <button
      type="button"
      onClick={() =>
        push({
          title: "Decision recorded",
          detail: "The approval was granted.",
          tone: "positive",
          href: "/audit",
          hrefLabel: "View audit event",
        })
      }
    >
      fire toast
    </button>
  );
}

describe("Toast", () => {
  it("renders on push and auto-dismisses after 6 seconds", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastHarness />
        </ToastProvider>,
      );

      fireEvent.click(screen.getByText("fire toast"));
      expect(screen.getByText("Decision recorded")).toBeInTheDocument();
      expect(screen.getByText("The approval was granted.")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "View audit event" })).toHaveAttribute(
        "href",
        "/audit",
      );

      act(() => {
        vi.advanceTimersByTime(5999);
      });
      expect(screen.getByText("Decision recorded")).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(screen.queryByText("Decision recorded")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("can be dismissed manually before the timeout", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastHarness />
        </ToastProvider>,
      );

      fireEvent.click(screen.getByText("fire toast"));
      expect(screen.getByText("Decision recorded")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
      expect(screen.queryByText("Decision recorded")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
