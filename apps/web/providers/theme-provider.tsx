"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  DEFAULT_THEME_PREFERENCE,
  THEME_STORAGE_KEY,
  parseThemePreference,
  resolveTheme,
  type ResolvedTheme,
  type ThemePreference,
} from "@/lib/theme";

type ThemeContextValue = {
  /** The operator preference, including "system". */
  theme: ThemePreference;
  /** The concrete theme applied to the document. */
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const DARK_QUERY = "(prefers-color-scheme: dark)";

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia(DARK_QUERY).matches;
}

function readStoredPreference(): ThemePreference {
  if (typeof window === "undefined") {
    return DEFAULT_THEME_PREFERENCE;
  }

  try {
    return parseThemePreference(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }
}

function applyResolvedTheme(resolved: ResolvedTheme) {
  document.documentElement.dataset.theme = resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>(readStoredPreference);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    resolveTheme(readStoredPreference(), systemPrefersDark()),
  );

  const setTheme = useCallback((next: ThemePreference) => {
    setThemeState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Storage may be unavailable (private mode); the theme still applies.
    }

    const resolved = resolveTheme(next, systemPrefersDark());
    setResolvedTheme(resolved);
    applyResolvedTheme(resolved);
  }, []);

  // Keep the document attribute in sync after hydration (the inline no-FOUC
  // script already applied the resolved theme before first paint, and the
  // useState initializers read the same sources on the client).
  useEffect(() => {
    applyResolvedTheme(resolveTheme(theme, systemPrefersDark()));
  }, [theme]);

  // Follow OS scheme changes while the preference is "system".
  useEffect(() => {
    if (theme !== "system") {
      return undefined;
    }

    const query = window.matchMedia(DARK_QUERY);
    const onChange = (event: MediaQueryListEvent) => {
      const resolved: ResolvedTheme = event.matches ? "dark" : "light";
      setResolvedTheme(resolved);
      applyResolvedTheme(resolved);
    };

    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [theme]);

  const value = useMemo(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
