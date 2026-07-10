import type { HTMLAttributes, LabelHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface FieldProps extends LabelHTMLAttributes<HTMLLabelElement> {
  /** Mono eyebrow-style field label. */
  label: ReactNode;
  children: ReactNode;
}

/**
 * Form field wrapper: a `<label>` whose caption uses the brand's mono
 * eyebrow treatment (muted, not Signal, so filled forms stay calm).
 */
export function Field({ label, className, children, ...rest }: FieldProps) {
  return (
    <label className={cn("grid min-w-0 content-start gap-1.5", className)} {...rest}>
      <span className="font-mono text-[10.5px] font-medium tracking-[0.16em] text-muted uppercase">
        {label}
      </span>
      {children}
    </label>
  );
}

/** Inline validation error in the brand's red status color. */
export function FieldError({
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLParagraphElement> & { children: ReactNode }) {
  return (
    <p className={cn("m-0 text-sm text-danger", className)} role="alert" {...rest}>
      {children}
    </p>
  );
}
