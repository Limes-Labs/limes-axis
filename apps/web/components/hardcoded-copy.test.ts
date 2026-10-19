import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import ts from "typescript";
import { describe, expect, it } from "vitest";

/*
 * Guards the Italian locale against English copy written straight into
 * components. User-facing text belongs in lib/strings.ts (and its Italian
 * counterpart); a sentence built around values belongs in a template
 * function there, never in JSX text next to `{expression}`.
 *
 * The scan parses every non-test .tsx under components/ and app/ and flags:
 *   - JSX text containing letters ("Showing {n} of", "{x} decision pending");
 *   - string or template literals rendered as a JSX child, including the
 *     branches of `a ? "x" : "y"`, `a ?? "x"` and `a && "x"`;
 *   - English nouns passed to `pluralize(count, "event")`;
 *   - literals in copy-bearing attributes (aria-label, title, placeholder…),
 *     against a known-debt baseline that may only shrink.
 * Text without letters (punctuation, arrows, numbers) is always allowed.
 */

const WEB_ROOT = path.resolve(import.meta.dirname, "..");
const SCANNED_DIRS = ["components", "app"];

/*
 * Exact texts that are correctly the same in every locale: protocol acronyms
 * and the product name. Keep this list short; anything else is copy.
 */
const ALLOWED_TEXT = new Set(["API", "Limes Axis"]);

/** HTTP methods and API paths are technical identifiers, not copy. */
function withoutTechnicalTokens(text: string): string {
  return text
    .replace(/\b(?:GET|POST|PUT|PATCH|DELETE)\b/g, "")
    .replace(/\/[\w./{}:-]*/g, "");
}

function isCopy(text: string): boolean {
  const trimmed = text.replace(/\s+/g, " ").trim();
  if (!trimmed || ALLOWED_TEXT.has(trimmed)) return false;
  return /\p{L}/u.test(withoutTechnicalTokens(trimmed));
}

/** Attributes whose value is read or announced to the user. */
const COPY_ATTRIBUTES = new Set([
  "labelPrefix",
  "aria-label",
  "aria-description",
  "alt",
  "description",
  "detail",
  "eyebrow",
  "label",
  "placeholder",
  "prefix",
  "subject",
  "title",
]);

/** A sample identifier such as `tenant_acme` or `platform:tenant:read` is data, not copy. */
function isSampleIdentifier(text: string): boolean {
  return /^[a-z0-9]+(?:[_:.-][a-z0-9]+)+$/.test(text);
}

/*
 * Copy-bearing attribute literals that predate this guard, keyed by
 * "file|attribute|text". This list may only shrink: a new literal fails the
 * test, and so does an entry here that no longer matches anything. It is
 * empty: keep it that way by moving new copy into the catalogue instead.
 */
const ATTRIBUTE_DEBT = new Set<string>([]);

type Finding = { file: string; line: number; kind: string; text: string };

function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (ts.isTemplateExpression(node)) {
    return [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join("…");
  }
  return null;
}

/** Literals an expression can render as-is: itself or a conditional/logical branch. */
function renderedLiterals(expression: ts.Expression | undefined, out: ts.Node[] = []): ts.Node[] {
  if (!expression) return out;
  if (ts.isParenthesizedExpression(expression)) return renderedLiterals(expression.expression, out);
  if (literalText(expression) !== null) {
    out.push(expression);
  } else if (ts.isConditionalExpression(expression)) {
    renderedLiterals(expression.whenTrue, out);
    renderedLiterals(expression.whenFalse, out);
  } else if (
    ts.isBinaryExpression(expression)
    && [
      ts.SyntaxKind.AmpersandAmpersandToken,
      ts.SyntaxKind.BarBarToken,
      ts.SyntaxKind.QuestionQuestionToken,
    ].includes(expression.operatorToken.kind)
  ) {
    renderedLiterals(expression.left, out);
    renderedLiterals(expression.right, out);
  }
  return out;
}

