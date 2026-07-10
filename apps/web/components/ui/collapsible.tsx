"use client";

import type { ComponentProps } from "react";

import { Collapsible as CollapsiblePrimitive } from "radix-ui";

import { cn } from "@/lib/cn";

export const Collapsible = CollapsiblePrimitive.Root;
export const CollapsibleTrigger = CollapsiblePrimitive.Trigger;

export function CollapsibleContent({
  className,
  ...props
}: ComponentProps<typeof CollapsiblePrimitive.Content>) {
  return <CollapsiblePrimitive.Content className={cn("min-w-0", className)} {...props} />;
}
