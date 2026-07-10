import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-full px-6 py-3 text-[15px] font-medium transition-all duration-300 select-none disabled:cursor-not-allowed disabled:opacity-55";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-navy text-white hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none",
  secondary:
    "border border-mist bg-surface text-ink hover:border-signal/50 hover:text-signal dark:border-white/20 dark:hover:border-signal/60",
  destructive:
    "border border-danger/40 bg-surface text-danger hover:border-danger hover:bg-danger/8 dark:border-danger/50 dark:bg-transparent dark:hover:bg-danger/12",
  ghost: "px-3 py-2 text-ink hover:text-signal",
};

export function Button({ variant = "primary", className, children, ...rest }: ButtonProps) {
  return (
    <button className={cn(base, variants[variant], className)} type="button" {...rest}>
      {children}
    </button>
  );
}
