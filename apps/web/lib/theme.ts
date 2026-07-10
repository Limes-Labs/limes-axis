export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

/** localStorage key shared by the provider and the no-FOUC inline script. */
export const THEME_STORAGE_KEY = "axis-theme";

export const DEFAULT_THEME_PREFERENCE: ThemePreference = "system";

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

/** Parse a persisted preference, falling back to "system" for unknown input. */
export function parseThemePreference(value: string | null): ThemePreference {
  return isThemePreference(value) ? value : DEFAULT_THEME_PREFERENCE;
}

/**
 * Resolve the stored preference to the concrete theme that should be applied
 * to `document.documentElement.dataset.theme`.
 */
export function resolveTheme(stored: string | null, systemDark: boolean): ResolvedTheme {
  const preference = parseThemePreference(stored);

  if (preference === "system") {
    return systemDark ? "dark" : "light";
  }

  return preference;
}
