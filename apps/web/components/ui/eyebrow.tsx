import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface EyebrowProps extends HTMLAttributes<HTMLParagraphElement> {
  children: ReactNode;
}

/** Mono uppercase micro-label in Signal Blue — the brand's section marker. */
export function Eyebrow({ className, children, ...rest }: EyebrowProps) {
  return (
    <p className={cn("eyebrow m-0", className)} {...rest}>
      {children}
    </p>
  );
}
