"use client";

import type {
  ManufacturingConnectorCredentialHandleRegistry,
  ManufacturingConnectorCredentialLeaseRegistry,
  ManufacturingConnectorEgressPolicyRegistry,
  ManufacturingConnectorEvidenceInvariantReport,
  ManufacturingConnectorEvidenceInvariantSnapshotHistory,
  ManufacturingConnectorManifestRegistry,
  ManufacturingConnectorOntologyProposalRegistry,
  ManufacturingConnectorRegistry,
  ManufacturingConnectorRunRegistry,
} from "./connectors-demo";
import {
  parseManufacturingConnectorCredentialHandleRegistry,
  parseManufacturingConnectorCredentialLeaseRegistry,
  parseManufacturingConnectorEgressPolicyRegistry,
  parseManufacturingConnectorEvidenceInvariantReport,
  parseManufacturingConnectorEvidenceInvariantSnapshotHistory,
  parseManufacturingConnectorManifestRegistry,
  parseManufacturingConnectorOntologyProposalRegistry,
  parseManufacturingConnectorRegistry,
  parseManufacturingConnectorRunRegistry,
} from "./runtime-contracts/connectors";
import { useAxisQuery } from "./use-axis-query";
import { buildTenantScopedPath, DEMO_TENANT_ID } from "./tenant-scope";

/*
 * One `useAxisQuery` per endpoint the rebuilt connector console actually
 * renders. The old monolith fetched 16 endpoints behind a single Promise.all
 * gate; the eight endpoints whose data only fed the deleted invariant-tile
 * wall and promotion forms (configurations, sync checkpoints, checkpoint
 * claims, evidence snapshots, snapshot exports, manual imports, promotion
 * policies, promotion policy sets) are dropped.
 */

export const CONNECTOR_ENDPOINTS = {
  registry: "/demo/manufacturing/connectors",
  manifests: "/demo/manufacturing/connectors/manifests",
  credentialHandles: "/demo/manufacturing/connectors/credential-handles",
  credentialLeases: "/demo/manufacturing/connectors/credential-leases",
  egressPolicies: "/demo/manufacturing/connectors/egress-policies",
  runs: "/demo/manufacturing/connectors/runs",
  evidenceInvariants: "/demo/manufacturing/connectors/evidence-invariants",
  evidenceSnapshots: "/demo/manufacturing/connectors/evidence-invariants/snapshots",
  ontologyProposals: "/demo/manufacturing/connectors/ontology-proposals",
} as const;

export function useConnectorRegistries(
  tenantId: string | null,
  enabled: boolean,
  snapshotId = "",
  connectorId = "",
) {
  // Hooks must receive a stable path even while identity is unresolved. The
  // query gate guarantees the placeholder demo path is never requested until
  // the identity API has explicitly selected that tenant.
  const scopedPath = (path: string) =>
    buildTenantScopedPath(path, tenantId ?? DEMO_TENANT_ID);
  const queryOptions = {
    enabled: enabled && tenantId !== null,
    expectedTenantId: tenantId ?? undefined,
  };

  const registry = useAxisQuery<ManufacturingConnectorRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.registry),
    {
      ...queryOptions,
      parse: parseManufacturingConnectorRegistry,
    },
  );
  const manifests = useAxisQuery<ManufacturingConnectorManifestRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.manifests),
    { ...queryOptions, parse: parseManufacturingConnectorManifestRegistry },
  );
  const credentialHandles = useAxisQuery<ManufacturingConnectorCredentialHandleRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.credentialHandles),
    { ...queryOptions, parse: parseManufacturingConnectorCredentialHandleRegistry },
  );
  const credentialLeases = useAxisQuery<ManufacturingConnectorCredentialLeaseRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.credentialLeases),
    { ...queryOptions, parse: parseManufacturingConnectorCredentialLeaseRegistry },
  );
  const egressPolicies = useAxisQuery<ManufacturingConnectorEgressPolicyRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.egressPolicies),
    { ...queryOptions, parse: parseManufacturingConnectorEgressPolicyRegistry },
  );
  const runs = useAxisQuery<ManufacturingConnectorRunRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.runs),
    {
      ...queryOptions,
      parse: parseManufacturingConnectorRunRegistry,
    },
  );
  const evidenceInvariants = useAxisQuery<ManufacturingConnectorEvidenceInvariantReport>(
    scopedPath(CONNECTOR_ENDPOINTS.evidenceInvariants),
    { ...queryOptions, parse: parseManufacturingConnectorEvidenceInvariantReport },
  );
  const evidenceSnapshots = useAxisQuery<ManufacturingConnectorEvidenceInvariantSnapshotHistory>(
    buildTenantScopedPath(
      CONNECTOR_ENDPOINTS.evidenceSnapshots,
      tenantId ?? DEMO_TENANT_ID,
      {
        ...(snapshotId ? { snapshot_id: snapshotId } : {}),
        ...(connectorId ? { connector_id: connectorId } : {}),
      },
    ),
    {
      ...queryOptions,
      enabled: queryOptions.enabled && Boolean(snapshotId),
      parse: parseManufacturingConnectorEvidenceInvariantSnapshotHistory,
    },
  );
  const ontologyProposals = useAxisQuery<ManufacturingConnectorOntologyProposalRegistry>(
    scopedPath(CONNECTOR_ENDPOINTS.ontologyProposals),
    { ...queryOptions, parse: parseManufacturingConnectorOntologyProposalRegistry },
  );

  return {
    registry,
    manifests,
    credentialHandles,
    credentialLeases,
    egressPolicies,
    runs,
    evidenceInvariants,
    evidenceSnapshots,
    ontologyProposals,
  };
}

export type ConnectorRegistries = ReturnType<typeof useConnectorRegistries>;
