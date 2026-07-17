import { describe, expect, it } from "vitest";

import {
  connectorRegistryFixture,
  credentialHandleRegistryFixture,
  credentialLeaseRegistryFixture,
  egressPolicyRegistryFixture,
  evidenceInvariantReportFixture,
  manifestRegistryFixture,
  ontologyProposalRegistryFixture,
  runRegistryFixture,
} from "@/components/connector-console/connector-fixtures";
import { ontologyFixture } from "@/components/ontology/ontology-fixtures";
import {
  approvalInboxFixture,
  auditEventsFixture,
  identitySessionFixture,
  modelRoutingFixture,
  overviewFixture,
  policyRegistryFixture,
  snapshotFixture,
} from "@/components/overview/overview-fixtures";

import {
  parseActionRunPersistenceResult,
  parseManufacturingActionRegistry,
} from "./runtime-contracts/actions";
import {
  parseApprovalDecisionPersistenceResult,
  parseManufacturingApprovalInbox,
} from "./runtime-contracts/approvals";
import { parseAuditExportBundle, parseManufacturingAuditExplorer } from "./runtime-contracts/audit";
import {
  parseAxisReadyReport,
  parseDeploymentReadinessReport,
  parseIdentityBrowserSessionList,
  parseOidcReadinessReport,
  parseSupportDiagnosticsReport,
} from "./runtime-contracts/identity";
import {
  parseConnectorCsvPreviewResult,
  parseConnectorExternalDbPreviewResult,
  parseConnectorRunRecord,
  parseManufacturingConnectorCredentialHandleRegistry,
  parseManufacturingConnectorCredentialLeaseRegistry,
  parseManufacturingConnectorEgressPolicyRegistry,
  parseManufacturingConnectorEvidenceInvariantReport,
  parseManufacturingConnectorManifestRegistry,
  parseManufacturingConnectorOntologyProposalRegistry,
  parseManufacturingConnectorRegistry,
  parseManufacturingConnectorRunRegistry,
} from "./runtime-contracts/connectors";
import { parseDemoBootstrapResult } from "./runtime-contracts/bootstrap";
import {
  parseIdentitySessionReadModel,
  parseManufacturingNotificationCenter,
  parseManufacturingNotificationAcknowledgementResult,
  parseManufacturingOperationsSnapshot,
  parseManufacturingOverview,
  parseOperationsArtifactResponse,
} from "./runtime-contracts/overview";
import { parseManufacturingAgentRegistry } from "./runtime-contracts/agents";
import { parseManufacturingModelRouting } from "./runtime-contracts/model-routing";
import {
  parseManufacturingOntology,
  parseManufacturingOntologyEntityDetail,
} from "./runtime-contracts/ontology";
import { parseManufacturingReplaySimulation } from "./runtime-contracts/simulation";
import { parseManufacturingWorkflowConsole } from "./runtime-contracts/workflows";
import {
  parsePlatformPolicyDecision,
  parsePlatformPolicyDetail,
  parsePlatformPolicyRecord,
  parsePlatformPolicyRegistry,
} from "./runtime-contracts/policies";
import {
  parseTenantQuotaSet,
  parseTenantRecord,
  parseTenantRegistry,
  parseTenantUsageSummary,
} from "./runtime-contracts/tenants";

const productionDecoders = [
  parseActionRunPersistenceResult,
  parseApprovalDecisionPersistenceResult,
  parseAuditExportBundle,
  parseAxisReadyReport,
  parseConnectorCsvPreviewResult,
  parseConnectorExternalDbPreviewResult,
  parseConnectorRunRecord,
  parseDemoBootstrapResult,
  parseDeploymentReadinessReport,
  parseIdentityBrowserSessionList,
  parseIdentitySessionReadModel,
  parseManufacturingActionRegistry,
  parseManufacturingAgentRegistry,
  parseManufacturingApprovalInbox,
  parseManufacturingAuditExplorer,
  parseManufacturingConnectorCredentialHandleRegistry,
  parseManufacturingConnectorCredentialLeaseRegistry,
  parseManufacturingConnectorEgressPolicyRegistry,
  parseManufacturingConnectorEvidenceInvariantReport,
  parseManufacturingConnectorManifestRegistry,
  parseManufacturingConnectorOntologyProposalRegistry,
  parseManufacturingConnectorRegistry,
  parseManufacturingConnectorRunRegistry,
  parseManufacturingModelRouting,
  parseManufacturingNotificationCenter,
  parseManufacturingNotificationAcknowledgementResult,
  parseManufacturingOntology,
  parseManufacturingOntologyEntityDetail,
  parseManufacturingOperationsSnapshot,
  parseManufacturingOverview,
  parseManufacturingReplaySimulation,
  parseManufacturingWorkflowConsole,
  parseOidcReadinessReport,
  parseOperationsArtifactResponse,
  parsePlatformPolicyDecision,
  parsePlatformPolicyDetail,
  parsePlatformPolicyRecord,
  parsePlatformPolicyRegistry,
  parseSupportDiagnosticsReport,
  parseTenantQuotaSet,
  parseTenantRecord,
  parseTenantRegistry,
  parseTenantUsageSummary,
] as const;

