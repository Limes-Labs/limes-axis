import { Loader2 } from "lucide-react";
import { Slot } from "radix-ui";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

import { cn } from "@/lib/cn";

/**
 * The console's one call-to-action vocabulary. `link` is the quiet text CTA
 * ("Open agents →") for cards and rows; it shares the focus, disabled and
 * icon rules of the boxed variants instead of carrying its own type style.
 */
export type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost" | "link";
/** `md` (36px) is the console control height, shared with Input and Select. */
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Render as the single child element (e.g. a `next/link`) instead of a `button`. */
  asChild?: boolean;
  /**
   * Shows a spinner and blocks further clicks. Use for any action that hits
   * the API so a slow request cannot be submitted twice.
   */
  loading?: boolean;
  ref?: Ref<HTMLButtonElement>;
  children: ReactNode;
}

const base = cn(
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg font-medium whitespace-nowrap",
  "transition-colors duration-150 select-none",
  // Disabled controls keep pointer events so a `title` can still explain why;
  // hover and press states are scoped to enabled controls instead.
  "disabled:cursor-not-allowed disabled:opacity-50",
  // Touch screens get a 44px target (WCAG 2.5.5) without changing the
  // compact desktop control height.
  "pointer-coarse:min-h-11",
  "[&_svg]:shrink-0",
);

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 gap-1 px-2.5 text-[13px] [&_svg]:size-3.5",
  md: "h-9 px-3.5 text-sm [&_svg]:size-4",
  lg: "h-10 px-5 text-sm [&_svg]:size-4",
};

/**
 * Hover shifts the same hue rather than switching color, and no variant casts
 * a glow — a console button should read as a control, not a landing-page CTA.
 */
const variants: Record<ButtonVariant, string> = {
  primary: cn(
    "bg-navy text-white not-disabled:hover:bg-navy/88 not-disabled:active:bg-navy/80",
    "dark:bg-signal dark:text-white dark:not-disabled:hover:bg-signal/85",
  ),
  secondary: cn(
    "border border-line bg-surface text-ink not-disabled:hover:border-ink/20 not-disabled:hover:bg-ink/4",
    "dark:border-white/15 dark:bg-white/5 dark:not-disabled:hover:border-white/25 dark:not-disabled:hover:bg-white/10",
  ),
  destructive: cn(
    "border border-danger/40 bg-surface text-danger not-disabled:hover:border-danger not-disabled:hover:bg-danger/8",
    "dark:border-danger/50 dark:bg-transparent dark:not-disabled:hover:bg-danger/12",
  ),
  ghost: cn("text-ink not-disabled:hover:bg-ink/6", "dark:not-disabled:hover:bg-white/10"),
  link: "text-signal underline-offset-4 not-disabled:hover:underline",
};

/** A text CTA keeps the type scale but sheds the control box. */
const linkSizes: Record<ButtonSize, string> = {
  sm: "min-h-6 gap-1 text-[13px] [&_svg]:size-3.5",
  md: "min-h-6 text-sm [&_svg]:size-4",
  lg: "min-h-6 text-sm [&_svg]:size-4",
};

/**
 * Class names for a Button variant, for elements that must stay their own
 * component (a `next/link`, `SsoSignInLink`) or for shared class constants.
 * Prefer `<Button>` wherever the element itself can be rendered by it.
 */
export function buttonVariants({
  variant = "primary",
  size = "md",
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}): string {
  return cn(base, variant === "link" ? linkSizes[size] : sizes[size], variants[variant], className);
}

export function Button({
  variant = "primary",
  size = "md",
  asChild = false,
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const classes = buttonVariants({ variant, size, className });

  if (asChild) {
    return (
      <Slot.Root className={classes} {...rest}>
        {children}
      </Slot.Root>
    );
  }

  return (
    <button
      aria-busy={loading || undefined}
      className={classes}
      disabled={disabled || loading}
      type="button"
      {...rest}
    >
      {loading ? <Loader2 aria-hidden="true" className="animate-spin" /> : null}
      {children}
    </button>
  );
}
