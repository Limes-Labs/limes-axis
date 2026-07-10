"use client";

import type { ComponentProps } from "react";

import { Tooltip as TooltipPrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof TooltipPrimitive.Content>) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        className={cn(
          "z-50 max-w-xs rounded-xl border border-line bg-surface px-3 py-2 text-xs leading-snug text-ink",
          "shadow-[0_12px_32px_rgb(4_18_46/0.18)] dark:border-white/10 dark:shadow-[0_12px_32px_rgb(0_0_0/0.45)]",
          className,
        )}
        sideOffset={sideOffset}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}