describe("production runtime contracts", () => {
  it.each(productionDecoders)("rejects an empty object at every API boundary", (parse) => {
    expect(() => parse({})).toThrow();
  });

  it("accepts a valid identity session and preserves additive compatibility", () => {
    const payload = {
      authenticated: true,
      mode: "secure_oidc_cookie",
      actor_id: "operator-1",
      tenant_id: "tenant-1",
      scopes: ["tenant:read"],
      expires_at: 1_800_000_000,
      api_auth_required: true,
      enterprise_sso_ready: true,
      readiness_status: "ready",
      issuer: "https://issuer.example",
      audience: "axis-api",
      jwks_source: "remote",
      session_boundary: "api_owned",
      capabilities: ["browser_session_rotation"],
      limitations: [],
      notes: [],
      future_additive_field: "accepted",
    };

    const parsed = parseIdentitySessionReadModel(payload);
    expect(parsed).toBe(payload);
    expect(parsed).toMatchObject({
      actor_id: "operator-1",
      authenticated: true,
      readiness_status: "ready",
    });
    expect(parsed).toHaveProperty("future_additive_field", "accepted");
  });

  it("rejects malformed nested identity fields instead of fabricating defaults", () => {
    expect(() =>
      parseIdentitySessionReadModel({
        authenticated: "yes",
        scopes: null,
      }),
    ).toThrow();
  });

  it("requires and preserves approval decision replay evidence", () => {
    const payload = {
      tenant_id: "tenant-1",
      approval_id: "approval-1",
      workflow_id: "workflow-1",
      action_id: "action-1",
      decision: "approve",
      status: "approve",
      actor_id: "operator-1",
      audit_event_id: "11111111-1111-4111-8111-111111111111",
      audit_event_type: "approval.decision.recorded",
      persisted: true,
      idempotent_replay: true,
      permission_decision: { allowed: true, reason: "allowed" },
      workflow_signal: {
        workflow_id: "workflow-1",
        status: "approval_signaled",
        adapter: "axis-test",
        signal_name: "approve",
        payload: { approval_id: "approval-1", approved: true, decision: "approve" },
      },
      workflow_signal_status: "approval_signaled",
      decision_event_id: "22222222-2222-4222-8222-222222222222",
    };

    expect(parseApprovalDecisionPersistenceResult(payload)).toMatchObject({
      idempotent_replay: true,
      decision_event_id: "22222222-2222-4222-8222-222222222222",
    });
    expect(() =>
      parseApprovalDecisionPersistenceResult({ ...payload, idempotent_replay: "yes" }),
    ).toThrow();
  });

  it("accepts scalar and collection audit references without accepting nulls", () => {
    const payload = structuredClone(snapshotFixture);
    payload.recent_audit_events[0].payload_refs = {
      scenario_id: "supplier_delay_demo",
      source_record_ids: ["order_rush_4812"],
    };

    expect(parseManufacturingOperationsSnapshot(payload)).toBe(payload);

    payload.recent_audit_events[0].payload_refs = { workflow_id: null } as never;
    expect(() => parseManufacturingOperationsSnapshot(payload)).toThrow();
  });

  it.each([
    ["overview", parseManufacturingOverview, overviewFixture],
    ["operations snapshot", parseManufacturingOperationsSnapshot, snapshotFixture],
    ["identity", parseIdentitySessionReadModel, identitySessionFixture],
    ["approval inbox", parseManufacturingApprovalInbox, approvalInboxFixture],
    ["ontology", parseManufacturingOntology, ontologyFixture],
    ["model routing", parseManufacturingModelRouting, modelRoutingFixture],
    ["audit explorer", parseManufacturingAuditExplorer, auditEventsFixture],
    ["policy registry", parsePlatformPolicyRegistry, policyRegistryFixture],
    ["connector registry", parseManufacturingConnectorRegistry, connectorRegistryFixture],
    ["connector manifests", parseManufacturingConnectorManifestRegistry, manifestRegistryFixture],
    [
      "connector credential handles",
      parseManufacturingConnectorCredentialHandleRegistry,
      credentialHandleRegistryFixture,
    ],
    [
      "connector credential leases",
      parseManufacturingConnectorCredentialLeaseRegistry,
      credentialLeaseRegistryFixture,
    ],
    ["connector egress policies", parseManufacturingConnectorEgressPolicyRegistry, egressPolicyRegistryFixture],
    ["connector runs", parseManufacturingConnectorRunRegistry, runRegistryFixture],
    [
      "connector evidence invariants",
      parseManufacturingConnectorEvidenceInvariantReport,
      evidenceInvariantReportFixture,
    ],
    [
      "connector ontology proposals",
      parseManufacturingConnectorOntologyProposalRegistry,
      ontologyProposalRegistryFixture,
    ],
  ] as const)("accepts the representative %s payload", (_name, parse, fixture) => {
    expect(parse(fixture)).toBe(fixture);
  });
});
