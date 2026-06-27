import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

describe("Axis brand system", () => {
  const globalsCss = readFileSync(join(process.cwd(), "app", "globals.css"), "utf8").toLowerCase();

  it("uses the public Axis brand palette for the console shell", () => {
    expect(globalsCss).toContain("color-scheme: dark");
    expect(globalsCss).toContain("--axis-black: #111317");
    expect(globalsCss).toContain("--graphite: #262c35");
    expect(globalsCss).toContain("--cloud: #f7f8fa");
    expect(globalsCss).toContain("--mist: #dce2ea");
    expect(globalsCss).toContain("--signal-blue: #3e6bff");
    expect(globalsCss).toContain("--teal-pulse: #30c7be");
  });

  it("keeps brand composition neutral-first instead of monochrome blue", () => {
    expect(globalsCss).toContain("--axis-neutral-balance: 70%");
    expect(globalsCss).toContain("--axis-support-balance: 20%");
    expect(globalsCss).toContain("--axis-accent-balance: 10%");
  });
});
