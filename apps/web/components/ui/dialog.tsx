"use client";

import { useRef, type ComponentProps, type RefObject } from "react";

import { X } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";
import { useStrings } from "@/providers/locale-provider";

/*
 * Thin Radix Dialog wrapper styled with the console tokens: midnight-tinted
 * blurred overlay, rounded surface panel with the hairline border.
 */

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogClose = DialogPrimitive.Close;

export function DialogOverlay({
  className,
  ...props
}: ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      className={cn("fixed inset-0 z-50 bg-navy/55 backdrop-blur-sm", className)}
      {...props}
    />
  );
}

export interface DialogContentProps extends ComponentProps<typeof DialogPrimitive.Content> {
  /**
   * Where focus lands on close when the element that opened the dialog is no
   * longer in the document (e.g. the option button a decision replaced).
   */
  returnFocusRef?: RefObject<HTMLElement | null>;
}

export function DialogContent({
  className,
  children,
  onOpenAutoFocus,
  onCloseAutoFocus,
  returnFocusRef,
  ...props
}: DialogContentProps) {
  const strings = useStrings();
  // Radix returns focus only to a <DialogTrigger>. Most console dialogs are
  // controlled and opened from a plain button, so without this focus fell to
  // <body> on close (WCAG 2.4.3). Capture the opener as the dialog mounts —
  // before Radix moves focus inside — and restore it on close.
  const openerRef = useRef<HTMLElement | null>(null);

  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        onOpenAutoFocus={(event) => {
          const active = document.activeElement;
          openerRef.current = active instanceof HTMLElement && active !== document.body ? active : null;
          onOpenAutoFocus?.(event);
        }}
        onCloseAutoFocus={(event) => {
          onCloseAutoFocus?.(event);
          if (event.defaultPrevented) {
            return;
          }
          const opener = openerRef.current;
          const target = opener?.isConnected ? opener : returnFocusRef?.current;
          if (target?.isConnected) {
            event.preventDefault();
            target.focus();
          }
        }}
        className={cn(
          "fixed top-1/2 left-1/2 z-50 grid w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2",
          // Without a height cap, tall content (the connector wizard's CSV step
          // is a select + file field + issue list + a 5-row preview table) runs
          // off both edges of a phone viewport and takes the footer buttons —
          // Next/Register — out of reach entirely. The body scrolls rather than
          // the whole panel, so the close button stays pinned.
          "max-h-[calc(100dvh-2rem)] grid-rows-[minmax(0,1fr)]",
          "rounded-2xl border border-line bg-surface p-6 shadow-[var(--shadow-modal)]",
          "dark:border-white/10 dark:shadow-[0_24px_60px_rgb(0_0_0/0.5)]",
          className,
        )}
        {...props}
      >
        <div className="grid min-h-0 content-start gap-4 overflow-y-auto overscroll-contain">
          {children}
        </div>
        {/* `absolute!`: .icon-button sets position: relative and would otherwise win. */}
        <DialogPrimitive.Close aria-label={strings.ui.common.close} className="icon-button absolute! top-3 right-3">
          <X aria-hidden="true" size={16} />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPortal>
  );
}

export function DialogHeader({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex min-w-0 flex-col gap-1.5 pr-8", className)} {...props} />;
}

export function DialogFooter({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex flex-wrap items-center justify-end gap-2", className)} {...props} />;
}

export function DialogTitle({
  className,
  ...props
}: ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      className={cn("font-display m-0 text-lg text-ink", className)}
      {...props}
    />
  );
}

export function DialogDescription({
  className,
  ...props
}: ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      className={cn("m-0 text-sm leading-snug text-muted", className)}
      {...props}
    />
  );
}
