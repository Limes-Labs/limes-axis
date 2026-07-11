"use client";

import type {
  ManufacturingConnectorCredentialHandleRegistry,
  ManufacturingConnectorCredentialLeaseRegistry,
  ManufacturingConnectorEgressPolicyRegistry,
  ManufacturingConnectorEvidenceInvariantReport,
  ManufacturingConnectorManifestRegistry,
  ManufacturingConnectorOntologyProposalRegistry,
  ManufacturingConnectorRegistry,
  ManufacturingConnectorRunRegistry,
} from "./connectors-demo";
import { CONNECTOR_TENANT_ID } from "./connectors-console";
import { useAxisQuery } from "./use-axis-query";

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
  evidenceInvariants:
    `/demo/manufacturing/connectors/evidence-invariants?tenant_id=${CONNECTOR_TENANT_ID}`,
  ontologyProposals: "/demo/manufacturing/connectors/ontology-proposals",
} as const;

export function useConnectorRegistries() {
  const registry = useAxisQuery<ManufacturingConnectorRegistry>(CONNECTOR_ENDPOINTS.registry);
  const manifests = useAxisQuery<ManufacturingConnectorManifestRegistry>(
    CONNECTOR_ENDPOINTS.manifests,
  );
  const credentialHandles = useAxisQuery<ManufacturingConnectorCredentialHandleRegistry>(
    CONNECTOR_ENDPOINTS.credentialHandles,
  );
  const credentialLeases = useAxisQuery<ManufacturingConnectorCredentialLeaseRegistry>(
    CONNECTOR_ENDPOINTS.credentialLeases,
  );
  const egressPolicies = useAxisQuery<ManufacturingConnectorEgressPolicyRegistry>(
    CONNECTOR_ENDPOINTS.egressPolicies,
  );
  const runs = useAxisQuery<ManufacturingConnectorRunRegistry>(CONNECTOR_ENDPOINTS.runs);
  const evidenceInvariants = useAxisQuery<ManufacturingConnectorEvidenceInvariantReport>(
    CONNECTOR_ENDPOINTS.evidenceInvariants,
  );
  const ontologyProposals = useAxisQuery<ManufacturingConnectorOntologyProposalRegistry>(
    CONNECTOR_ENDPOINTS.ontologyProposals,
  );

  return {
    registry,
    manifests,
    credentialHandles,
    credentialLeases,
    egressPolicies,
    runs,
    evidenceInvariants,
    ontologyProposals,
  };
}

export type ConnectorRegistries = ReturnType<typeof useConnectorRegistries>;
