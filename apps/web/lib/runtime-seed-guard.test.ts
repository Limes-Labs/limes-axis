import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const runtimeLibFiles = [
  "action-demo.ts",
  "agent-demo.ts",
  "approval-demo.ts",
  "audit-demo.ts",
  "connectors-demo.ts",
  "model-routing-demo.ts",
  "ontology-demo.ts",
  "operations-artifacts.ts",
  "platform-overview.ts",
  "simulation-demo.ts",
  "workflow-demo.ts",
];

const forbiddenRuntimeSeedPatterns = [
  /defaultManufacturing[A-Za-z0-9_]+/,
  /defaultConnector[A-Za-z0-9_]+/,
  /defaultAuditExportBundle/,
  /defaultArtifacts/,
  /defaultPersistedOutputs/,
  /ontologyDetailOverrides/,
  /demo-seed/i,
  /public-demo/i,
  /synthetic/i,
];

describe("frontend runtime seed guard", () => {
  it("does not keep default seed records in runtime libraries", () => {
    const offenders = runtimeLibFiles.filter((fileName) => {
      const source = readFileSync(join(process.cwd(), "lib", fileName), "utf8");
      return forbiddenRuntimeSeedPatterns.some((pattern) => pattern.test(source));
    });

    expect(offenders).toEqual([]);
  });
});
