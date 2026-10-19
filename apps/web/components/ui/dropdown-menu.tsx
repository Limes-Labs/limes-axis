"use client";

import type { ComponentProps } from "react";

import { Check } from "lucide-react";
import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;
export const DropdownMenuGroup = DropdownMenuPrimitive.Group;
export const DropdownMenuPortal = DropdownMenuPrimitive.Portal;
export const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup;

const itemClass = cn(
  "flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-ink outline-none select-none",
  "data-[disabled]:pointer-events-none data-[disabled]:opacity-55",
  "data-[highlighted]:bg-tint-100 data-[highlighted]:text-signal",
);

export function DropdownMenuContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        className={cn(
          "z-50 min-w-[11rem] overflow-hidden rounded-xl border border-line bg-surface p-1.5",
          "shadow-[0_16px_44px_rgb(4_18_46/0.2)] dark:border-white/10 dark:shadow-[0_16px_44px_rgb(0_0_0/0.5)]",
          className,
        )}
        sideOffset={sideOffset}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

export function DropdownMenuItem({
  className,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Item>) {
  return (
    <DropdownMenuPrimitive.Item className={cn(itemClass, className)} {...props} />
  );
}

/**
 * A `menuitemradio`: Radix exposes the choice through `aria-checked`, and the
 * check mark repeats it visually so state never rests on color alone.
 */
export function DropdownMenuRadioItem({
  className,
  children,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.RadioItem>) {
  return (
    <DropdownMenuPrimitive.RadioItem className={cn(itemClass, "pr-2", className)} {...props}>
      {children}
      <span aria-hidden="true" className="ml-auto inline-flex size-4 items-center justify-center">
        <DropdownMenuPrimitive.ItemIndicator>
          <Check size={14} />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
    </DropdownMenuPrimitive.RadioItem>
  );
}

export function DropdownMenuLabel({
  className,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Label>) {
  return (
    <DropdownMenuPrimitive.Label
      className={cn(
        "px-2.5 py-1.5 font-mono text-[10.5px] font-medium tracking-[0.16em] text-muted uppercase",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuSeparator({
  className,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return (
    <DropdownMenuPrimitive.Separator
      className={cn("-mx-1.5 my-1.5 h-px bg-line dark:bg-white/10", className)}
      {...props}
    />
  );
}
