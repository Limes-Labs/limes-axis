import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

type Rgb = [number, number, number];

/** WCAG 2.1 relative luminance contrast ratio. */
function contrast(a: Rgb, b: Rgb): number {
  const luminance = ([r, g, b]: Rgb) => {
    const [lr, lg, lb] = [r, g, b].map((value) => {
      const c = value / 255;
      return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
  };
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

function blend(foreground: Rgb, background: Rgb, alpha: number): Rgb {
  return foreground.map((value, index) => value * alpha + background[index] * (1 - alpha)) as Rgb;
}

describe("Axis brand system", () => {
  const globalsCss = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8").toLowerCase();

  it("defines the brand palette as light-first channel tokens", () => {
    expect(globalsCss).toContain("color-scheme: light");
    expect(globalsCss).toContain("--signal: 47 100 255;");
    expect(globalsCss).toContain("--navy: 4 18 46;");
    expect(globalsCss).toContain("--cloud: 247 248 251;");
    expect(globalsCss).toContain("--mist: 217 222 232;");
    expect(globalsCss).toContain("--slate: 91 103 130;");
    expect(globalsCss).toContain("--tint-50: #f3f6ff;");
    expect(globalsCss).toContain("--tint-100: #eef3ff;");
    expect(globalsCss).toContain("--tint-200: #dce6ff;");
  });

  it("ships a navy dark theme, not a black one", () => {
    const darkBlock = globalsCss.match(/\[data-theme="dark"\]\s*\{[^}]+\}/);
    expect(darkBlock).not.toBeNull();
    expect(darkBlock?.[0]).toContain("color-scheme: dark");
    expect(darkBlock?.[0]).toContain("--bg: 4 18 46;");
    expect(darkBlock?.[0]).toContain("--surface: 9 26 58;");
    expect(darkBlock?.[0]).toContain("--ink: 237 241 248;");
    expect(darkBlock?.[0]).toContain("--line: 34 52 88;");
    expect(darkBlock?.[0]).toContain("--muted: 158 172 200;");
  });

  it("keeps light-theme text tokens at WCAG AA 4.5:1 on every console background", () => {
    const rootBlock = globalsCss.match(/:root\s*\{[^}]+\}/)?.[0] ?? "";
    const channel = (name: string): Rgb => {
      const match = rootBlock.match(new RegExp(`--${name}:\\s*(\\d+) (\\d+) (\\d+);`));
      expect(match, `--${name} channel`).not.toBeNull();
      return [Number(match![1]), Number(match![2]), Number(match![3])];
    };
    const hex = (name: string): Rgb => {
      const match = rootBlock.match(new RegExp(`--${name}:\\s*#([0-9a-f]{6});`));
      expect(match, `--${name} color`).not.toBeNull();
      const value = match![1];
      return [0, 2, 4].map((offset) => parseInt(value.slice(offset, offset + 2), 16)) as Rgb;
    };

    const cloud = channel("cloud");
    const surface = channel("surface");
    const ink = channel("navy");
    const accent = channel("accent");
    const backgrounds: Record<string, Rgb> = {
      cloud,
      surface,
      "tint-50": hex("tint-50"),
      "tint-100": hex("tint-100"),
      "tint-200": hex("tint-200"),
      "signal/10 on cloud": blend(accent, cloud, 0.1),
      "ink/4 on cloud": blend(ink, cloud, 0.04),
    };
    const textTokens = ["slate", "accent", "positive", "warning", "danger"];
    for (const token of textTokens) {
      const text = channel(token);
      for (const [label, background] of Object.entries(backgrounds)) {
        expect(contrast(text, background), `${token} on ${label}`).toBeGreaterThanOrEqual(4.5);
      }
    }
    // Status pills render their tone as text over a 12% wash of the same tone.
    for (const token of ["accent", "positive", "warning", "danger"]) {
      const text = channel(token);
      for (const [label, base] of Object.entries({ cloud, surface })) {
        expect(
          contrast(text, blend(text, base, 0.12)),
          `${token} pill on ${label}`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("keeps table headers on the shared muted DataTable styling", () => {
    // Signal headers were 3.46:1 on the dark card; tables must share
    // DataTable's muted header styling instead of hand-rolling their own.
    for (const file of ["policy-registry.tsx", "policy-detail.tsx", "tenant-registry.tsx"]) {
      const source = readFileSync(join(process.cwd(), "components", file), "utf8");
      expect(source, file).not.toContain("[&_th]:text-signal");
      expect(source, file).toMatch(/DataTable|dataTableClassName/);
    }
  });

  it("respects reduced-motion preferences", () => {
    expect(globalsCss).toContain("@media (prefers-reduced-motion: reduce)");
  });

});
