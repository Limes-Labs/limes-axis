import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

import { controlClassName } from "@/components/ui/input";

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(controlClassName, "pr-8", className)} {...rest}>
      {children}
    </select>
  );
}
