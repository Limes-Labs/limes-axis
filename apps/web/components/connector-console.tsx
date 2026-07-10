"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Cable, Database, FileText, KeyRound, ScrollText, ShieldCheck } from "lucide-react";

import { axisFetch } from "@/lib/axis-api";
import { useConsole } from "@/providers/console-provider";
import { buildAuditEventHref } from "@/lib/audit-demo";
import {
  buildConnectorEvidenceInvariantSnapshotRequest,
  buildConnectorEvidenceInvariantSnapshotExportPath,
  buildConnectorEvidenceInvariantSnapshotExportRequest,
  buildConnectorEvidenceInvariantSnapshotExportRequestDecision,
  buildConnectorEvidenceInvariantSnapshotExportRequestDecisionPath,
  buildConnectorEvidenceInvariantSnapshotExportRequestMaterialization,
  buildConnectorEvidenceInvariantSnapshotExportRequestMaterializationPath,
  buildConnectorEvidenceInvariantSnapshotExportRequestPath,
  buildConnectorEvidenceInvariantSnapshotHistoryPath,
  buildConnectorSyncCheckpointClaimQueryPath,
  buildConnectorSyncCheckpointQueryPath,
  buildConnectorOntologyPromotionRequest,
  buildConnectorPromotionPolicyDraftRequest,
  buildConnectorPromotionPolicyEnableRequest,
  findApprovedManualImportForProposal,
  resolveOntologyPromotionStatus,
  filterConnectorCredentialLeaseInvariantsByLeases,
  filterConnectorEgressPolicyInvariantsByPolicies,
  filterConnectorSyncCheckpointClaimInvariantsByClaims,
  filterConnectorSyncCheckpointInvariantsByCheckpoints,
  filterConnectorSyncCheckpointClaimsByCheckpoints,
  filterConnectorSyncCheckpointsByConnector,
  formatConnectorLabel,
  resolveConnectorSnapshotSelection,
  summarizeConnectorEvidenceInvariantSnapshotHistory,
  summarizeConnectorEvidenceInvariantCounts,
  type ConnectorCsvPreviewResult,
  type ConnectorEvidenceInvariantSnapshotExportBundle,
  type ConnectorEvidenceInvariantSnapshotExportDecisionResult,
  type ConnectorEvidenceInvariantSnapshotExportMaterializationResult,
  type ConnectorEvidenceInvariantSnapshotExportRequestRecord,
  type ConnectorEvidenceInvariantSnapshotHistory,
  type ConnectorEvidenceInvariantSnapshotRecord,
  type ConnectorOntologyProposalRecord,
  type ConnectorPromotionPolicyCreateRequest,
  type ConnectorPromotionPolicyEnableRequest,
  type ConnectorRunRecord,
  type ManufacturingConnectorConfigurationRegistry,
  type ManufacturingConnectorEgressPolicyRegistry,
  type ManufacturingConnectorEvidenceInvariantReport,
  type ManufacturingConnectorCredentialHandleRegistry,
  type ManufacturingConnectorCredentialLeaseRegistry,
  type ManufacturingConnectorManifestRegistry,
  type ManufacturingConnectorManualImportRegistry,
  type ManufacturingConnectorOntologyProposalRegistry,
  type ManufacturingConnectorPromotionPolicyRegistry,
  type ManufacturingConnectorPromotionPolicySetRegistry,
  type ManufacturingConnectorRunRegistry,
  type ManufacturingConnectorSyncCheckpointClaimRegistry,
  type ManufacturingConnectorRegistry,
  type ManufacturingConnectorSyncCheckpointRegistry,
} from "@/lib/connectors-demo";
import {
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

type ConnectorSource = "loading" | "api" | "unavailable";
type PolicyAuthoringStatus = "idle" | "saving" | "api_created" | "error";
type PolicyEnableStatus = "idle" | "saving" | "api_enabled" | "error";
type ProposalPromotionStatus =
  | "idle"
  | "promoting"
  | "promoted"
  | "deferred"
  | "failed"
  | "forbidden"
  | "no_evidence"
  | "error";

const PROPOSAL_PROMOTION_STATUS_LABEL: Record<ProposalPromotionStatus, string> = {
  idle: "",
  promoting: "promoting…",
  promoted: "promoted to graph",
  deferred: "promotion deferred (mutations disabled)",
  failed: "promotion failed",
  forbidden: "permission denied",
  no_evidence: "approved manual import required",
  error: "promotion request failed",
};
type EvidenceSnapshotStatus = "idle" | "saving" | "api_created" | "error";
type EvidenceSnapshotExportRequestStatus = "idle" | "saving" | "api_created" | "error";
type EvidenceSnapshotExportDecisionStatus = "idle" | "saving" | "api_decided" | "error";
type EvidenceSnapshotExportMaterializationStatus =
  | "idle"
  | "saving"
  | "api_materialized"
  | "error";

const CONNECTOR_TENANT_ID = "tenant_demo_manufacturing";
const CONNECTOR_PLANT_NAME = "Ravenna Works";
const CONNECTOR_SCENARIO = "Plant Operations Cockpit";

const EMPTY_REGISTRY_BASE = {
  tenant_id: CONNECTOR_TENANT_ID,
  plant_name: CONNECTOR_PLANT_NAME,
  scenario: CONNECTOR_SCENARIO,
  registry_status: "watch" as const,
  metrics: [],
};

const EMPTY_CONNECTOR_REGISTRY: ManufacturingConnectorRegistry = {
  ...EMPTY_REGISTRY_BASE,
  connectors: [],
  connector_notes: [],
};

const EMPTY_CSV_PREVIEW: ConnectorCsvPreviewResult = {
  tenant_id: CONNECTOR_TENANT_ID,
  connector_id: "",
  file_name: "",
  preview_status: "not_requested",
  sync_mode: "not_requested",
  record_count: 0,
  accepted_record_count: 0,
  rejected_record_count: 0,
  validation_issues: [],
  proposed_entities: [],
  audit_event_preview: {
    event_type: "not_requested",
    scope: "api",
    actor_id: "",
    result: "not_requested",
    evidence_refs: [],
    payload_preview: {},
  },
  preview_notes: [],
};

const EMPTY_MANIFEST_REGISTRY: ManufacturingConnectorManifestRegistry = {
  ...EMPTY_REGISTRY_BASE,
  manifests: [],
  manifest_notes: [],
};

const EMPTY_CONFIGURATION_REGISTRY: ManufacturingConnectorConfigurationRegistry = {
  ...EMPTY_REGISTRY_BASE,
  configurations: [],
  configuration_notes: [],
};

const EMPTY_CREDENTIAL_HANDLE_REGISTRY: ManufacturingConnectorCredentialHandleRegistry = {
  ...EMPTY_REGISTRY_BASE,
  handles: [],
  handle_notes: [],
};

const EMPTY_CREDENTIAL_LEASE_REGISTRY: ManufacturingConnectorCredentialLeaseRegistry = {
  ...EMPTY_REGISTRY_BASE,
  leases: [],
  lease_evidence_invariants: [],
  lease_notes: [],
};

const EMPTY_EGRESS_POLICY_REGISTRY: ManufacturingConnectorEgressPolicyRegistry = {
  ...EMPTY_REGISTRY_BASE,
  policies: [],
  policy_evidence_invariants: [],
  policy_notes: [],
};

const EMPTY_RUN_REGISTRY: ManufacturingConnectorRunRegistry = {
  ...EMPTY_REGISTRY_BASE,
  runs: [],
  run_notes: [],
};

const EMPTY_SYNC_CHECKPOINT_REGISTRY: ManufacturingConnectorSyncCheckpointRegistry = {
  ...EMPTY_REGISTRY_BASE,
  checkpoints: [],
  evidence_invariants: [],
  checkpoint_notes: [],
};

const EMPTY_SYNC_CHECKPOINT_CLAIM_REGISTRY: ManufacturingConnectorSyncCheckpointClaimRegistry = {
  ...EMPTY_REGISTRY_BASE,
  claims: [],
  claim_evidence_invariants: [],
  next_cursor: null,
  has_more: false,
  claim_notes: [],
};

const EMPTY_EVIDENCE_INVARIANT_REPORT: ManufacturingConnectorEvidenceInvariantReport = {
  ...EMPTY_REGISTRY_BASE,
  invariant_counts: {
    checkpoint: 0,
    checkpoint_claim: 0,
    credential_lease: 0,
    egress_policy: 0,
  },
  invariants: [],
  report_notes: [],
};

const EMPTY_EVIDENCE_SNAPSHOT_HISTORY: ConnectorEvidenceInvariantSnapshotHistory = {
  tenant_id: CONNECTOR_TENANT_ID,
  plant_name: CONNECTOR_PLANT_NAME,
  scenario: CONNECTOR_SCENARIO,
  history_status: "watch",
  metrics: [],
  snapshots: [],
  history_notes: [],
};

const EMPTY_ONTOLOGY_PROPOSAL_REGISTRY: ManufacturingConnectorOntologyProposalRegistry = {
  ...EMPTY_REGISTRY_BASE,
  proposals: [],
  proposal_notes: [],
};

const EMPTY_MANUAL_IMPORT_REGISTRY: ManufacturingConnectorManualImportRegistry = {
  ...EMPTY_REGISTRY_BASE,
  imports: [],
  import_notes: [],
};

const EMPTY_PROMOTION_POLICY_REGISTRY: ManufacturingConnectorPromotionPolicyRegistry = {
  ...EMPTY_REGISTRY_BASE,
  policies: [],
  policy_notes: [],
};

const EMPTY_PROMOTION_POLICY_SET_REGISTRY: ManufacturingConnectorPromotionPolicySetRegistry = {
  ...EMPTY_REGISTRY_BASE,
  policy_sets: [],
  policy_set_notes: [],
};

function sourceLabel(source: ConnectorSource): string {
  if (source === "api") {
    return "API connector data";
  }

  return source === "loading" ? "Loading connector API" : "Connector API unavailable";
}

function sourcePillClass(source: ConnectorSource): string {
  if (source === "api") {
    return "signal-ready";
  }

  return source === "loading" ? "status-checking" : "signal-action-required";
}

function snapshotIdStamp(date: Date): string {
  return date.toISOString().replace(/\D/g, "").slice(0, 17);
}

async function fetchConnectorJson<T>(
  path: string,
  signal?: AbortSignal,
  init?: Parameters<typeof axisFetch>[1],
): Promise<T> {
  const response = await axisFetch(path, {
    ...init,
    signal,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Connector request failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

async function fetchConnectorData(signal?: AbortSignal) {
  const [
    registryData,
    manifestData,
    configurationData,
    credentialHandleData,
    credentialLeaseData,
    egressPolicyData,
    runData,
    syncCheckpointData,
    syncCheckpointClaimData,
    evidenceInvariantData,
    evidenceSnapshotHistoryData,
    evidenceSnapshotExportData,
    ontologyProposalData,
    manualImportData,
    promotionPolicyData,
    promotionPolicySetData,
  ] = await Promise.all([
    fetchConnectorJson<ManufacturingConnectorRegistry>("/demo/manufacturing/connectors", signal),
    fetchConnectorJson<ManufacturingConnectorManifestRegistry>(
      "/demo/manufacturing/connectors/manifests",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorConfigurationRegistry>(
      "/demo/manufacturing/connectors/configurations",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorCredentialHandleRegistry>(
      "/demo/manufacturing/connectors/credential-handles",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorCredentialLeaseRegistry>(
      "/demo/manufacturing/connectors/credential-leases",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorEgressPolicyRegistry>(
      "/demo/manufacturing/connectors/egress-policies",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorRunRegistry>(
      "/demo/manufacturing/connectors/runs",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorSyncCheckpointRegistry>(
      buildConnectorSyncCheckpointQueryPath(CONNECTOR_TENANT_ID),
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorSyncCheckpointClaimRegistry>(
      buildConnectorSyncCheckpointClaimQueryPath(CONNECTOR_TENANT_ID),
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorEvidenceInvariantReport>(
      `/demo/manufacturing/connectors/evidence-invariants?tenant_id=${CONNECTOR_TENANT_ID}`,
      signal,
    ),
    fetchConnectorJson<ConnectorEvidenceInvariantSnapshotHistory>(
      buildConnectorEvidenceInvariantSnapshotHistoryPath(CONNECTOR_TENANT_ID, {
        limit: 20,
      }),
      signal,
    ),
    fetchConnectorJson<ConnectorEvidenceInvariantSnapshotExportBundle>(
      buildConnectorEvidenceInvariantSnapshotExportPath(CONNECTOR_TENANT_ID, {
        limit: 20,
        exportReason: "console-review",
      }),
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorOntologyProposalRegistry>(
      "/demo/manufacturing/connectors/ontology-proposals",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorManualImportRegistry>(
      "/demo/manufacturing/connectors/manual-imports",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorPromotionPolicyRegistry>(
      "/demo/manufacturing/connectors/promotion-policies",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorPromotionPolicySetRegistry>(
      "/demo/manufacturing/connectors/promotion-policy-sets",
      signal,
    ),
  ]);

  return {
    configurationData,
    credentialHandleData,
    credentialLeaseData,
    evidenceInvariantData,
    evidenceSnapshotExportData,
    evidenceSnapshotHistoryData,
    egressPolicyData,
    manifestData,
    manualImportData,
    ontologyProposalData,
    promotionPolicyData,
    promotionPolicySetData,
    registryData,
    runData,
    syncCheckpointClaimData,
    syncCheckpointData,
  };
}

function connectorRunRuntimeAdapter(run: ConnectorRunRecord): string {
  return (
    run.sync_execution_result?.adapter ??
    run.dispatch_result?.adapter ??
    run.schedule_result?.adapter ??
    run.execution_result?.adapter ??
    "not requested"
  );
}

function connectorRunRuntimeStatus(run: ConnectorRunRecord): string {
  return (
    run.sync_execution_result?.status ??
    run.dispatch_result?.status ??
    run.schedule_result?.status ??
    run.execution_result?.status ??
    "record-only evidence"
  );
}

function connectorRunExternalSyncStarted(run: ConnectorRunRecord): boolean {
  return Boolean(
    run.sync_execution_result?.external_sync_started ??
      run.dispatch_result?.external_sync_started ??
      run.schedule_result?.external_sync_started ??
      run.execution_result?.external_sync_started,
  );
}

function connectorRunRuntimeEvidence(run: ConnectorRunRecord): string {
  return (
    run.sync_execution_result?.sync_ref ??
    run.sync_execution_result?.idempotency_key ??
    run.dispatch_result?.dispatch_ref ??
    run.dispatch_result?.idempotency_key ??
    run.schedule_result?.schedule_ref ??
    run.schedule_result?.idempotency_key ??
    run.execution_result?.idempotency_key ??
    "no runtime idempotency key"
  );
}

function formatCheckpointScalar(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return "not recorded";
}

export function ConnectorConsole() {
  const [registry, setRegistry] = useState<ManufacturingConnectorRegistry>(
    EMPTY_CONNECTOR_REGISTRY,
  );
  const [preview, setPreview] = useState<ConnectorCsvPreviewResult>(
    EMPTY_CSV_PREVIEW,
  );
  const [configurationRegistry, setConfigurationRegistry] =
    useState<ManufacturingConnectorConfigurationRegistry>(
      EMPTY_CONFIGURATION_REGISTRY,
    );
  const [manifestRegistry, setManifestRegistry] = useState<ManufacturingConnectorManifestRegistry>(
    EMPTY_MANIFEST_REGISTRY,
  );
  const [credentialHandleRegistry, setCredentialHandleRegistry] =
    useState<ManufacturingConnectorCredentialHandleRegistry>(
      EMPTY_CREDENTIAL_HANDLE_REGISTRY,
    );
  const [credentialLeaseRegistry, setCredentialLeaseRegistry] =
    useState<ManufacturingConnectorCredentialLeaseRegistry>(
      EMPTY_CREDENTIAL_LEASE_REGISTRY,
    );
  const [egressPolicyRegistry, setEgressPolicyRegistry] =
    useState<ManufacturingConnectorEgressPolicyRegistry>(
      EMPTY_EGRESS_POLICY_REGISTRY,
    );
  const [runRegistry, setRunRegistry] =
    useState<ManufacturingConnectorRunRegistry>(EMPTY_RUN_REGISTRY);
  const [syncCheckpointRegistry, setSyncCheckpointRegistry] =
    useState<ManufacturingConnectorSyncCheckpointRegistry>(
      EMPTY_SYNC_CHECKPOINT_REGISTRY,
    );
  const [syncCheckpointClaimRegistry, setSyncCheckpointClaimRegistry] =
    useState<ManufacturingConnectorSyncCheckpointClaimRegistry>(
      EMPTY_SYNC_CHECKPOINT_CLAIM_REGISTRY,
    );
  const [evidenceInvariantReport, setEvidenceInvariantReport] =
    useState<ManufacturingConnectorEvidenceInvariantReport>(
      EMPTY_EVIDENCE_INVARIANT_REPORT,
    );
  const [evidenceSnapshotHistory, setEvidenceSnapshotHistory] =
    useState<ConnectorEvidenceInvariantSnapshotHistory>(
      EMPTY_EVIDENCE_SNAPSHOT_HISTORY,
    );
  const [evidenceSnapshotExport, setEvidenceSnapshotExport] =
    useState<ConnectorEvidenceInvariantSnapshotExportBundle | null>(null);
  const [evidenceSnapshotExportRequest, setEvidenceSnapshotExportRequest] =
    useState<ConnectorEvidenceInvariantSnapshotExportRequestRecord | null>(null);
  const [evidenceSnapshotExportRequestStatus, setEvidenceSnapshotExportRequestStatus] =
    useState<EvidenceSnapshotExportRequestStatus>("idle");
  const [evidenceSnapshotExportDecisionStatus, setEvidenceSnapshotExportDecisionStatus] =
    useState<EvidenceSnapshotExportDecisionStatus>("idle");
  const [
    evidenceSnapshotExportMaterializationStatus,
    setEvidenceSnapshotExportMaterializationStatus,
  ] = useState<EvidenceSnapshotExportMaterializationStatus>("idle");
  const [ontologyProposalRegistry, setOntologyProposalRegistry] =
    useState<ManufacturingConnectorOntologyProposalRegistry>(
      EMPTY_ONTOLOGY_PROPOSAL_REGISTRY,
    );
  const [manualImportRegistry, setManualImportRegistry] =
    useState<ManufacturingConnectorManualImportRegistry>(
      EMPTY_MANUAL_IMPORT_REGISTRY,
    );
  const [promotionPolicyRegistry, setPromotionPolicyRegistry] =
    useState<ManufacturingConnectorPromotionPolicyRegistry>(
      EMPTY_PROMOTION_POLICY_REGISTRY,
    );
  const [promotionPolicySetRegistry, setPromotionPolicySetRegistry] =
    useState<ManufacturingConnectorPromotionPolicySetRegistry>(
      EMPTY_PROMOTION_POLICY_SET_REGISTRY,
    );
  const [source, setSource] = useState<ConnectorSource>("loading");
  const [requestedSnapshotId] = useState<string | null>(() =>
    typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("snapshot_id"),
  );
  const [requestedConnectorId] = useState<string | null>(() =>
    typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("connector_id"),
  );
  const [selectedConnectorId, setSelectedConnectorId] = useState("");
  const [policyForm, setPolicyForm] = useState<ConnectorPromotionPolicyCreateRequest>(() =>
    buildConnectorPromotionPolicyDraftRequest(),
  );
  const [policyEnableForm, setPolicyEnableForm] =
    useState<ConnectorPromotionPolicyEnableRequest>(() =>
      buildConnectorPromotionPolicyEnableRequest(),
    );
  const [policyAuthoringStatus, setPolicyAuthoringStatus] =
    useState<PolicyAuthoringStatus>("idle");
  const [policyEnableStatus, setPolicyEnableStatus] = useState<PolicyEnableStatus>("idle");
  const [proposalPromotionStatuses, setProposalPromotionStatuses] = useState<
    Record<string, ProposalPromotionStatus>
  >({});
  const [evidenceSnapshotStatus, setEvidenceSnapshotStatus] =
    useState<EvidenceSnapshotStatus>("idle");
  const { refreshNonce } = useConsole();

  useEffect(() => {
    const controller = new AbortController();

    async function loadInitialConnectors() {
      try {
        const data = await fetchConnectorData(controller.signal);
        setRegistry(data.registryData);
        setManifestRegistry(data.manifestData);
        setConfigurationRegistry(data.configurationData);
        setCredentialHandleRegistry(data.credentialHandleData);
        setCredentialLeaseRegistry(data.credentialLeaseData);
        setEgressPolicyRegistry(data.egressPolicyData);
        setRunRegistry(data.runData);
        setSyncCheckpointRegistry(data.syncCheckpointData);
        setSyncCheckpointClaimRegistry(data.syncCheckpointClaimData);
        setEvidenceInvariantReport(data.evidenceInvariantData);
        setEvidenceSnapshotHistory(data.evidenceSnapshotHistoryData);
        setEvidenceSnapshotExport(data.evidenceSnapshotExportData);
        setOntologyProposalRegistry(data.ontologyProposalData);
        setManualImportRegistry(data.manualImportData);
        setPromotionPolicyRegistry(data.promotionPolicyData);
        setPromotionPolicySetRegistry(data.promotionPolicySetData);
        setPreview(EMPTY_CSV_PREVIEW);
        setSelectedConnectorId(
          resolveConnectorSnapshotSelection({
            registry: data.registryData,
            history: data.evidenceSnapshotHistoryData,
            requestedConnectorId,
            requestedSnapshotId,
          }).connectorId,
        );
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setSource("unavailable");
        }
      }
    }

    void loadInitialConnectors();

    return () => controller.abort();
  }, [refreshNonce, requestedConnectorId, requestedSnapshotId]);

  const selectedConnector = useMemo(
    () =>
      registry.connectors.find(
        (connector) => connector.manifest.connector_id === selectedConnectorId,
      ),
    [registry, selectedConnectorId],
  );
  const selectedConfiguration = useMemo(
    () =>
      configurationRegistry.configurations.find(
        (configuration) => configuration.connector_id === selectedConnectorId,
      ),
    [configurationRegistry.configurations, selectedConnectorId],
  );
  const selectedManifestRecord = useMemo(
    () =>
      manifestRegistry.manifests.find(
        (manifestRecord) => manifestRecord.connector_id === selectedConnectorId,
      ),
    [manifestRegistry.manifests, selectedConnectorId],
  );
  const selectedCredentialHandles = useMemo(
    () =>
      credentialHandleRegistry.handles.filter(
        (handle) => handle.connector_id === selectedConnectorId,
      ),
    [credentialHandleRegistry.handles, selectedConnectorId],
  );
  const selectedCredentialLeases = useMemo(
    () =>
      credentialLeaseRegistry.leases.filter(
        (lease) => lease.connector_id === selectedConnectorId,
      ),
    [credentialLeaseRegistry.leases, selectedConnectorId],
  );
  const selectedCredentialLeaseInvariants = useMemo(
    () =>
      filterConnectorCredentialLeaseInvariantsByLeases(
        credentialLeaseRegistry,
        selectedCredentialLeases,
      ),
    [credentialLeaseRegistry, selectedCredentialLeases],
  );
  const selectedEgressPolicies = useMemo(
    () =>
      egressPolicyRegistry.policies.filter(
        (policy) => policy.connector_id === selectedConnectorId,
      ),
    [egressPolicyRegistry.policies, selectedConnectorId],
  );
  const selectedEgressPolicyInvariants = useMemo(
    () =>
      filterConnectorEgressPolicyInvariantsByPolicies(
        egressPolicyRegistry,
        selectedEgressPolicies,
      ),
    [egressPolicyRegistry, selectedEgressPolicies],
  );
  const selectedRuns = useMemo(
    () => runRegistry.runs.filter((run) => run.connector_id === selectedConnectorId),
    [runRegistry.runs, selectedConnectorId],
  );
  const selectedSyncCheckpoints = useMemo(
    () =>
      filterConnectorSyncCheckpointsByConnector(
        syncCheckpointRegistry,
        selectedConnectorId,
      ),
    [syncCheckpointRegistry, selectedConnectorId],
  );
  const selectedSyncCheckpointClaims = useMemo(
    () =>
      filterConnectorSyncCheckpointClaimsByCheckpoints(
        syncCheckpointClaimRegistry,
        selectedSyncCheckpoints,
      ),
    [syncCheckpointClaimRegistry, selectedSyncCheckpoints],
  );
  const selectedSyncCheckpointClaimInvariants = useMemo(
    () =>
      filterConnectorSyncCheckpointClaimInvariantsByClaims(
        syncCheckpointClaimRegistry,
        selectedSyncCheckpointClaims,
      ),
    [syncCheckpointClaimRegistry, selectedSyncCheckpointClaims],
  );
  const selectedSyncCheckpointInvariants = useMemo(
    () =>
      filterConnectorSyncCheckpointInvariantsByCheckpoints(
        syncCheckpointRegistry,
        selectedSyncCheckpoints,
      ),
    [syncCheckpointRegistry, selectedSyncCheckpoints],
  );
  const selectedOntologyProposals = useMemo(
    () =>
      ontologyProposalRegistry.proposals.filter(
        (proposal) => proposal.connector_id === selectedConnectorId,
      ),
    [ontologyProposalRegistry.proposals, selectedConnectorId],
  );
  const selectedManualImports = useMemo(
    () =>
      manualImportRegistry.imports.filter(
        (manualImport) => manualImport.connector_id === selectedConnectorId,
      ),
    [manualImportRegistry.imports, selectedConnectorId],
  );
  const selectedPromotionPolicies = useMemo(
    () =>
      promotionPolicyRegistry.policies.filter(
        (policy) => policy.connector_id === selectedConnectorId,
      ),
    [promotionPolicyRegistry.policies, selectedConnectorId],
  );
  const selectedPromotionPolicySets = useMemo(
    () =>
      promotionPolicySetRegistry.policy_sets.filter(
        (policySet) => policySet.connector_id === selectedConnectorId,
      ),
    [promotionPolicySetRegistry.policy_sets, selectedConnectorId],
  );
  const evidenceInvariantCounts = useMemo(
    () => summarizeConnectorEvidenceInvariantCounts(evidenceInvariantReport),
    [evidenceInvariantReport],
  );
  const evidenceSnapshotHistorySummary = useMemo(
    () => summarizeConnectorEvidenceInvariantSnapshotHistory(evidenceSnapshotHistory),
    [evidenceSnapshotHistory],
  );
  const selectedEvidenceSnapshots = useMemo(
    () =>
      evidenceSnapshotHistory.snapshots.filter(
        (snapshot) =>
          snapshot.connector_id === null || snapshot.connector_id === selectedConnectorId,
      ),
    [evidenceSnapshotHistory.snapshots, selectedConnectorId],
  );

  async function refreshConnectorData() {
    const data = await fetchConnectorData();
    setRegistry(data.registryData);
    setManifestRegistry(data.manifestData);
    setConfigurationRegistry(data.configurationData);
    setCredentialHandleRegistry(data.credentialHandleData);
    setCredentialLeaseRegistry(data.credentialLeaseData);
    setEgressPolicyRegistry(data.egressPolicyData);
    setRunRegistry(data.runData);
    setSyncCheckpointRegistry(data.syncCheckpointData);
    setSyncCheckpointClaimRegistry(data.syncCheckpointClaimData);
    setEvidenceInvariantReport(data.evidenceInvariantData);
    setEvidenceSnapshotHistory(data.evidenceSnapshotHistoryData);
    setEvidenceSnapshotExport(data.evidenceSnapshotExportData);
    setOntologyProposalRegistry(data.ontologyProposalData);
    setManualImportRegistry(data.manualImportData);
    setPromotionPolicyRegistry(data.promotionPolicyData);
    setPromotionPolicySetRegistry(data.promotionPolicySetData);
    setPreview(EMPTY_CSV_PREVIEW);
    setSelectedConnectorId((currentConnectorId) =>
      data.registryData.connectors.some(
        (connector) => connector.manifest.connector_id === currentConnectorId,
      )
        ? currentConnectorId
        : (data.registryData.connectors[0]?.manifest.connector_id ?? ""),
    );
    setSource("api");
  }

  async function authorPromotionPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request = {
      ...policyForm,
      tenant_id: registry.tenant_id,
      connector_id: selectedConnectorId,
      actor_scopes: ["connectors:promotion_policy:author"],
      required_scopes: ["connectors:ontology:promote"],
      required_manual_import_status: "approval_approved",
      required_workflow_signal_status: "manual_import_signal_requested",
      allowed_risk_levels: ["high", "medium"],
      allowed_ontology_types: ["manufacturing_asset"],
      review_window_hours: 24,
    };

    setPolicyAuthoringStatus("saving");
    try {
      await fetchConnectorJson<unknown>("/demo/manufacturing/connectors/promotion-policies", undefined, {
        body: request,
        method: "POST",
      });
      await refreshConnectorData();
      setPolicyEnableForm(
        buildConnectorPromotionPolicyEnableRequest({
          policy_id: request.policy_id,
        }),
      );
      setPolicyAuthoringStatus("api_created");
    } catch {
      setPolicyAuthoringStatus("error");
    }
  }

  async function enablePromotionPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request = {
      ...policyEnableForm,
      tenant_id: registry.tenant_id,
      actor_scopes: ["connectors:promotion_policy:enable"],
      approval_decision: "approve",
      workflow_signal_status: "policy_enable_signal_recorded",
    };

    setPolicyEnableStatus("saving");
    try {
      await fetchConnectorJson<unknown>(
        `/demo/manufacturing/connectors/promotion-policies/${request.policy_id}/enable`,
        undefined,
        {
          body: request,
          method: "POST",
        },
      );
      await refreshConnectorData();
      setPolicyEnableStatus("api_enabled");
    } catch {
      setPolicyEnableStatus("error");
    }
  }

  async function promoteOntologyProposal(proposal: ConnectorOntologyProposalRecord) {
    // The promotion is governed server-side (approved manual import, promotion
    // policy, permission scope). The console only submits the request; the API
    // remains the source of truth. We optimistically render "promoting" and
    // reconcile from the server response (including a 403 rollback).
    const approvedImport = findApprovedManualImportForProposal(
      selectedManualImports,
      proposal.proposal_id,
    );
    if (!approvedImport) {
      setProposalPromotionStatuses((current) => ({
        ...current,
        [proposal.proposal_id]: "no_evidence",
      }));
      return;
    }

    setProposalPromotionStatuses((current) => ({
      ...current,
      [proposal.proposal_id]: "promoting",
    }));

    const request = buildConnectorOntologyPromotionRequest({
      tenantId: registry.tenant_id,
      proposalId: proposal.proposal_id,
      manualImportId: approvedImport.import_id,
    });

    try {
      const response = await axisFetch(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        {
          method: "POST",
          body: request,
          headers: { "Content-Type": "application/json" },
        },
      );

      if (response.status === 403) {
        setProposalPromotionStatuses((current) => ({
          ...current,
          [proposal.proposal_id]: "forbidden",
        }));
        return;
      }
      if (!response.ok) {
        setProposalPromotionStatuses((current) => ({
          ...current,
          [proposal.proposal_id]: "error",
        }));
        return;
      }

      const result = (await response.json()) as { graph_mutation_status?: string };
      setProposalPromotionStatuses((current) => ({
        ...current,
        [proposal.proposal_id]: resolveOntologyPromotionStatus(
          result.graph_mutation_status ?? "",
        ),
      }));
      await refreshConnectorData();
    } catch {
      setProposalPromotionStatuses((current) => ({
        ...current,
        [proposal.proposal_id]: "error",
      }));
    }
  }

  async function createEvidenceSnapshot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConnectorId) {
      return;
    }

    const stamp = snapshotIdStamp(new Date());
    const request = buildConnectorEvidenceInvariantSnapshotRequest({
      tenantId: registry.tenant_id,
      connectorId: selectedConnectorId,
      snapshotId: `snap_${selectedConnectorId}_${stamp}`,
      idempotencyKey: `idem_snap_${selectedConnectorId}_${stamp}`,
      requestedBy: "connector-security-reviewer-role",
      reason: "console-security-review",
      limit: 100,
    });

    setEvidenceSnapshotStatus("saving");
    try {
      await fetchConnectorJson<ConnectorEvidenceInvariantSnapshotRecord>(
        "/demo/manufacturing/connectors/evidence-invariants/snapshots",
        undefined,
        {
          body: request,
          method: "POST",
        },
      );
      await refreshConnectorData();
      setEvidenceSnapshotStatus("api_created");
    } catch {
      setEvidenceSnapshotStatus("error");
    }
  }

  async function requestEvidenceSnapshotExport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedConnectorId) {
      return;
    }

    const newestSnapshotId = selectedEvidenceSnapshots[0]?.snapshot_id;
    const request = buildConnectorEvidenceInvariantSnapshotExportRequest({
      tenantId: registry.tenant_id,
      connectorId: selectedConnectorId,
      snapshotId: newestSnapshotId,
      requestedBy: "connector-compliance-reviewer-role",
      now: new Date(),
    });

    setEvidenceSnapshotExportRequestStatus("saving");
    try {
      const result = await fetchConnectorJson<ConnectorEvidenceInvariantSnapshotExportRequestRecord>(
        buildConnectorEvidenceInvariantSnapshotExportRequestPath(),
        undefined,
        {
          body: request,
          method: "POST",
        },
      );
      setEvidenceSnapshotExportRequest(result);
      setEvidenceSnapshotExportRequestStatus("api_created");
      setEvidenceSnapshotExportDecisionStatus("idle");
      setEvidenceSnapshotExportMaterializationStatus("idle");
    } catch {
      setEvidenceSnapshotExportRequest(null);
      setEvidenceSnapshotExportRequestStatus("error");
      setEvidenceSnapshotExportDecisionStatus("idle");
      setEvidenceSnapshotExportMaterializationStatus("idle");
    }
  }

  async function approveEvidenceSnapshotExportRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!evidenceSnapshotExportRequest) {
      return;
    }

    const request = buildConnectorEvidenceInvariantSnapshotExportRequestDecision({
      actorId: "connector-compliance-owner-role",
      decision: "approve",
      note: "Approved from the connector evidence console.",
    });

    setEvidenceSnapshotExportDecisionStatus("saving");
    try {
      const result =
        await fetchConnectorJson<ConnectorEvidenceInvariantSnapshotExportDecisionResult>(
          buildConnectorEvidenceInvariantSnapshotExportRequestDecisionPath(
            evidenceSnapshotExportRequest.export_request_id,
          ),
          undefined,
          {
            body: request,
            method: "POST",
          },
        );
      setEvidenceSnapshotExportRequest(result.export_request);
      setEvidenceSnapshotExportDecisionStatus("api_decided");
      setEvidenceSnapshotExportMaterializationStatus("idle");
    } catch {
      setEvidenceSnapshotExportDecisionStatus("error");
    }
  }

  async function materializeEvidenceSnapshotExportRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !evidenceSnapshotExportRequest ||
      evidenceSnapshotExportRequest.decision !== "approve" ||
      evidenceSnapshotExportRequest.storage_status !== "not_written"
    ) {
      return;
    }

    const request = buildConnectorEvidenceInvariantSnapshotExportRequestMaterialization({
      exportRequestId: evidenceSnapshotExportRequest.export_request_id,
      actorId: "connector-compliance-owner-role",
      now: new Date(),
    });

    setEvidenceSnapshotExportMaterializationStatus("saving");
    try {
      const result =
        await fetchConnectorJson<ConnectorEvidenceInvariantSnapshotExportMaterializationResult>(
          buildConnectorEvidenceInvariantSnapshotExportRequestMaterializationPath(
            evidenceSnapshotExportRequest.export_request_id,
          ),
          undefined,
          {
            body: request,
            method: "POST",
          },
        );
      setEvidenceSnapshotExportRequest(result.export_request);
      setEvidenceSnapshotExportMaterializationStatus("api_materialized");
    } catch {
      setEvidenceSnapshotExportMaterializationStatus("error");
    }
  }

  const connectorMetrics = registry.metrics
    .concat(manifestRegistry.metrics)
    .concat(configurationRegistry.metrics)
    .concat(credentialHandleRegistry.metrics)
    .concat(credentialLeaseRegistry.metrics)
    .concat(egressPolicyRegistry.metrics)
    .concat(runRegistry.metrics)
    .concat(syncCheckpointRegistry.metrics)
    .concat(syncCheckpointClaimRegistry.metrics)
    .concat(evidenceInvariantReport.metrics)
    .concat(evidenceSnapshotHistory.metrics)
    .concat(ontologyProposalRegistry.metrics)
    .concat(manualImportRegistry.metrics)
    .concat(promotionPolicyRegistry.metrics)
    .concat(promotionPolicySetRegistry.metrics);

  if (!selectedConnector) {
    return (
      <div className="grid min-w-0 gap-4">
        <div
          aria-label="Connector source and status"
          className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
        >
          <p className="m-0 min-w-0 text-sm leading-snug break-words text-muted">
            {registry.plant_name} / {registry.scenario} / {registry.tenant_id}
          </p>
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className={`status-pill ${sourcePillClass(source)}`}>
              <Cable size={15} />
              {sourceLabel(source)}
            </span>
            <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
              <ShieldCheck size={15} />
              {platformStatusLabel(registry.registry_status)}
            </span>
          </div>
        </div>

        {connectorMetrics.length > 0 ? (
          <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
            {connectorMetrics.map((metric) => (
              <article className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]" key={`${metric.label}-${metric.detail}`}>
                <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
                  <p className="eyebrow m-0">{metric.label}</p>
                  <span className={`status-pill ${platformStatusClass(metric.status)}`}>
                    {platformStatusLabel(metric.status)}
                  </span>
                </div>
                <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{metric.value}</p>
                <p className="m-0 text-xs leading-relaxed text-muted break-words">{metric.detail}</p>
              </article>
            ))}
          </div>
        ) : null}

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Manifests</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
                {source === "loading" ? "Loading connector API" : "Connector API unavailable"}
              </h2>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                Connector data is loaded from the Axis API. Local fallback connector records are
                disabled.
              </p>
            </div>
            <span className={`status-pill ${sourcePillClass(source)}`}>
              <Database size={15} />
              {source === "loading" ? "Loading" : "API required"}
            </span>
          </div>
        </section>
      </div>
    );
  }

  const manifest = selectedConnector.manifest;
  const csvPreviewApplies = preview.connector_id === selectedConnectorId;
  const selectedPreviewMode = csvPreviewApplies
    ? preview.sync_mode
    : (manifest.sync_modes[0] ?? "preview");
  const selectedRecordCount = csvPreviewApplies
    ? preview.record_count
    : selectedConnector.preview_sample.record_count;
  const selectedRecordDetail = csvPreviewApplies
    ? `${preview.accepted_record_count} accepted / ${preview.rejected_record_count} rejected`
    : `${selectedConnector.preview_sample.headers.length} metadata fields / ${selectedConnector.preview_sample.file_name}`;
  const credentialDetail =
    manifest.credential_requirements.required_secret_refs.length > 0
      ? `${manifest.credential_requirements.required_secret_refs.length} external handle ref`
      : "no stored credentials";

  return (
    <div className="grid min-w-0 gap-4">
      <div
        aria-label="Connector source and status"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm leading-snug break-words text-muted">
          {registry.plant_name} / {registry.scenario} / {registry.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className={`status-pill ${sourcePillClass(source)}`}>
            <Cable size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
            <ShieldCheck size={15} />
            {platformStatusLabel(registry.registry_status)}
          </span>
        </div>
      </div>

      <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        {connectorMetrics.map((metric) => (
          <article
            className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]"
            key={`${metric.label}-${metric.detail}`}
          >
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
              <p className="eyebrow m-0">{metric.label}</p>
              <span className={`status-pill ${platformStatusClass(metric.status)}`}>
                {platformStatusLabel(metric.status)}
              </span>
            </div>
            <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{metric.value}</p>
            <p className="m-0 text-xs leading-relaxed text-muted break-words">{metric.detail}</p>
          </article>
        ))}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(300px,0.42fr)_minmax(0,1fr)] [&>*]:min-w-0">
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Manifests</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{registry.connectors.length} connector</h2>
            </div>
            <span className="status-pill signal-watch">
              <Database size={15} />
              Preview only
            </span>
          </div>

          <div className="grid">
            {registry.connectors.map((connector) => {
              const isSelected = connector.manifest.connector_id === manifest.connector_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3.5 border-0 border-t border-line/60 bg-transparent px-2.5 py-3.5 text-left text-ink transition-colors first:border-t-0 hover:bg-ink/4 dark:border-white/10 dark:hover:bg-white/6${isSelected ? " bg-signal/10 shadow-[inset_2px_0_0_rgb(var(--signal))] dark:bg-signal/15" : ""}`}
                  key={connector.manifest.connector_id}
                  onClick={() => setSelectedConnectorId(connector.manifest.connector_id)}
                  type="button"
                >
                  <span>
                    <span className="m-0 font-medium text-ink break-words">{connector.manifest.display_name}</span>
                    <span className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{connector.manifest.connector_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                      {connector.preview_sample.record_count} sample rows /{" "}
                      {formatConnectorLabel(connector.manifest.connector_type)}
                    </span>
                  </span>
                  <span className="status-pill signal-watch">
                    {formatConnectorLabel(connector.connector_status)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 grid gap-4">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">{manifest.connector_type}</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{manifest.display_name}</h2>
              <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{manifest.connector_id}</p>
            </div>
            <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
              <span className="status-pill signal-watch">{manifest.runtime_boundary}</span>
              <span className="status-pill status-checking">{manifest.version}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
            <div>
              <p className="eyebrow m-0">Sync Mode</p>
              <p className="m-0 font-medium text-ink break-words">{formatConnectorLabel(selectedPreviewMode)}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manifest.sync_modes.join(", ")}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Rows</p>
              <p className="m-0 font-medium text-ink break-words">{selectedRecordCount}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedRecordDetail}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Credentials</p>
              <p className="m-0 font-medium text-ink break-words">{manifest.credential_requirements.storage}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{credentialDetail}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Payload</p>
              <p className="m-0 font-medium text-ink break-words">{selectedConnector.runtime_policy.payload_policy}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedConnector.runtime_policy.egress_policy}</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
            <section>
              <p className="eyebrow m-0">Required Permissions</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {manifest.required_permissions.map((permission) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="eyebrow m-0">Blocked Operations</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {selectedConnector.runtime_policy.blocked_operations.map((operation) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={operation}>
                    {operation}
                  </span>
                ))}
              </div>
            </section>
          </div>

          {selectedConfiguration ? (
            <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
              <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="eyebrow m-0">Tenant Configuration</p>
                  <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{selectedConfiguration.display_name}</h3>
                  <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{selectedConfiguration.status}</p>
                </div>
                <Database size={18} />
              </div>
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
                <div>
                  <p className="eyebrow m-0">Sync</p>
                  <p className="m-0 font-medium text-ink break-words">{selectedConfiguration.sync_mode}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedConfiguration.runtime_boundary}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Created By</p>
                  <p className="m-0 font-medium text-ink break-words">{selectedConfiguration.created_by}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">tenant-scoped configuration</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Credential Handles</p>
                  <p className="m-0 font-medium text-ink break-words">{selectedConfiguration.credential_ref_ids.length}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">no raw credential values</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Mode</p>
                  <p className="m-0 font-medium text-ink break-words">Preview only</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">no scheduled sync</p>
                </div>
              </div>
              <div className="grid min-w-0 gap-2">
                {Object.entries(selectedConfiguration.configuration_payload).map(([key, value]) => (
                  <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={key}>
                    <span className="eyebrow m-0">{key}</span>
                    <span className="font-mono text-[13px] break-words">{value}</span>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {selectedManifestRecord ? (
            <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
              <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="eyebrow m-0">Persisted Manifest</p>
                  <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{selectedManifestRecord.status}</h3>
                  <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{selectedManifestRecord.manifest_id}</p>
                </div>
                <ScrollText size={18} />
              </div>
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
                <div>
                  <p className="eyebrow m-0">Registered By</p>
                  <p className="m-0 font-medium text-ink break-words">{selectedManifestRecord.registered_by}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedManifestRecord.audit_event_type}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Manifest Type</p>
                  <p className="m-0 font-medium text-ink break-words">{formatConnectorLabel(selectedManifestRecord.connector_type)}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedManifestRecord.source_type}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Runtime</p>
                  <p className="m-0 font-medium text-ink break-words">{selectedManifestRecord.runtime_boundary}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedManifestRecord.version}</p>
                </div>
              </div>
            </section>
          ) : null}

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Evidence Invariant Report</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {evidenceInvariantReport.invariants.length} aggregate finding
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{evidenceInvariantReport.registry_status}</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
              {evidenceInvariantCounts.map((count) => (
                <div key={count.label}>
                  <p className="eyebrow m-0">{count.label}</p>
                  <p className="m-0 font-medium text-ink break-words">{count.value}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">append-only audit invariant</p>
                </div>
              ))}
            </div>
            {evidenceInvariantReport.invariants.length > 0 ? (
              <div className="grid min-w-0 gap-2">
                {evidenceInvariantReport.invariants.slice(0, 8).map((invariant) => (
                  <div
                    className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5"
                    key={`${invariant.evidence_type}-${invariant.subject_id}-${invariant.reason}`}
                  >
                    <span>
                      <span className="eyebrow m-0">
                        {formatConnectorLabel(invariant.evidence_type)}
                      </span>
                      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{invariant.subject_id}</span>
                    </span>
                    <span className="font-mono text-[13px] break-words">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Snapshot History</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {evidenceSnapshotHistorySummary.snapshotCount} audit artifact
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  latest {evidenceSnapshotHistorySummary.latestSnapshotId}
                </p>
              </div>
              <ScrollText size={18} />
            </div>
            <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
              <div>
                <p className="eyebrow m-0">Total Invariants</p>
                <p className="m-0 font-medium text-ink break-words">{evidenceSnapshotHistorySummary.totalInvariantCount}</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{evidenceSnapshotHistory.history_status}</p>
              </div>
              <div>
                <p className="eyebrow m-0">Evidence Surfaces</p>
                <p className="m-0 font-medium text-ink break-words">
                  {evidenceSnapshotHistorySummary.evidenceSurfaceCount}
                </p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">append-only snapshot history</p>
              </div>
              <div>
                <p className="eyebrow m-0">Selected Connector</p>
                <p className="m-0 font-medium text-ink break-words">{selectedEvidenceSnapshots.length}</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">matching snapshot artifact</p>
              </div>
              {evidenceSnapshotExport ? (
                <div>
                  <p className="eyebrow m-0">Signed Export</p>
                  <p className="m-0 font-medium text-ink break-words">{evidenceSnapshotExport.manifest.record_count}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExport.ledger_signature.verification_status}
                  </p>
                </div>
              ) : null}
            </div>
            {evidenceSnapshotExport ? (
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5">
                <span>
                  <span className="eyebrow m-0">{evidenceSnapshotExport.manifest.export_id}</span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExport.manifest.redaction_policy} /{" "}
                    {evidenceSnapshotExport.integrity_proof.algorithm}
                  </span>
                </span>
                <span>
                  <span className="font-mono text-[13px] break-words">
                    {evidenceSnapshotExport.manifest.checksum_sha256.slice(0, 12)}
                  </span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExport.ledger_signature.key_id ??
                      evidenceSnapshotExport.ledger_signature.signing_mode}
                  </span>
                </span>
              </div>
            ) : null}
            {selectedEvidenceSnapshots.length > 0 ? (
              <div className="grid min-w-0 gap-2">
                {selectedEvidenceSnapshots.slice(0, 5).map((snapshot) => (
                  <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={snapshot.snapshot_id}>
                    <span>
                      <span className="eyebrow m-0">{snapshot.snapshot_id}</span>
                      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                        {snapshot.connector_id ?? "tenant-wide"} / {snapshot.status}
                      </span>
                      {requestedSnapshotId === snapshot.snapshot_id ? (
                        <span className="status-pill status-checking">Selected artifact</span>
                      ) : null}
                    </span>
                    <span>
                      <span className="font-mono text-[13px] break-words">{snapshot.report_digest_sha256.slice(0, 12)}</span>
                      {snapshot.audit_event_id ? (
                        <a className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" href={buildAuditEventHref(snapshot.audit_event_id)}>
                          Audit event
                        </a>
                      ) : (
                        <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">no audit event</span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">No matching snapshot artifacts recorded.</p>
            )}
            <form
              aria-label="Evidence snapshot creation"
              className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
              onSubmit={createEvidenceSnapshot}
            >
              <button
                className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none"
                disabled={evidenceSnapshotStatus === "saving" || !selectedConnectorId}
                type="submit"
              >
                {evidenceSnapshotStatus === "saving" ? "Creating" : "Create snapshot"}
              </button>
            </form>
            {evidenceSnapshotStatus !== "idle" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {evidenceSnapshotStatus === "api_created"
                  ? "Snapshot persisted in the audit ledger."
                  : evidenceSnapshotStatus === "saving"
                    ? "Snapshot creation is being submitted."
                    : "Snapshot creation failed."}
              </p>
            ) : null}
            <form
              aria-label="Evidence snapshot export request"
              className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
              onSubmit={requestEvidenceSnapshotExport}
            >
              <button
                className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none"
                disabled={
                  evidenceSnapshotExportRequestStatus === "saving" || !selectedConnectorId
                }
                type="submit"
              >
                {evidenceSnapshotExportRequestStatus === "saving"
                  ? "Requesting"
                  : "Request export"}
              </button>
            </form>
            {evidenceSnapshotExportRequestStatus !== "idle" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {evidenceSnapshotExportRequestStatus === "api_created"
                  ? "Export request recorded for approval."
                  : evidenceSnapshotExportRequestStatus === "saving"
                    ? "Export request is being submitted."
                    : "Export request failed."}
              </p>
            ) : null}
            {evidenceSnapshotExportRequest ? (
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5">
                <span>
                  <span className="eyebrow m-0">
                    {evidenceSnapshotExportRequest.export_request_id}
                  </span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExportRequest.status} /{" "}
                    {evidenceSnapshotExportRequest.workflow_signal_status}
                  </span>
                </span>
                <span>
                  <span className="font-mono text-[13px] break-words">
                    {evidenceSnapshotExportRequest.snapshot_checksum_sha256.slice(0, 12)}
                  </span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExportRequest.approval_id} /{" "}
                    {evidenceSnapshotExportRequest.storage_status}
                  </span>
                </span>
                {evidenceSnapshotExportRequest.decision ? (
                  <span>
                    <span className="eyebrow m-0">
                      {evidenceSnapshotExportRequest.decision}
                    </span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                      {evidenceSnapshotExportRequest.export_status}
                    </span>
                  </span>
                ) : null}
              </div>
            ) : null}
            {evidenceSnapshotExportRequest ? (
              <form
                aria-label="Evidence snapshot export decision"
                className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
                onSubmit={approveEvidenceSnapshotExportRequest}
              >
                <button
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none"
                  disabled={
                    evidenceSnapshotExportDecisionStatus === "saving" ||
                    evidenceSnapshotExportRequest.decision !== null
                  }
                  type="submit"
                >
                  {evidenceSnapshotExportDecisionStatus === "saving"
                    ? "Approving"
                    : "Approve export"}
                </button>
              </form>
            ) : null}
            {evidenceSnapshotExportDecisionStatus !== "idle" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {evidenceSnapshotExportDecisionStatus === "api_decided"
                  ? "Export request decision recorded."
                  : evidenceSnapshotExportDecisionStatus === "saving"
                    ? "Export request decision is being submitted."
                    : "Export request decision failed."}
              </p>
            ) : null}
            {evidenceSnapshotExportRequest?.decision === "approve" ? (
              <form
                aria-label="Evidence snapshot export materialization"
                className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
                onSubmit={materializeEvidenceSnapshotExportRequest}
              >
                <button
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none"
                  disabled={
                    evidenceSnapshotExportMaterializationStatus === "saving" ||
                    evidenceSnapshotExportRequest.storage_status !== "not_written"
                  }
                  type="submit"
                >
                  {evidenceSnapshotExportMaterializationStatus === "saving"
                    ? "Materializing"
                    : "Materialize export"}
                </button>
              </form>
            ) : null}
            {evidenceSnapshotExportMaterializationStatus !== "idle" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {evidenceSnapshotExportMaterializationStatus === "api_materialized"
                  ? "Approved export artifact written to the configured object-store adapter."
                  : evidenceSnapshotExportMaterializationStatus === "saving"
                    ? "Approved export artifact is being written."
                    : "Export materialization failed."}
              </p>
            ) : null}
            {evidenceSnapshotExportRequest?.storage_uri ? (
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5">
                <span>
                  <span className="eyebrow m-0">Artifact</span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExportRequest.storage_adapter} /{" "}
                    {evidenceSnapshotExportRequest.artifact_content_type}
                  </span>
                </span>
                <span>
                  <span className="font-mono text-[13px] break-words">
                    {evidenceSnapshotExportRequest.artifact_checksum_sha256?.slice(0, 12)}
                  </span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {evidenceSnapshotExportRequest.artifact_size_bytes ?? 0} bytes
                  </span>
                </span>
                <span>
                  <span className="eyebrow m-0">
                    {evidenceSnapshotExportRequest.storage_status}
                  </span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{evidenceSnapshotExportRequest.storage_uri}</span>
                </span>
              </div>
            ) : null}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Credential Handles</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedCredentialHandles.length} metadata reference
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">external secret refs only</p>
              </div>
              <KeyRound size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedCredentialHandles.map((handle) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={handle.handle_id}>
                  <span>
                    <span className="eyebrow m-0">{handle.handle_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{handle.secret_provider}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{formatConnectorLabel(handle.rotation_status)}</span>
                </div>
              ))}
            </div>
            {selectedCredentialHandles.map((handle) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${handle.handle_id}-rotation`}>
                <div>
                  <p className="eyebrow m-0">Reference</p>
                  <p className="m-0 font-medium text-ink break-words">{handle.secret_ref}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{handle.purpose}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Rotation</p>
                  <p className="m-0 font-medium text-ink break-words">{handle.rotation_interval_days} days</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{handle.next_rotation_due_at ?? "not scheduled"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Last Evidence</p>
                  <p className="m-0 font-medium text-ink break-words">{handle.last_rotation?.evidence_ref ?? "none"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{handle.last_rotation?.rotated_by ?? handle.created_by}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Raw Value</p>
                  <p className="m-0 font-medium text-ink break-words">Never Stored</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{handle.rotation_count} rotation records</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Checkpoint Claims</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedSyncCheckpointClaims.length} worker claim
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {selectedSyncCheckpointClaimInvariants.length} claim invariant
                </p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedSyncCheckpointClaims.map((claim) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={claim.claim_id}>
                  <span>
                    <span className="eyebrow m-0">{claim.claim_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{claim.checkpoint_id}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{formatConnectorLabel(claim.status)}</span>
                </div>
              ))}
            </div>
            {selectedSyncCheckpointClaimInvariants.length > 0 ? (
              <div className="grid min-w-0 gap-2">
                {selectedSyncCheckpointClaimInvariants.map((invariant) => (
                  <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={`${invariant.claim_id}-${invariant.reason}`}>
                    <span>
                      <span className="eyebrow m-0">{invariant.reason}</span>
                      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{invariant.claim_id}</span>
                    </span>
                    <span className="font-mono text-[13px] break-words">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedSyncCheckpointClaims.map((claim) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${claim.claim_id}-claim`}>
                <div>
                  <p className="eyebrow m-0">Worker</p>
                  <p className="m-0 font-medium text-ink break-words">{claim.claimed_by}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{claim.audit_event_type}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Lease Window</p>
                  <p className="m-0 font-medium text-ink break-words">{claim.lease_expires_at}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{claim.lease_duration_seconds} seconds</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Renewal</p>
                  <p className="m-0 font-medium text-ink break-words">{claim.renewal_count} renewals</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{claim.renewed_by ?? "not renewed"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Release</p>
                  <p className="m-0 font-medium text-ink break-words">{claim.released_by ?? "not released"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{claim.release_reason ?? claim.status}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">External Sync</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {formatCheckpointScalar(claim.claim_result.external_sync_started)}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {formatCheckpointScalar(claim.claim_result.worker_claim_only)}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Secret Material</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {formatCheckpointScalar(claim.claim_result.secret_material_returned)}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{claim.audit_event_id ?? "pending audit"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Sync Checkpoints</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedSyncCheckpoints.length} checkpoint record
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {selectedSyncCheckpointInvariants.length} evidence invariant
                </p>
              </div>
              <ScrollText size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedSyncCheckpoints.map((checkpoint) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={checkpoint.checkpoint_id}>
                  <span>
                    <span className="eyebrow m-0">{checkpoint.checkpoint_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{checkpoint.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{checkpoint.status}</span>
                </div>
              ))}
            </div>
            {selectedSyncCheckpointInvariants.length > 0 ? (
              <div className="grid min-w-0 gap-2">
                {selectedSyncCheckpointInvariants.map((invariant) => (
                  <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={`${invariant.checkpoint_id}-${invariant.reason}`}>
                    <span>
                      <span className="eyebrow m-0">{invariant.reason}</span>
                      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{invariant.checkpoint_id}</span>
                    </span>
                    <span className="font-mono text-[13px] break-words">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedSyncCheckpoints.map((checkpoint) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${checkpoint.checkpoint_id}-summary`}>
                <div>
                  <p className="eyebrow m-0">Sequence</p>
                  <p className="m-0 font-medium text-ink break-words">{checkpoint.sequence}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{checkpoint.checkpoint_type}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Adapter</p>
                  <p className="m-0 font-medium text-ink break-words">{checkpoint.adapter}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{checkpoint.runtime_boundary}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Run</p>
                  <p className="m-0 font-medium text-ink break-words">{checkpoint.run_id}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{checkpoint.created_at}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Cursor</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {formatCheckpointScalar(checkpoint.cursor.high_watermark_kind)}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {formatCheckpointScalar(checkpoint.cursor.high_watermark_value)}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">External Query</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {formatCheckpointScalar(checkpoint.result_summary.external_query_started)}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {formatCheckpointScalar(
                      checkpoint.result_summary.live_query_preflight_status,
                    )}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Secret Material</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {formatCheckpointScalar(
                      checkpoint.result_summary.credential_material_returned,
                    )}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {checkpoint.evidence_refs.length} evidence ref
                  </p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Credential Leases</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedCredentialLeases.length} vault/kms lease
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {selectedCredentialLeaseInvariants.length} lease invariant
                </p>
              </div>
              <KeyRound size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedCredentialLeases.map((lease) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={lease.lease_id}>
                  <span>
                    <span className="eyebrow m-0">{lease.lease_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{lease.lease_mode}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{formatConnectorLabel(lease.status)}</span>
                </div>
              ))}
            </div>
            {selectedCredentialLeaseInvariants.length > 0 ? (
              <div className="grid min-w-0 gap-2">
                {selectedCredentialLeaseInvariants.map((invariant) => (
                  <div
                    className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5"
                    key={`${invariant.lease_id}-${invariant.reason}`}
                  >
                    <span>
                      <span className="eyebrow m-0">{invariant.reason}</span>
                      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{invariant.lease_id}</span>
                    </span>
                    <span className="font-mono text-[13px] break-words">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedCredentialLeases.map((lease) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${lease.lease_id}-evidence`}>
                <div>
                  <p className="eyebrow m-0">Adapter</p>
                  <p className="m-0 font-medium text-ink break-words">{lease.lease_result.adapter}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{lease.lease_result.provider_mode}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Lease Window</p>
                  <p className="m-0 font-medium text-ink break-words">{lease.expires_at}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{lease.renewal_due_at}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Evidence</p>
                  <p className="m-0 font-medium text-ink break-words">{lease.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{lease.lease_result.provider_lease_ref}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Secret Material</p>
                  <p className="m-0 font-medium text-ink break-words">{lease.lease_result.secret_material_returned}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{lease.renewal_count} renewals</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Egress Policies</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedEgressPolicies.length} persisted policy
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {selectedEgressPolicyInvariants.length} policy invariant
                </p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedEgressPolicies.map((policy) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={policy.policy_id}>
                  <span>
                    <span className="eyebrow m-0">{policy.policy_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{policy.status}</span>
                </div>
              ))}
            </div>
            {selectedEgressPolicyInvariants.length > 0 ? (
              <div className="grid min-w-0 gap-2">
                {selectedEgressPolicyInvariants.map((invariant) => (
                  <div
                    className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5"
                    key={`${invariant.policy_id}-${invariant.reason}`}
                  >
                    <span>
                      <span className="eyebrow m-0">{invariant.reason}</span>
                      <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{invariant.policy_id}</span>
                    </span>
                    <span className="font-mono text-[13px] break-words">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedEgressPolicies.map((policy) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${policy.policy_id}-egress`}>
                <div>
                  <p className="eyebrow m-0">Profile</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.connection_profile_id}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.display_name}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Boundary</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.egress_boundary}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.policy_mode}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Runtime</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.runtime_boundary}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.private_endpoint_ref}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Audit Event</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.audit_event_id ?? "pending"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Policy Sets</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedPromotionPolicySets.length} versioned policy set
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">required gate selection and transition evidence</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedPromotionPolicySets.map((policySet) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={policySet.policy_set_id}>
                  <span>
                    <span className="eyebrow m-0">{policySet.policy_set_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policySet.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{policySet.status}</span>
                </div>
              ))}
            </div>
            {selectedPromotionPolicySets.map((policySet) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${policySet.policy_set_id}-summary`}>
                <div>
                  <p className="eyebrow m-0">Version</p>
                  <p className="m-0 font-medium text-ink break-words">{policySet.policy_set_version}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policySet.activation_scope}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Policies</p>
                  <p className="m-0 font-medium text-ink break-words">{policySet.policy_ids.length} required</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policySet.policy_ids.join(", ")}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Activated By</p>
                  <p className="m-0 font-medium text-ink break-words">{policySet.activated_by}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policySet.permission_decision.reason}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Audit Event</p>
                  <p className="m-0 font-medium text-ink break-words">{policySet.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policySet.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Transition</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {policySet.rollback_to_policy_set_id ??
                      policySet.replaces_policy_set_id ??
                      policySet.replaced_by_policy_set_id ??
                      "none"}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {policySet.rollback_workflow_signal_status ??
                      policySet.replacement_workflow_signal_status ??
                      "no transition signal"}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Revision Adoptions</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {policySet.policy_revision_adoptions.length} adopted
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {policySet.policy_revision_adoptions
                      .map(
                        (adoption) =>
                          `${adoption.current_policy_id} -> ${adoption.revised_policy_id}`,
                      )
                      .join(", ") || "none"}
                  </p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Connector Runs</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{selectedRuns.length} audit-backed record</h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">metadata-only evidence</p>
              </div>
              <Cable size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedRuns.map((run) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={run.run_id}>
                  <span>
                    <span className="eyebrow m-0">{run.run_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{run.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{run.status}</span>
                </div>
              ))}
            </div>
            {selectedRuns.map((run) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${run.run_id}-summary`}>
                <div>
                  <p className="eyebrow m-0">Execution</p>
                  <p className="m-0 font-medium text-ink break-words">{formatConnectorLabel(run.execution_mode)}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{run.runtime_boundary}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Runtime Adapter</p>
                  <p className="m-0 font-medium text-ink break-words">{connectorRunRuntimeAdapter(run)}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{connectorRunRuntimeStatus(run)}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">External Sync</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {connectorRunExternalSyncStarted(run) ? "started" : "not started"}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{connectorRunRuntimeEvidence(run)}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Requested By</p>
                  <p className="m-0 font-medium text-ink break-words">{run.requested_by}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{run.created_at}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Audit Event</p>
                  <p className="m-0 font-medium text-ink break-words">{run.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{run.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Credential Handles</p>
                  <p className="m-0 font-medium text-ink break-words">{run.credential_handle_ids.length}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">referenced by id only</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Ontology Proposals</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedOntologyProposals.length} review-only proposal
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">no graph mutation applied</p>
              </div>
              <Database size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedOntologyProposals.map((proposal) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={proposal.proposal_id}>
                  <span>
                    <span className="eyebrow m-0">{proposal.proposal_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{proposal.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{proposal.graph_mutation_status}</span>
                </div>
              ))}
            </div>
            {selectedOntologyProposals.map((proposal) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${proposal.proposal_id}-summary`}>
                <div>
                  <p className="eyebrow m-0">Node</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.node_id}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{proposal.ontology_type}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Write Mode</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.write_mode}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{proposal.status}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Promotion</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.promotion_id ?? "pending"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {proposal.ontology_mutation?.status ?? proposal.graph_mutation_status}
                  </p>
                  {proposal.status === "promoted_to_graph" ? (
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">graph mutation applied</p>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="inline-flex items-center justify-center gap-2 rounded-full border border-mist bg-surface px-4 py-2 text-sm font-medium text-ink transition-all duration-300 select-none hover:border-signal/50 hover:text-signal disabled:cursor-not-allowed disabled:opacity-55 dark:border-white/20 dark:hover:border-signal/60"
                        onClick={() => void promoteOntologyProposal(proposal)}
                        disabled={
                          proposalPromotionStatuses[proposal.proposal_id] === "promoting"
                        }
                      >
                        Promote to graph
                      </button>
                      {proposalPromotionStatuses[proposal.proposal_id] &&
                      proposalPromotionStatuses[proposal.proposal_id] !== "idle" ? (
                        <p
                          className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words"
                          data-testid={`promotion-status-${proposal.proposal_id}`}
                        >
                          {
                            PROPOSAL_PROMOTION_STATUS_LABEL[
                              proposalPromotionStatuses[proposal.proposal_id]
                            ]
                          }
                        </p>
                      ) : null}
                    </>
                  )}
                </div>
                <div>
                  <p className="eyebrow m-0">Policy</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.policy_id ?? "not requested"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {proposal.policy_decision?.status ?? "policy_not_requested"}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Policy Result</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {proposal.policy_decision?.reason ?? "no policy evidence"}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {proposal.policy_decision?.matched_constraints.selection_mode
                      ? `${proposal.policy_decision.enforcement_mode} / ${proposal.policy_decision.matched_constraints.selection_mode}`
                      : (proposal.policy_decision?.enforcement_mode ?? "not enforced")}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Promoted By</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.promoted_by ?? "unassigned"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {proposal.ontology_mutation?.mutation_ref ?? "no graph mutation"}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Audit Event</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{proposal.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Source</p>
                  <p className="m-0 font-medium text-ink break-words">{proposal.source_file_name}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{proposal.source_run_id ?? "preview only"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Manual Imports</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedManualImports.length} approval-gated request
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">workflow and idempotency controls recorded</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {selectedManualImports.map((manualImport) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={manualImport.import_id}>
                  <span>
                    <span className="eyebrow m-0">{manualImport.import_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manualImport.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{manualImport.status}</span>
                </div>
              ))}
            </div>
            {selectedManualImports.map((manualImport) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${manualImport.import_id}-summary`}>
                <div>
                  <p className="eyebrow m-0">Approval</p>
                  <p className="m-0 font-medium text-ink break-words">{manualImport.approval_id}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manualImport.owner_role}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Workflow</p>
                  <p className="m-0 font-medium text-ink break-words">{manualImport.workflow_id}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manualImport.workflow_signal_status}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Decision</p>
                  <p className="m-0 font-medium text-ink break-words">{manualImport.decision ?? "pending"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manualImport.decision_actor_id ?? "unassigned"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Signal</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {manualImport.workflow_signal?.signal_name ?? "pending"}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {manualImport.workflow_signal?.adapter ?? "runtime not signaled"}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Idempotency</p>
                  <p className="m-0 font-medium text-ink break-words">{manualImport.idempotency_key}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manualImport.import_mode}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Graph</p>
                  <p className="m-0 font-medium text-ink break-words">{manualImport.graph_mutation_status}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {manualImport.proposal_ids.length} linked proposal
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Audit Event</p>
                  <p className="m-0 font-medium text-ink break-words">{manualImport.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{manualImport.audit_event_id ?? "pending"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Promotion Policies</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
                  {selectedPromotionPolicies.length} promotion policy
                </h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">authoring and enforcement evidence recorded</p>
              </div>
              <ScrollText size={18} />
            </div>
            <form
              aria-label="Promotion policy authoring"
              className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
              onSubmit={authorPromotionPolicy}
            >
              <Field label="Policy ID">
                <Input
                  aria-label="Policy ID"
                  onChange={(event) =>
                    setPolicyForm((currentForm) => ({
                      ...currentForm,
                      policy_id: event.target.value,
                    }))
                  }
                  pattern="[a-z0-9][a-z0-9_-]*"
                  required
                  type="text"
                  value={policyForm.policy_id}
                />
              </Field>
              <Field label="Status">
                <Select
                  aria-label="Status"
                  onChange={(event) =>
                    setPolicyForm((currentForm) => ({
                      ...currentForm,
                      status: event.target.value,
                    }))
                  }
                  value={policyForm.status}
                >
                  <option value="draft">draft</option>
                </Select>
              </Field>
              <Field label="Enforcement">
                <Select
                  aria-label="Enforcement"
                  onChange={(event) =>
                    setPolicyForm((currentForm) => ({
                      ...currentForm,
                      enforcement_mode: event.target.value,
                    }))
                  }
                  value={policyForm.enforcement_mode}
                >
                  <option value="advisory">advisory</option>
                  <option value="required">required</option>
                </Select>
              </Field>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none"
                disabled={policyAuthoringStatus === "saving"}
                type="submit"
              >
                <ScrollText size={15} />
                {policyAuthoringStatus === "saving" ? "Authoring" : "Author policy"}
              </button>
            </form>
            {policyAuthoringStatus !== "idle" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {policyAuthoringStatus === "api_created"
                  ? "API policy authored"
                  : policyAuthoringStatus === "saving"
                    ? "Policy authoring pending"
                    : "Policy authoring rejected"}
              </p>
            ) : null}
            <form
              aria-label="Promotion policy enablement"
              className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
              onSubmit={enablePromotionPolicy}
            >
              <Field label="Enable Policy ID">
                <Input
                  aria-label="Enable Policy ID"
                  onChange={(event) =>
                    setPolicyEnableForm((currentForm) => ({
                      ...currentForm,
                      policy_id: event.target.value,
                    }))
                  }
                  pattern="[a-z0-9][a-z0-9_-]*"
                  required
                  type="text"
                  value={policyEnableForm.policy_id}
                />
              </Field>
              <Field label="Approval ID">
                <Input
                  aria-label="Approval ID"
                  onChange={(event) =>
                    setPolicyEnableForm((currentForm) => ({
                      ...currentForm,
                      approval_id: event.target.value,
                    }))
                  }
                  required
                  type="text"
                  value={policyEnableForm.approval_id}
                />
              </Field>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none"
                disabled={policyEnableStatus === "saving"}
                type="submit"
              >
                <ShieldCheck size={15} />
                {policyEnableStatus === "saving" ? "Enabling" : "Enable policy"}
              </button>
            </form>
            {policyEnableStatus !== "idle" ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {policyEnableStatus === "api_enabled"
                  ? "API policy enabled"
                  : policyEnableStatus === "saving"
                    ? "Policy enable pending"
                    : "Policy enable rejected"}
              </p>
            ) : null}
            <div className="grid min-w-0 gap-2">
              {selectedPromotionPolicies.map((policy) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={policy.policy_id}>
                  <span>
                    <span className="eyebrow m-0">{policy.policy_id}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.audit_event_type}</span>
                  </span>
                  <span className="font-mono text-[13px] break-words">{policy.status}</span>
                </div>
              ))}
            </div>
            {selectedPromotionPolicies.map((policy) => (
              <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={`${policy.policy_id}-summary`}>
                <div>
                  <p className="eyebrow m-0">Authoring</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.created_by}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.required_authoring_scope}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Promotion Scope</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.required_scopes.join(", ")}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.enforcement_mode}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Manual Import</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.required_manual_import_status}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.required_workflow_signal_status}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Risk</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.allowed_risk_levels.join(", ")}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.allowed_ontology_types.join(", ")}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Review Window</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.review_window_hours}h</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.permission_decision.reason}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Audit Event</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.audit_event_type}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Revision Lineage</p>
                  <p className="m-0 font-medium text-ink break-words">
                    {policy.revises_policy_id ?? policy.replaced_by_policy_id ?? "none"}
                  </p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{policy.revision_idempotency_key ?? "not replayed"}</p>
                </div>
                <div>
                  <p className="eyebrow m-0">Revision Evidence</p>
                  <p className="m-0 font-medium text-ink break-words">{policy.revision_workflow_signal_status ?? "none"}</p>
                  <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {policy.revision_approval_id ?? policy.revision_decision ?? "not required"}
                  </p>
                </div>
              </div>
            ))}
          </section>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Schema Mapping</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{selectedConnector.preview_sample.file_name}</h3>
              </div>
              <FileText size={18} />
            </div>
            <div className="grid min-w-0 gap-2">
              {manifest.schema_fields.map((field) => (
                <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={field.source_column}>
                  <span className="eyebrow m-0">{field.source_column}</span>
                  <span className="font-mono text-[13px] break-words">{field.target_field}</span>
                </div>
              ))}
            </div>
          </section>

          {csvPreviewApplies ? (
            <section className="grid items-start gap-4 border-b border-line/60 pb-4 dark:border-white/10 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.48fr)] [&>*]:min-w-0">
              <div>
                <p className="eyebrow m-0">CSV Preview</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{preview.audit_event_preview.event_type}</h3>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {preview.audit_event_preview.result} / {preview.audit_event_preview.scope}
                </p>
              </div>
              <div className="grid min-w-0 gap-2">
                {preview.proposed_entities.map((entity) => (
                  <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={entity.node_id}>
                    <span className="eyebrow m-0">{entity.node_id}</span>
                    <span className="font-mono text-[13px] break-words">{entity.ontology_type}</span>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="grid min-w-0 gap-2.5">
            {registry.connector_notes
              .concat(manifestRegistry.manifest_notes)
              .concat(configurationRegistry.configuration_notes)
              .concat(credentialHandleRegistry.handle_notes)
              .concat(credentialLeaseRegistry.lease_notes)
              .concat(egressPolicyRegistry.policy_notes)
              .concat(runRegistry.run_notes)
              .concat(syncCheckpointRegistry.checkpoint_notes)
              .concat(syncCheckpointClaimRegistry.claim_notes)
              .concat(evidenceInvariantReport.report_notes)
              .concat(evidenceSnapshotHistory.history_notes)
              .concat(ontologyProposalRegistry.proposal_notes)
              .concat(manualImportRegistry.import_notes)
              .concat(promotionPolicyRegistry.policy_notes)
              .concat(promotionPolicySetRegistry.policy_set_notes)
              .concat(selectedConfiguration?.notes ?? [])
              .concat(selectedManifestRecord?.notes ?? [])
              .concat(selectedCredentialHandles.flatMap((handle) => handle.notes))
              .concat(selectedCredentialLeases.flatMap((lease) => lease.notes))
              .concat(selectedEgressPolicies.flatMap((policy) => policy.notes))
              .concat(selectedRuns.flatMap((run) => run.notes))
              .concat(selectedSyncCheckpoints.flatMap((checkpoint) => checkpoint.notes))
              .concat(selectedSyncCheckpointClaims.flatMap((claim) => claim.notes))
              .concat(selectedOntologyProposals.flatMap((proposal) => proposal.notes))
              .concat(selectedManualImports.flatMap((manualImport) => manualImport.notes))
              .concat(selectedPromotionPolicies.flatMap((policy) => policy.notes))
              .concat(selectedPromotionPolicySets.flatMap((policySet) => policySet.notes))
              .concat(csvPreviewApplies ? preview.preview_notes : [])
              .map((note, index) => (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={`${note}-${index}`}>
                {note}
              </p>
              ))}
          </div>
        </section>
      </div>
    </div>
  );
}
