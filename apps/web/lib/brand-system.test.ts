import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { brandTokens } from "./foundation";

function hexToChannels(hex: string): string {
  const value = hex.replace("#", "");
  const r = Number.parseInt(value.slice(0, 2), 16);
  const g = Number.parseInt(value.slice(2, 4), 16);
  const b = Number.parseInt(value.slice(4, 6), 16);
  return `${r} ${g} ${b}`;
}

describe("Axis brand system", () => {
  const globalsCss = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8").toLowerCase();

  it("is built on Tailwind v4 (CSS-first)", () => {
    expect(globalsCss).toContain('@import "tailwindcss"');
    expect(globalsCss).toContain("@custom-variant dark");
    expect(globalsCss).toContain("@theme inline");
  });

  it("defines the brand palette as light-first channel tokens", () => {
    expect(globalsCss).toContain("color-scheme: light");
    expect(globalsCss).toContain(`--signal: ${brandTokens.signalChannels};`);
    expect(globalsCss).toContain(`--navy: ${brandTokens.navyChannels};`);
    expect(globalsCss).toContain(`--cloud: ${brandTokens.cloudChannels};`);
    expect(globalsCss).toContain(`--mist: ${brandTokens.mistChannels};`);
    expect(globalsCss).toContain(`--slate: ${brandTokens.slateChannels};`);
    expect(globalsCss).toContain(`--tint-50: ${brandTokens.tint50};`);
    expect(globalsCss).toContain(`--tint-100: ${brandTokens.tint100};`);
    expect(globalsCss).toContain(`--tint-200: ${brandTokens.tint200};`);
  });

  it("keeps the exported hex tokens in sync with the channel tokens", () => {
    expect(hexToChannels(brandTokens.signal)).toBe(brandTokens.signalChannels);
    expect(hexToChannels(brandTokens.navy)).toBe(brandTokens.navyChannels);
    expect(hexToChannels(brandTokens.cloud)).toBe(brandTokens.cloudChannels);
    expect(hexToChannels(brandTokens.mist)).toBe(brandTokens.mistChannels);
    expect(hexToChannels(brandTokens.slate)).toBe(brandTokens.slateChannels);
  });

  it("ships a navy dark theme, not a black one", () => {
    const darkBlock = globalsCss.match(/\[data-theme="dark"\]\s*\{[^}]+\}/);
    expect(darkBlock).not.toBeNull();
    expect(darkBlock?.[0]).toContain("color-scheme: dark");
    expect(darkBlock?.[0]).toContain(`--bg: ${brandTokens.dark.bgChannels};`);
    expect(darkBlock?.[0]).toContain(`--surface: ${brandTokens.dark.surfaceChannels};`);
    expect(darkBlock?.[0]).toContain(`--ink: ${brandTokens.dark.inkChannels};`);
    expect(darkBlock?.[0]).toContain(`--line: ${brandTokens.dark.lineChannels};`);
    expect(darkBlock?.[0]).toContain(`--muted: ${brandTokens.dark.mutedChannels};`);
  });

  it("respects reduced-motion preferences", () => {
    expect(globalsCss).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("retires the legacy dark-only palette literals", () => {
    expect(globalsCss).not.toContain("#3e6bff");
    expect(globalsCss).not.toContain("#070b10");
    expect(globalsCss).not.toContain("#30c7be");
  });
});
