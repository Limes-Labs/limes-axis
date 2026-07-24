/**
 * The console promises to show only recorded evidence, so a surface must be
 * able to say *which* of these it is showing. `useAxisQuery` keeps the last
 * good payload when a refresh fails, which is why "stale" is a distinct state
 * rather than a flavour of "unavailable": the numbers on screen are real, they
 * are just no longer current.
 */
export type AxisSource = "loading" | "api" | "tenant_not_found" | "unavailable";

export type SourceState = "loading" | "live" | "stale" | "unavailable";

export function deriveSourceState(source: AxisSource, hasData: boolean): SourceState {
  if (source === "api") {
    return "live";
  }

  if (source === "tenant_not_found" || source === "unavailable") {
    return hasData ? "stale" : "unavailable";
  }

  return "loading";
}
