/*
 * Display-name helpers for records whose API payloads carry identifiers
 * (role slugs, workflow ids, tenant ids, scopes). Operators read the display
 * name first; the raw identifier stays available as a `title` or a secondary
 * mono line, and in Inspect drawers.
 */

/** Literals a serializer may leave behind for a missing value. */
const MISSING_LITERALS = new Set(["none", "null", "undefined"]);

/** Machine prefixes on reference ids that carry no meaning for an operator. */
const IDENTIFIER_PREFIX = /^(?:wf|tenant|rel|ent|entity|act|appr|agent|pol|policy|run)_/;

/** Slug-shaped identifiers only; free text and display names pass through. */
const SLUG_IDENTIFIER = /^[a-z0-9]+(?:[-_.][a-z0-9]+)*$/;

const OPAQUE_IDENTIFIER =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$|^[0-9a-f]{16,}$/i;

/**
 * Trimmed text, or null when the value is absent, blank or one of the literal
 * strings "None", "null" and "undefined". Never render those literals.
 */
export function presentText(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const trimmed = String(value).trim();
  if (!trimmed || MISSING_LITERALS.has(trimmed.toLowerCase())) {
    return null;
  }
  return trimmed;
}

/**
 * A readable label for a slug identifier: `plant-operations-owner` becomes
 * "Plant operations owner" and `wf_supplier_delay_review` becomes "Supplier
 * delay review". UUIDs, hashes and text that is not slug-shaped are returned
 * unchanged; missing values return null.
 */
export function humanizeIdentifier(value: string | null | undefined): string | null {
  const text = presentText(value);
  if (text === null) {
    return null;
  }
  if (OPAQUE_IDENTIFIER.test(text) || !SLUG_IDENTIFIER.test(text)) {
    return text;
  }
  const words = text.replace(IDENTIFIER_PREFIX, "").split(/[-_.]+/).filter(Boolean);
  if (words.length === 0) {
    return text;
  }
  const label = words.join(" ");
  return `${label.charAt(0).toUpperCase()}${label.slice(1)}`;
}

/**
 * A permission scope such as `approvals:supply:decide` as plain words:
 * "Approvals · supply · decide".
 */
export function humanizeScope(scope: string | null | undefined): string | null {
  const text = presentText(scope);
  if (text === null) {
    return null;
  }
  const parts = text
    .split(":")
    .map((part) => part.replaceAll(/[-_]+/g, " ").trim())
    .filter(Boolean);
  if (parts.length === 0) {
    return text;
  }
  const [first, ...rest] = parts;
  return [`${first.charAt(0).toUpperCase()}${first.slice(1)}`, ...rest].join(" · ");
}

/**
 * The payload's display field when present, else the humanized identifier,
 * else the fallback. Use for owners, workflows, tenants and relations.
 */
export function displayName(
  display: string | null | undefined,
  identifier: string | null | undefined,
  fallback: string,
): string {
  return presentText(display) ?? humanizeIdentifier(identifier) ?? fallback;
}
