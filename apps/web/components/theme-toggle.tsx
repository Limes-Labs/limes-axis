"use client";

import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/providers/theme-provider";

/**
 * Simple light/dark toggle for the topbar icon cluster. The icons are driven
 * by CSS (`dark:` variant) so server and client markup always match, even
 * before the provider hydrates.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <button
      aria-label="Toggle color theme"
      className="ops-icon-button"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      title="Toggle color theme"
      type="button"
    >
      <Sun className="dark:hidden" size={17} />
      <Moon className="hidden dark:block" size={17} />
    </button>
  );
}
