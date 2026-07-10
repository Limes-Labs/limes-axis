"use client";

import type { ComponentProps } from "react";

import { Command as CommandPrimitive } from "cmdk";
import { Search } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/cn";

/* cmdk wrapper styled with the console tokens. */

export function Command({ className, ...props }: ComponentProps<typeof CommandPrimitive>) {
  return (
    <CommandPrimitive
      className={cn(
        "flex w-full min-w-0 flex-col overflow-hidden rounded-2xl border border-line bg-surface text-ink",
        "dark:border-white/10",
        className,
      )}
      {...props}
    />
  );
}

export function CommandInput({
  className,
  ...props
}: ComponentProps<typeof CommandPrimitive.Input>) {
  return (
    <div className="flex items-center gap-2 border-b border-line px-3.5 dark:border-white/10">
      <Search aria-hidden="true" className="shrink-0 text-muted" size={15} />
      <CommandPrimitive.Input
        className={cn(
          "h-11 w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-muted/70",
          "disabled:cursor-not-allowed disabled:opacity-55",
          className,
        )}
        {...props}
      />
    </div>
  );
}

export function CommandList({ className, ...props }: ComponentProps<typeof CommandPrimitive.List>) {
  return (
    <CommandPrimitive.List
      className={cn("max-h-72 overflow-x-hidden overflow-y-auto p-1.5", className)}
      {...props}
    />
  );
}

export function CommandEmpty({
  className,
  ...props
}: ComponentProps<typeof CommandPrimitive.Empty>) {
  return (
    <CommandPrimitive.Empty
      className={cn("py-6 text-center text-sm text-muted", className)}
      {...props}
    />
  );
}

export function CommandGroup({
  className,
  ...props
}: ComponentProps<typeof CommandPrimitive.Group>) {
  return (
    <CommandPrimitive.Group
      className={cn(
        "overflow-hidden [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5",
        "[&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-[10.5px] [&_[cmdk-group-heading]]:font-medium",
        "[&_[cmdk-group-heading]]:tracking-[0.16em] [&_[cmdk-group-heading]]:text-muted [&_[cmdk-group-heading]]:uppercase",
        className,
      )}
      {...props}
    />
  );
}

export function CommandSeparator({
  className,
  ...props
}: ComponentProps<typeof CommandPrimitive.Separator>) {
  return (
    <CommandPrimitive.Separator
      className={cn("-mx-1.5 my-1.5 h-px bg-line dark:bg-white/10", className)}
      {...props}
    />
  );
}

export function CommandItem({ className, ...props }: ComponentProps<typeof CommandPrimitive.Item>) {
  return (
    <CommandPrimitive.Item
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-ink select-none",
        "data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-55",
        "data-[selected=true]:bg-tint-100 data-[selected=true]:text-signal",
        className,
      )}
      {...props}
    />
  );
}

export interface CommandDialogProps extends ComponentProps<typeof Dialog> {
  /** Accessible dialog title (visually hidden). */
  title?: string;
}

export function CommandDialog({ title = "Command menu", children, ...props }: CommandDialogProps) {
  return (
    <Dialog {...props}>
      <DialogContent
        aria-describedby={undefined}
        className="top-[18%] max-w-xl translate-y-0 gap-0 overflow-hidden p-0"
      >
        <DialogTitle className="sr-only">{title}</DialogTitle>
        <Command className="rounded-2xl border-0">{children}</Command>
      </DialogContent>
    </Dialog>
  );
}
