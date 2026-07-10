"use client";

import { useEffect, useRef, useState, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface RevealProps extends HTMLAttributes<HTMLDivElement> {
  /** Stagger delay in milliseconds, applied via `--reveal-delay`. */
  delay?: number;
  children: ReactNode;
}

/**
 * Scroll-reveal wrapper for the brand's `.reveal` utility: the block fades and
 * lifts in once it enters the viewport. Respects `prefers-reduced-motion`
 * through the global CSS block (which forces `.reveal` fully visible).
 */
export function Reveal({ delay = 0, className, children, ...rest }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const element = ref.current;

    if (!element || typeof IntersectionObserver === "undefined") {
      setRevealed(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const shouldReveal = entries.some(
          // Reveal when entering the viewport — or when already above it,
          // so jump-scrolls (keyboard End, anchor links) don't skip sections.
          (entry) => entry.isIntersecting || entry.boundingClientRect.bottom < 0,
        );

        if (shouldReveal) {
          setRevealed(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );

    observer.observe(element);

    return () => observer.disconnect();
  }, []);

  return (
    <div
      className={cn("reveal", revealed && "revealed", className)}
      ref={ref}
      style={delay ? ({ "--reveal-delay": `${delay}ms` } as React.CSSProperties) : undefined}
      {...rest}
    >
      {children}
    </div>
  );
}
