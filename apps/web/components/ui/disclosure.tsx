"use client";

import { useId, useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { Collapsible as CollapsiblePrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

export type DisclosureVariant = "card" | "plain";
export type DisclosureSize = "sm" | "md";

export interface DisclosureProps {
  title: ReactNode;
  children: ReactNode;
  /**
   * `card` frames the disclosure as its own surface (create forms, notes);
   * `plain` sits inside an existing card (technical details, row detail).
   * Both share the same trigger: a chevron button that rotates when open.
   */
  variant?: DisclosureVariant;
  /** `sm` is the quiet 12px trigger used for technical details. */
  size?: DisclosureSize;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /**
   * Keep the content mounted (hidden) while closed, so a half-typed form
   * draft survives collapsing it (the default, as with a native `<details>`).
   * Detail that should leave the DOM while closed passes `false`.
   */
  keepMounted?: boolean;
  className?: string;
  contentClassName?: string;
}

const triggerSizes: Record<DisclosureSize, string> = {
  sm: "gap-1 text-xs font-medium text-muted hover:text-ink [&_svg]:size-3.5",
  md: "gap-1.5 text-sm font-medium text-ink [&_svg]:size-4",
};

/**
 * The console's one disclosure pattern. It used to come in two flavours — a
 * native `<details>` with the browser triangle and a chevron `<button>` — that
 * looked and announced differently. This is the button flavour: it is exposed
 * as a button with `aria-expanded`, and its chevron is the only open/closed cue.
 */
export function Disclosure({
  title,
  children,
  variant = "card",
  size = "md",
  defaultOpen,
  open,
  onOpenChange,
  keepMounted = true,
  className,
  contentClassName,
}: DisclosureProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen ?? false);
  const isOpen = open ?? uncontrolledOpen;
  const changeOpen = (next: boolean) => {
    if (open === undefined) setUncontrolledOpen(next);
    onOpenChange?.(next);
  };

  return (
    <CollapsiblePrimitive.Root
      className={cn(
        "group/disclosure min-w-0",
        variant === "card" && "rounded-2xl border border-line bg-surface p-4 dark:border-white/10",
        className,
      )}
      data-disclosure=""
      onOpenChange={changeOpen}
      open={isOpen}
    >
      <CollapsiblePrimitive.Trigger
        className={cn(
          "inline-flex min-h-6 max-w-full min-w-0 cursor-pointer items-center bg-transparent p-0 text-left transition-colors pointer-coarse:min-h-11",
          triggerSizes[size],
        )}
        type="button"
      >
        <ChevronRight
          aria-hidden="true"
          className="shrink-0 text-muted transition-transform duration-150 group-data-[state=open]/disclosure:rotate-90 motion-reduce:transition-none"
        />
        <span className="min-w-0 break-words">{title}</span>
      </CollapsiblePrimitive.Trigger>
      <CollapsiblePrimitive.Content
        className={cn(
          "min-w-0",
          variant === "card" ? "mt-4 grid gap-3" : size === "sm" ? "mt-2" : "mt-3",
          contentClassName,
        )}
        // A force-mounted panel is always "present" to Radix, so it is hidden
        // here; the attribute also takes it out of the accessibility tree.
        forceMount={keepMounted ? true : undefined}
        hidden={keepMounted ? !isOpen : undefined}
      >
        {children}
      </CollapsiblePrimitive.Content>
    </CollapsiblePrimitive.Root>
  );
}

/**
 * The same disclosure, applied only below the `md` breakpoint: on a phone the
 * section starts collapsed behind a full-width trigger; from `md` up the
 * trigger is not rendered and the section is always shown. The breakpoint is
 * pure CSS, so server and client markup match and nothing flashes on
 * hydration. Content stays mounted (its queries keep running) while collapsed.
 */
export function MobileDisclosure({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const contentId = useId();

  return (
    <div className={cn("group/disclosure grid min-w-0 gap-3", className)} data-mobile-disclosure="" data-state={open ? "open" : "closed"}>
      <button
        aria-controls={contentId}
        aria-expanded={open}
        className={cn(
          "flex min-h-11 w-full min-w-0 cursor-pointer items-center justify-between gap-2 rounded-2xl border border-line bg-surface px-4 text-left md:hidden dark:border-white/10",
          triggerSizes.md,
        )}
        data-mobile-disclosure-trigger=""
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className="min-w-0 break-words">{title}</span>
        <ChevronRight
          aria-hidden="true"
          className="shrink-0 text-muted transition-transform duration-150 group-data-[state=open]/disclosure:rotate-90 motion-reduce:transition-none"
        />
      </button>
      <div className={cn("grid min-w-0 gap-4", !open && "max-md:hidden")} id={contentId}>
        {children}
      </div>
    </div>
  );
}