export function scanSource(file: string, source: string): Finding[] {
  const sourceFile = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const findings: Finding[] = [];
  const report = (node: ts.Node, kind: string, text: string) => {
    const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
    findings.push({ file, line: line + 1, kind, text: text.replace(/\s+/g, " ").trim() });
  };

  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && isCopy(node.text)) {
      report(node, "jsx-text", node.text);
    } else if (
      ts.isJsxExpression(node)
      && node.parent
      && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))
    ) {
      for (const literal of renderedLiterals(node.expression)) {
        const text = literalText(literal) ?? "";
        if (isCopy(text)) report(literal, "jsx-literal", text);
      }
    } else if (
      ts.isCallExpression(node)
      && ts.isIdentifier(node.expression)
      && node.expression.text === "pluralize"
    ) {
      for (const argument of node.arguments.slice(1)) {
        const text = literalText(argument);
        if (text !== null && isCopy(text)) report(argument, "pluralize", text);
      }
    } else if (ts.isJsxAttribute(node) && COPY_ATTRIBUTES.has(node.name.getText(sourceFile))) {
      const value = node.initializer && ts.isJsxExpression(node.initializer)
        ? node.initializer.expression
        : node.initializer;
      const text = value ? literalText(value) : null;
      if (text !== null && isCopy(text) && !isSampleIdentifier(text)) {
        report(node, `attribute:${node.name.getText(sourceFile)}`, text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return findings;
}

function sourceFiles(): string[] {
  return SCANNED_DIRS.flatMap((dir) =>
    (readdirSync(path.join(WEB_ROOT, dir), { recursive: true }) as string[])
      .filter((file) => file.endsWith(".tsx") && !file.endsWith(".test.tsx"))
      .map((file) => path.join(dir, file).split(path.sep).join("/")),
  ).sort();
}

const debtKey = (finding: Finding) =>
  `${finding.file}|${finding.kind.replace("attribute:", "")}|${finding.text}`;

describe("hardcoded component copy", () => {
  const files = sourceFiles();
  const findings = files.flatMap((file) => scanSource(file, readFileSync(path.join(WEB_ROOT, file), "utf8")));
  const rendered = findings.filter((finding) => !finding.kind.startsWith("attribute:"));
  const attributes = findings.filter((finding) => finding.kind.startsWith("attribute:"));

  it("scans the component tree", () => {
    expect(files.length).toBeGreaterThan(100);
    expect(files).toContain("components/approval-inbox.tsx");
  });

  it("renders no English text that is not from the catalogue", () => {
    const report = rendered.map(({ file, line, kind, text }) => `${file}:${line} ${kind} ${JSON.stringify(text)}`);
    expect(report, "Move this copy into lib/strings.ts and lib/strings.it.ts").toEqual([]);
  });

  it("adds no copy-bearing attribute literals beyond the known debt", () => {
    const added = attributes
      .filter((finding) => !ATTRIBUTE_DEBT.has(debtKey(finding)))
      .map((finding) => `${finding.file}:${finding.line} ${finding.kind} ${JSON.stringify(finding.text)}`);
    expect(added, "Move this copy into lib/strings.ts and lib/strings.it.ts").toEqual([]);
  });

  it("keeps the known attribute debt list current", () => {
    const present = new Set(attributes.map(debtKey));
    expect([...ATTRIBUTE_DEBT].filter((key) => !present.has(key)), "Remove fixed entries from ATTRIBUTE_DEBT").toEqual([]);
  });
});

describe("hardcoded copy scanner", () => {
  const scan = (source: string) => scanSource("example.tsx", source).map(({ kind, text }) => `${kind}: ${text}`);

  it("flags sentence fragments split around expressions", () => {
    expect(scan(`const a = <p>Showing {shown} of {total}</p>;`)).toEqual([
      "jsx-text: Showing",
      "jsx-text: of",
    ]);
    expect(scan(`const a = <p>{owner} decision pending</p>;`)).toEqual(["jsx-text: decision pending"]);
    expect(scan(`const a = <p>Revision created: r{n}</p>;`)).toEqual(["jsx-text: Revision created: r"]);
    expect(scan(`const a = <span>r{n}</span>;`)).toEqual(["jsx-text: r"]);
    expect(scan(`const a = <p>{n} run{n === 1 ? "" : "s"}</p>;`)).toEqual(["jsx-text: run", "jsx-literal: s"]);
  });

  it("flags literals rendered from expressions and pluralize nouns", () => {
    expect(scan(`const a = <p>{ok ? "would match" : "would not match"}</p>;`)).toEqual([
      "jsx-literal: would match",
      "jsx-literal: would not match",
    ]);
    expect(scan(`const a = <p>{id ?? "unrouted"}</p>;`)).toEqual(["jsx-literal: unrouted"]);
    expect(scan("const a = <p>{`${n} recorded`}</p>;")).toEqual(["jsx-literal: … recorded"]);
    expect(scan(`const a = <p>{pluralize(n, "event")}</p>;`)).toEqual(["pluralize: event"]);
    expect(scan(`const a = <Pill aria-label="Data source" />;`)).toEqual(["attribute:aria-label: Data source"]);
  });

  it("allows catalogue copy, punctuation, symbols and technical tokens", () => {
    expect(scan(`const a = <p>{strings.ui.common.visibleCount(n)}</p>;`)).toEqual([]);
    expect(scan(`const a = <p>{a} · {b} / {c} — {d}%</p>;`)).toEqual([]);
    expect(scan(`const a = <p>{x ? " · " : ""}{"→"}</p>;`)).toEqual([]);
    expect(scan(`const a = <p>GET / PUT {path}</p>;`)).toEqual([]);
    expect(scan(`const a = <p>POST /platform/policies/{id}/revisions — {scope}</p>;`)).toEqual([]);
    expect(scan(`const a = <small>API</small>;`)).toEqual([]);
    expect(scan(`const a = <Input placeholder="tenant_acme_manufacturing" className="w-full" />;`)).toEqual([]);
  });
});
