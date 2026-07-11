import { describe, expect, it } from "vitest";

import { buildConnectorSnapshotHref, formatConnectorLabel } from "./connectors-demo";

describe("manufacturing connector helpers", () => {
  it("formats connector labels for API values", () => {
    expect(formatConnectorLabel("file_csv")).toBe("File Csv");
    expect(formatConnectorLabel("axis-egress-policy-enforcer")).toBe(
      "Axis Egress Policy Enforcer",
    );
  });

  it("builds public connector snapshot deep links from persisted audit fields", () => {
    expect(
      buildConnectorSnapshotHref({
        snapshotId: "snap_connector_evidence_20260627_1000",
        connectorId: "external_db_operational_mirror",
      }),
    ).toBe(
      "/connectors?snapshot_id=snap_connector_evidence_20260627_1000&connector_id=external_db_operational_mirror",
    );
    expect(
      buildConnectorSnapshotHref({
        snapshotId: "snap/id:fixture",
        connectorId: null,
      }),
    ).toBe("/connectors?snapshot_id=snap%2Fid%3Afixture");
    expect(
      buildConnectorSnapshotHref({
        snapshotId: null,
        connectorId: "external_db_operational_mirror",
      }),
    ).toBe("/connectors");
  });
});
