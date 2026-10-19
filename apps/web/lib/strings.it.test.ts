import { describe, expect, it } from "vitest";

import { glossary, strings } from "./strings";
import { glossaryIt, stringsIt } from "./strings.it";

/*
 * Values that are correctly identical in English and Italian: product names,
 * protocol and acronym labels, and the terms Italian IT practice keeps in
 * English. Anything else that matches the English copy is an untranslated
 * string.
 */
const ENGLISH_ALLOWLIST = new Set([
  "—",
  "Audit",
  "Audience",
  "Axis Console",
  "Batch",
  "Bearer token",
  "Console",
  "Demo",
  "Digest",
  "Egress",
  "Endpoint",
  "Governance",
  "Hosting",
  "Lease",
  "Limes Axis",
  "Menu",
  "No",
  "Object store",
  "Policy",
  "Provider",
  "Replay",
  "Runtime",
  "Schema",
  "Snapshot",
  "Stewardship",
  "Tenant",
  "Workflow",
]);

/* Leaf paths whose value is data rather than copy (a URL, a sample key). */
const IDENTICAL_PATHS = new Set([
  "commandMenu.docs.href",
  "tenantVocabulary.fields.domainKeyPlaceholder",
  "ui.rootLayout.titleTemplate",
]);

/* Template functions whose output stays identical for any sample input. */
const IDENTICAL_TEMPLATES = new Set([
  "connectors.manifestImport.applyEndpointPaths",
  "models.reference.routeDetail.latencyValue",
  "models.reference.routeDetail.tokenSplit",
  "ui.common.revisionNumber",
  "ui.common.revisionVersion",
  "ui.overviewActivityTimeline.dateInZone",
  "ui.detailPages.policyMetaTitle",
  "ui.detailPages.tenantMetaTitle",
]);

type Leaf = { path: string; value: unknown };

function leaves(node: unknown, path = ""): Leaf[] {
  if (node !== null && typeof node === "object") {
    return Object.entries(node).flatMap(([key, value]) =>
      leaves(value, path ? `${path}.${key}` : key),
    );
  }
  return [{ path, value: node }];
}

function lookup(root: unknown, path: string): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (node, key) => (node !== null && typeof node === "object" ? (node as Record<string, unknown>)[key] : undefined),
      root,
    );
}

/* Call a template with sample arguments that fit its parameter types. */
function sample(template: (...args: never[]) => unknown, value: number): unknown {
  const call = template as (...args: unknown[]) => unknown;
  try {
    return call(...Array.from({ length: template.length }, () => value));
  } catch {
    return call(...Array.from({ length: template.length }, () => [String(value)]));
  }
}

function placeholders(value: string): string[] {
  return [...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
}

function compare(english: unknown, italian: unknown) {
  const untranslated: string[] = [];
  const empty: string[] = [];
  const placeholderDrift: string[] = [];
  const missing: string[] = [];

  for (const { path, value } of leaves(english)) {
    const translated = lookup(italian, path);
    if (translated === undefined) {
      missing.push(path);
      continue;
    }

    if (typeof value === "function") {
      expect(typeof translated, path).toBe("function");
      for (const input of [1, 2]) {
        const en = sample(value as never, input);
        const it = sample(translated as never, input);
        if (typeof it !== "string" || it.trim() === "") {
          empty.push(`${path}(${input})`);
        } else if (it === en && !IDENTICAL_TEMPLATES.has(path)) {
          untranslated.push(`${path}(${input}): ${it}`);
        }
      }
      continue;
    }

    if (typeof value !== "string") {
      continue;
    }

    if (typeof translated !== "string" || translated.trim() === "") {
      empty.push(path);
      continue;
    }
    if (translated === value && !ENGLISH_ALLOWLIST.has(value) && !IDENTICAL_PATHS.has(path)) {
      untranslated.push(`${path}: ${value}`);
    }
    if (placeholders(value).join() !== placeholders(translated).join()) {
      placeholderDrift.push(path);
    }
  }

  return { empty, missing, placeholderDrift, untranslated };
}

describe("Italian catalogue", () => {
  it("translates every console string, keeping only allowlisted terms in English", () => {
    const result = compare(strings, stringsIt);
    expect(result.missing).toEqual([]);
    expect(result.empty).toEqual([]);
    expect(result.untranslated).toEqual([]);
    expect(result.placeholderDrift).toEqual([]);
  });

  it("translates every glossary entry", () => {
    const result = compare(glossary, glossaryIt);
    expect(result).toEqual({ empty: [], missing: [], placeholderDrift: [], untranslated: [] });
  });

  it("keeps plural forms in the template functions", () => {
    expect(stringsIt.connectors.sourceDiscovery.discoveredTitle(1)).toBe("Rilevata 1 tabella");
    expect(stringsIt.connectors.sourceDiscovery.discoveredTitle(3)).toBe("Rilevate 3 tabelle");
    expect(stringsIt.settings.gatesSummary(1)).toMatch(/^1 requisito richiede/);
    expect(stringsIt.settings.gatesSummary(4)).toMatch(/^4 requisiti richiedono/);
    expect(stringsIt.connectors.list.observedRecords(12000)).toBe("12.000 record osservati");
  });

  it("only allowlists terms that some English value actually uses", () => {
    const englishValues = new Set(
      [...leaves(strings), ...leaves(glossary)].map(({ value }) => value),
    );
    expect([...ENGLISH_ALLOWLIST].filter((term) => !englishValues.has(term))).toEqual([]);
  });
});
