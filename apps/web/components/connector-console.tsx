"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Cable, Database, FileText, KeyRound, ScrollText, ShieldCheck } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api-status";
import {
  buildConnectorSyncCheckpointClaimQueryPath,
  buildConnectorSyncCheckpointQueryPath,
  buildConnectorPromotionPolicyDraftRequest,
  buildConnectorPromotionPolicyEnableRequest,
  filterConnectorCredentialLeaseInvariantsByLeases,
  filterConnectorEgressPolicyInvariantsByPolicies,
  filterConnectorSyncCheckpointClaimInvariantsByClaims,
  filterConnectorSyncCheckpointInvariantsByCheckpoints,
  filterConnectorSyncCheckpointClaimsByCheckpoints,
  filterConnectorSyncCheckpointsByConnector,
  formatConnectorLabel,
  summarizeConnectorEvidenceInvariantCounts,
  type ConnectorCsvPreviewResult,
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
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";

type ConnectorSource = "loading" | "api" | "unavailable";
type PolicyAuthoringStatus = "idle" | "saving" | "api_created" | "error";
type PolicyEnableStatus = "idle" | "saving" | "api_enabled" | "error";

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

async function fetchConnectorJson<T>(
  apiBaseUrl: string,
  path: string,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    signal,
    cache: "no-store",
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

async function fetchConnectorData(apiBaseUrl: string, signal?: AbortSignal) {
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
    ontologyProposalData,
    manualImportData,
    promotionPolicyData,
    promotionPolicySetData,
  ] = await Promise.all([
    fetchConnectorJson<ManufacturingConnectorRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorManifestRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/manifests",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorConfigurationRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/configurations",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorCredentialHandleRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/credential-handles",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorCredentialLeaseRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/credential-leases",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorEgressPolicyRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/egress-policies",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorRunRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/runs",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorSyncCheckpointRegistry>(
      apiBaseUrl,
      buildConnectorSyncCheckpointQueryPath(CONNECTOR_TENANT_ID),
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorSyncCheckpointClaimRegistry>(
      apiBaseUrl,
      buildConnectorSyncCheckpointClaimQueryPath(CONNECTOR_TENANT_ID),
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorEvidenceInvariantReport>(
      apiBaseUrl,
      `/demo/manufacturing/connectors/evidence-invariants?tenant_id=${CONNECTOR_TENANT_ID}`,
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorOntologyProposalRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/ontology-proposals",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorManualImportRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/manual-imports",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorPromotionPolicyRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/promotion-policies",
      signal,
    ),
    fetchConnectorJson<ManufacturingConnectorPromotionPolicySetRegistry>(
      apiBaseUrl,
      "/demo/manufacturing/connectors/promotion-policy-sets",
      signal,
    ),
  ]);

  return {
    configurationData,
    credentialHandleData,
    credentialLeaseData,
    evidenceInvariantData,
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
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function loadInitialConnectors() {
      try {
        const data = await fetchConnectorData(apiBaseUrl, controller.signal);
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
        setOntologyProposalRegistry(data.ontologyProposalData);
        setManualImportRegistry(data.manualImportData);
        setPromotionPolicyRegistry(data.promotionPolicyData);
        setPromotionPolicySetRegistry(data.promotionPolicySetData);
        setPreview(EMPTY_CSV_PREVIEW);
        setSelectedConnectorId(data.registryData.connectors[0]?.manifest.connector_id ?? "");
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setSource("unavailable");
        }
      }
    }

    void loadInitialConnectors();

    return () => controller.abort();
  }, [apiBaseUrl]);

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

  async function refreshConnectorData() {
    const data = await fetchConnectorData(apiBaseUrl);
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
      await fetchConnectorJson<unknown>(
        apiBaseUrl,
        "/demo/manufacturing/connectors/promotion-policies",
        undefined,
        {
          body: JSON.stringify(request),
          method: "POST",
        },
      );
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
        apiBaseUrl,
        `/demo/manufacturing/connectors/promotion-policies/${request.policy_id}/enable`,
        undefined,
        {
          body: JSON.stringify(request),
          method: "POST",
        },
      );
      await refreshConnectorData();
      setPolicyEnableStatus("api_enabled");
    } catch {
      setPolicyEnableStatus("error");
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
    .concat(ontologyProposalRegistry.metrics)
    .concat(manualImportRegistry.metrics)
    .concat(promotionPolicyRegistry.metrics)
    .concat(promotionPolicySetRegistry.metrics);

  if (!selectedConnector) {
    return (
      <div className="stack">
        <section className="panel overview-context">
          <div>
            <p className="section-label">Connector Foundation</p>
            <h2 className="panel-title">{registry.plant_name}</h2>
            <p className="row-detail">
              {registry.scenario} / {registry.tenant_id}
            </p>
          </div>
          <div className="overview-meta" aria-label="Connector source and status">
            <span className={`status-pill ${sourcePillClass(source)}`}>
              <Cable size={15} />
              {sourceLabel(source)}
            </span>
            <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
              <ShieldCheck size={15} />
              {platformStatusLabel(registry.registry_status)}
            </span>
            <span className="mono">{formatOverviewTimestamp("2026-06-22T09:30:00+02:00")}</span>
          </div>
        </section>

        {connectorMetrics.length > 0 ? (
          <div className="metric-grid">
            {connectorMetrics.map((metric) => (
              <article className="metric-card compact-card" key={`${metric.label}-${metric.detail}`}>
                <div className="row">
                  <p className="metric-label">{metric.label}</p>
                  <span className={`status-pill ${platformStatusClass(metric.status)}`}>
                    {platformStatusLabel(metric.status)}
                  </span>
                </div>
                <p className="metric-value">{metric.value}</p>
                <p className="metric-detail">{metric.detail}</p>
              </article>
            ))}
          </div>
        ) : null}

        <section className="panel">
          <div className="audit-list-header">
            <div>
              <p className="section-label">Manifests</p>
              <h2 className="panel-title">
                {source === "loading" ? "Loading connector API" : "Connector API unavailable"}
              </h2>
              <p className="row-detail">
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
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Connector Foundation</p>
          <h2 className="panel-title">{registry.plant_name}</h2>
          <p className="row-detail">
            {registry.scenario} / {registry.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Connector source and status">
          <span className={`status-pill ${sourcePillClass(source)}`}>
            <Cable size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
            <ShieldCheck size={15} />
            {platformStatusLabel(registry.registry_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp("2026-06-22T09:30:00+02:00")}</span>
        </div>
      </section>

      <div className="metric-grid">
        {connectorMetrics.map((metric) => (
          <article
            className="metric-card compact-card"
            key={`${metric.label}-${metric.detail}`}
          >
            <div className="row">
              <p className="metric-label">{metric.label}</p>
              <span className={`status-pill ${platformStatusClass(metric.status)}`}>
                {platformStatusLabel(metric.status)}
              </span>
            </div>
            <p className="metric-value">{metric.value}</p>
            <p className="metric-detail">{metric.detail}</p>
          </article>
        ))}
      </div>

      <div className="simulation-layout">
        <section className="panel">
          <div className="audit-list-header">
            <div>
              <p className="section-label">Manifests</p>
              <h2 className="panel-title">{registry.connectors.length} connector</h2>
            </div>
            <span className="status-pill signal-watch">
              <Database size={15} />
              Preview only
            </span>
          </div>

          <div className="workflow-list">
            {registry.connectors.map((connector) => {
              const isSelected = connector.manifest.connector_id === manifest.connector_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`workflow-list-item${isSelected ? " active" : ""}`}
                  key={connector.manifest.connector_id}
                  onClick={() => setSelectedConnectorId(connector.manifest.connector_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{connector.manifest.display_name}</span>
                    <span className="row-detail mono">{connector.manifest.connector_id}</span>
                    <span className="row-detail">
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

        <section className="panel audit-detail">
          <div className="workflow-detail-header">
            <div>
              <p className="section-label">{manifest.connector_type}</p>
              <h2 className="panel-title">{manifest.display_name}</h2>
              <p className="row-detail mono">{manifest.connector_id}</p>
            </div>
            <div className="status-stack">
              <span className="status-pill signal-watch">{manifest.runtime_boundary}</span>
              <span className="status-pill status-checking">{manifest.version}</span>
            </div>
          </div>

          <div className="audit-detail-grid">
            <div>
              <p className="metric-label">Sync Mode</p>
              <p className="row-title">{formatConnectorLabel(selectedPreviewMode)}</p>
              <p className="row-detail">{manifest.sync_modes.join(", ")}</p>
            </div>
            <div>
              <p className="metric-label">Rows</p>
              <p className="row-title">{selectedRecordCount}</p>
              <p className="row-detail">{selectedRecordDetail}</p>
            </div>
            <div>
              <p className="metric-label">Credentials</p>
              <p className="row-title">{manifest.credential_requirements.storage}</p>
              <p className="row-detail">{credentialDetail}</p>
            </div>
            <div>
              <p className="metric-label">Payload</p>
              <p className="row-title">{selectedConnector.runtime_policy.payload_policy}</p>
              <p className="row-detail">{selectedConnector.runtime_policy.egress_policy}</p>
            </div>
          </div>

          <div className="workflow-columns">
            <section>
              <p className="section-label">Required Permissions</p>
              <div className="tag-list">
                {manifest.required_permissions.map((permission) => (
                  <span className="tag" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Blocked Operations</p>
              <div className="tag-list">
                {selectedConnector.runtime_policy.blocked_operations.map((operation) => (
                  <span className="tag" key={operation}>
                    {operation}
                  </span>
                ))}
              </div>
            </section>
          </div>

          {selectedConfiguration ? (
            <section className="audit-payload">
              <div className="audit-payload-header">
                <div>
                  <p className="section-label">Tenant Configuration</p>
                  <h3 className="subsection-title">{selectedConfiguration.display_name}</h3>
                  <p className="row-detail mono">{selectedConfiguration.status}</p>
                </div>
                <Database size={18} />
              </div>
              <div className="audit-detail-grid">
                <div>
                  <p className="metric-label">Sync</p>
                  <p className="row-title">{selectedConfiguration.sync_mode}</p>
                  <p className="row-detail">{selectedConfiguration.runtime_boundary}</p>
                </div>
                <div>
                  <p className="metric-label">Created By</p>
                  <p className="row-title">{selectedConfiguration.created_by}</p>
                  <p className="row-detail">tenant-scoped configuration</p>
                </div>
                <div>
                  <p className="metric-label">Credential Handles</p>
                  <p className="row-title">{selectedConfiguration.credential_ref_ids.length}</p>
                  <p className="row-detail">no raw credential values</p>
                </div>
                <div>
                  <p className="metric-label">Mode</p>
                  <p className="row-title">Preview only</p>
                  <p className="row-detail">no scheduled sync</p>
                </div>
              </div>
              <div className="payload-grid">
                {Object.entries(selectedConfiguration.configuration_payload).map(([key, value]) => (
                  <div className="payload-row" key={key}>
                    <span className="metric-label">{key}</span>
                    <span className="mono">{value}</span>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {selectedManifestRecord ? (
            <section className="audit-payload">
              <div className="audit-payload-header">
                <div>
                  <p className="section-label">Persisted Manifest</p>
                  <h3 className="subsection-title">{selectedManifestRecord.status}</h3>
                  <p className="row-detail mono">{selectedManifestRecord.manifest_id}</p>
                </div>
                <ScrollText size={18} />
              </div>
              <div className="audit-detail-grid">
                <div>
                  <p className="metric-label">Registered By</p>
                  <p className="row-title">{selectedManifestRecord.registered_by}</p>
                  <p className="row-detail">{selectedManifestRecord.audit_event_type}</p>
                </div>
                <div>
                  <p className="metric-label">Manifest Type</p>
                  <p className="row-title">{formatConnectorLabel(selectedManifestRecord.connector_type)}</p>
                  <p className="row-detail">{selectedManifestRecord.source_type}</p>
                </div>
                <div>
                  <p className="metric-label">Runtime</p>
                  <p className="row-title">{selectedManifestRecord.runtime_boundary}</p>
                  <p className="row-detail">{selectedManifestRecord.version}</p>
                </div>
              </div>
            </section>
          ) : null}

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Evidence Invariant Report</p>
                <h3 className="subsection-title">
                  {evidenceInvariantReport.invariants.length} aggregate finding
                </h3>
                <p className="row-detail">{evidenceInvariantReport.registry_status}</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="audit-detail-grid">
              {evidenceInvariantCounts.map((count) => (
                <div key={count.label}>
                  <p className="metric-label">{count.label}</p>
                  <p className="row-title">{count.value}</p>
                  <p className="row-detail">append-only audit invariant</p>
                </div>
              ))}
            </div>
            {evidenceInvariantReport.invariants.length > 0 ? (
              <div className="payload-grid">
                {evidenceInvariantReport.invariants.slice(0, 8).map((invariant) => (
                  <div
                    className="payload-row"
                    key={`${invariant.evidence_type}-${invariant.subject_id}-${invariant.reason}`}
                  >
                    <span>
                      <span className="metric-label">
                        {formatConnectorLabel(invariant.evidence_type)}
                      </span>
                      <span className="row-detail">{invariant.subject_id}</span>
                    </span>
                    <span className="mono">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Credential Handles</p>
                <h3 className="subsection-title">
                  {selectedCredentialHandles.length} metadata reference
                </h3>
                <p className="row-detail">external secret refs only</p>
              </div>
              <KeyRound size={18} />
            </div>
            <div className="payload-grid">
              {selectedCredentialHandles.map((handle) => (
                <div className="payload-row" key={handle.handle_id}>
                  <span>
                    <span className="metric-label">{handle.handle_id}</span>
                    <span className="row-detail">{handle.secret_provider}</span>
                  </span>
                  <span className="mono">{formatConnectorLabel(handle.rotation_status)}</span>
                </div>
              ))}
            </div>
            {selectedCredentialHandles.map((handle) => (
              <div className="audit-detail-grid" key={`${handle.handle_id}-rotation`}>
                <div>
                  <p className="metric-label">Reference</p>
                  <p className="row-title">{handle.secret_ref}</p>
                  <p className="row-detail">{handle.purpose}</p>
                </div>
                <div>
                  <p className="metric-label">Rotation</p>
                  <p className="row-title">{handle.rotation_interval_days} days</p>
                  <p className="row-detail">{handle.next_rotation_due_at ?? "not scheduled"}</p>
                </div>
                <div>
                  <p className="metric-label">Last Evidence</p>
                  <p className="row-title">{handle.last_rotation?.evidence_ref ?? "none"}</p>
                  <p className="row-detail">{handle.last_rotation?.rotated_by ?? handle.created_by}</p>
                </div>
                <div>
                  <p className="metric-label">Raw Value</p>
                  <p className="row-title">Never Stored</p>
                  <p className="row-detail">{handle.rotation_count} rotation records</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Checkpoint Claims</p>
                <h3 className="subsection-title">
                  {selectedSyncCheckpointClaims.length} worker claim
                </h3>
                <p className="row-detail">
                  {selectedSyncCheckpointClaimInvariants.length} claim invariant
                </p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="payload-grid">
              {selectedSyncCheckpointClaims.map((claim) => (
                <div className="payload-row" key={claim.claim_id}>
                  <span>
                    <span className="metric-label">{claim.claim_id}</span>
                    <span className="row-detail">{claim.checkpoint_id}</span>
                  </span>
                  <span className="mono">{formatConnectorLabel(claim.status)}</span>
                </div>
              ))}
            </div>
            {selectedSyncCheckpointClaimInvariants.length > 0 ? (
              <div className="payload-grid">
                {selectedSyncCheckpointClaimInvariants.map((invariant) => (
                  <div className="payload-row" key={`${invariant.claim_id}-${invariant.reason}`}>
                    <span>
                      <span className="metric-label">{invariant.reason}</span>
                      <span className="row-detail">{invariant.claim_id}</span>
                    </span>
                    <span className="mono">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedSyncCheckpointClaims.map((claim) => (
              <div className="audit-detail-grid" key={`${claim.claim_id}-claim`}>
                <div>
                  <p className="metric-label">Worker</p>
                  <p className="row-title">{claim.claimed_by}</p>
                  <p className="row-detail">{claim.audit_event_type}</p>
                </div>
                <div>
                  <p className="metric-label">Lease Window</p>
                  <p className="row-title">{claim.lease_expires_at}</p>
                  <p className="row-detail">{claim.lease_duration_seconds} seconds</p>
                </div>
                <div>
                  <p className="metric-label">Renewal</p>
                  <p className="row-title">{claim.renewal_count} renewals</p>
                  <p className="row-detail">{claim.renewed_by ?? "not renewed"}</p>
                </div>
                <div>
                  <p className="metric-label">Release</p>
                  <p className="row-title">{claim.released_by ?? "not released"}</p>
                  <p className="row-detail">{claim.release_reason ?? claim.status}</p>
                </div>
                <div>
                  <p className="metric-label">External Sync</p>
                  <p className="row-title">
                    {formatCheckpointScalar(claim.claim_result.external_sync_started)}
                  </p>
                  <p className="row-detail">
                    {formatCheckpointScalar(claim.claim_result.worker_claim_only)}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Secret Material</p>
                  <p className="row-title">
                    {formatCheckpointScalar(claim.claim_result.secret_material_returned)}
                  </p>
                  <p className="row-detail">{claim.audit_event_id ?? "pending audit"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Sync Checkpoints</p>
                <h3 className="subsection-title">
                  {selectedSyncCheckpoints.length} checkpoint record
                </h3>
                <p className="row-detail">
                  {selectedSyncCheckpointInvariants.length} evidence invariant
                </p>
              </div>
              <ScrollText size={18} />
            </div>
            <div className="payload-grid">
              {selectedSyncCheckpoints.map((checkpoint) => (
                <div className="payload-row" key={checkpoint.checkpoint_id}>
                  <span>
                    <span className="metric-label">{checkpoint.checkpoint_id}</span>
                    <span className="row-detail">{checkpoint.audit_event_type}</span>
                  </span>
                  <span className="mono">{checkpoint.status}</span>
                </div>
              ))}
            </div>
            {selectedSyncCheckpointInvariants.length > 0 ? (
              <div className="payload-grid">
                {selectedSyncCheckpointInvariants.map((invariant) => (
                  <div className="payload-row" key={`${invariant.checkpoint_id}-${invariant.reason}`}>
                    <span>
                      <span className="metric-label">{invariant.reason}</span>
                      <span className="row-detail">{invariant.checkpoint_id}</span>
                    </span>
                    <span className="mono">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedSyncCheckpoints.map((checkpoint) => (
              <div className="audit-detail-grid" key={`${checkpoint.checkpoint_id}-summary`}>
                <div>
                  <p className="metric-label">Sequence</p>
                  <p className="row-title">{checkpoint.sequence}</p>
                  <p className="row-detail">{checkpoint.checkpoint_type}</p>
                </div>
                <div>
                  <p className="metric-label">Adapter</p>
                  <p className="row-title">{checkpoint.adapter}</p>
                  <p className="row-detail">{checkpoint.runtime_boundary}</p>
                </div>
                <div>
                  <p className="metric-label">Run</p>
                  <p className="row-title">{checkpoint.run_id}</p>
                  <p className="row-detail">{checkpoint.created_at}</p>
                </div>
                <div>
                  <p className="metric-label">Cursor</p>
                  <p className="row-title">
                    {formatCheckpointScalar(checkpoint.cursor.high_watermark_kind)}
                  </p>
                  <p className="row-detail">
                    {formatCheckpointScalar(checkpoint.cursor.high_watermark_value)}
                  </p>
                </div>
                <div>
                  <p className="metric-label">External Query</p>
                  <p className="row-title">
                    {formatCheckpointScalar(checkpoint.result_summary.external_query_started)}
                  </p>
                  <p className="row-detail">
                    {formatCheckpointScalar(
                      checkpoint.result_summary.live_query_preflight_status,
                    )}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Secret Material</p>
                  <p className="row-title">
                    {formatCheckpointScalar(
                      checkpoint.result_summary.credential_material_returned,
                    )}
                  </p>
                  <p className="row-detail">
                    {checkpoint.evidence_refs.length} evidence ref
                  </p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Credential Leases</p>
                <h3 className="subsection-title">
                  {selectedCredentialLeases.length} vault/kms lease
                </h3>
                <p className="row-detail">
                  {selectedCredentialLeaseInvariants.length} lease invariant
                </p>
              </div>
              <KeyRound size={18} />
            </div>
            <div className="payload-grid">
              {selectedCredentialLeases.map((lease) => (
                <div className="payload-row" key={lease.lease_id}>
                  <span>
                    <span className="metric-label">{lease.lease_id}</span>
                    <span className="row-detail">{lease.lease_mode}</span>
                  </span>
                  <span className="mono">{formatConnectorLabel(lease.status)}</span>
                </div>
              ))}
            </div>
            {selectedCredentialLeaseInvariants.length > 0 ? (
              <div className="payload-grid">
                {selectedCredentialLeaseInvariants.map((invariant) => (
                  <div
                    className="payload-row"
                    key={`${invariant.lease_id}-${invariant.reason}`}
                  >
                    <span>
                      <span className="metric-label">{invariant.reason}</span>
                      <span className="row-detail">{invariant.lease_id}</span>
                    </span>
                    <span className="mono">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedCredentialLeases.map((lease) => (
              <div className="audit-detail-grid" key={`${lease.lease_id}-evidence`}>
                <div>
                  <p className="metric-label">Adapter</p>
                  <p className="row-title">{lease.lease_result.adapter}</p>
                  <p className="row-detail">{lease.lease_result.provider_mode}</p>
                </div>
                <div>
                  <p className="metric-label">Lease Window</p>
                  <p className="row-title">{lease.expires_at}</p>
                  <p className="row-detail">{lease.renewal_due_at}</p>
                </div>
                <div>
                  <p className="metric-label">Evidence</p>
                  <p className="row-title">{lease.audit_event_type}</p>
                  <p className="row-detail">{lease.lease_result.provider_lease_ref}</p>
                </div>
                <div>
                  <p className="metric-label">Secret Material</p>
                  <p className="row-title">{lease.lease_result.secret_material_returned}</p>
                  <p className="row-detail">{lease.renewal_count} renewals</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Egress Policies</p>
                <h3 className="subsection-title">
                  {selectedEgressPolicies.length} persisted policy
                </h3>
                <p className="row-detail">
                  {selectedEgressPolicyInvariants.length} policy invariant
                </p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="payload-grid">
              {selectedEgressPolicies.map((policy) => (
                <div className="payload-row" key={policy.policy_id}>
                  <span>
                    <span className="metric-label">{policy.policy_id}</span>
                    <span className="row-detail">{policy.audit_event_type}</span>
                  </span>
                  <span className="mono">{policy.status}</span>
                </div>
              ))}
            </div>
            {selectedEgressPolicyInvariants.length > 0 ? (
              <div className="payload-grid">
                {selectedEgressPolicyInvariants.map((invariant) => (
                  <div
                    className="payload-row"
                    key={`${invariant.policy_id}-${invariant.reason}`}
                  >
                    <span>
                      <span className="metric-label">{invariant.reason}</span>
                      <span className="row-detail">{invariant.policy_id}</span>
                    </span>
                    <span className="mono">{invariant.audit_event_id ?? "no audit"}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {selectedEgressPolicies.map((policy) => (
              <div className="audit-detail-grid" key={`${policy.policy_id}-egress`}>
                <div>
                  <p className="metric-label">Profile</p>
                  <p className="row-title">{policy.connection_profile_id}</p>
                  <p className="row-detail">{policy.display_name}</p>
                </div>
                <div>
                  <p className="metric-label">Boundary</p>
                  <p className="row-title">{policy.egress_boundary}</p>
                  <p className="row-detail">{policy.policy_mode}</p>
                </div>
                <div>
                  <p className="metric-label">Runtime</p>
                  <p className="row-title">{policy.runtime_boundary}</p>
                  <p className="row-detail">{policy.private_endpoint_ref}</p>
                </div>
                <div>
                  <p className="metric-label">Audit Event</p>
                  <p className="row-title">{policy.audit_event_type}</p>
                  <p className="row-detail">{policy.audit_event_id ?? "pending"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Policy Sets</p>
                <h3 className="subsection-title">
                  {selectedPromotionPolicySets.length} versioned policy set
                </h3>
                <p className="row-detail">required gate selection and transition evidence</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="payload-grid">
              {selectedPromotionPolicySets.map((policySet) => (
                <div className="payload-row" key={policySet.policy_set_id}>
                  <span>
                    <span className="metric-label">{policySet.policy_set_id}</span>
                    <span className="row-detail">{policySet.audit_event_type}</span>
                  </span>
                  <span className="mono">{policySet.status}</span>
                </div>
              ))}
            </div>
            {selectedPromotionPolicySets.map((policySet) => (
              <div className="audit-detail-grid" key={`${policySet.policy_set_id}-summary`}>
                <div>
                  <p className="metric-label">Version</p>
                  <p className="row-title">{policySet.policy_set_version}</p>
                  <p className="row-detail">{policySet.activation_scope}</p>
                </div>
                <div>
                  <p className="metric-label">Policies</p>
                  <p className="row-title">{policySet.policy_ids.length} required</p>
                  <p className="row-detail">{policySet.policy_ids.join(", ")}</p>
                </div>
                <div>
                  <p className="metric-label">Activated By</p>
                  <p className="row-title">{policySet.activated_by}</p>
                  <p className="row-detail">{policySet.permission_decision.reason}</p>
                </div>
                <div>
                  <p className="metric-label">Audit Event</p>
                  <p className="row-title">{policySet.audit_event_type}</p>
                  <p className="row-detail">{policySet.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="metric-label">Transition</p>
                  <p className="row-title">
                    {policySet.rollback_to_policy_set_id ??
                      policySet.replaces_policy_set_id ??
                      policySet.replaced_by_policy_set_id ??
                      "none"}
                  </p>
                  <p className="row-detail">
                    {policySet.rollback_workflow_signal_status ??
                      policySet.replacement_workflow_signal_status ??
                      "no transition signal"}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Revision Adoptions</p>
                  <p className="row-title">
                    {policySet.policy_revision_adoptions.length} adopted
                  </p>
                  <p className="row-detail">
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

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Connector Runs</p>
                <h3 className="subsection-title">{selectedRuns.length} audit-backed record</h3>
                <p className="row-detail">metadata-only evidence</p>
              </div>
              <Cable size={18} />
            </div>
            <div className="payload-grid">
              {selectedRuns.map((run) => (
                <div className="payload-row" key={run.run_id}>
                  <span>
                    <span className="metric-label">{run.run_id}</span>
                    <span className="row-detail">{run.audit_event_type}</span>
                  </span>
                  <span className="mono">{run.status}</span>
                </div>
              ))}
            </div>
            {selectedRuns.map((run) => (
              <div className="audit-detail-grid" key={`${run.run_id}-summary`}>
                <div>
                  <p className="metric-label">Execution</p>
                  <p className="row-title">{formatConnectorLabel(run.execution_mode)}</p>
                  <p className="row-detail">{run.runtime_boundary}</p>
                </div>
                <div>
                  <p className="metric-label">Runtime Adapter</p>
                  <p className="row-title">{connectorRunRuntimeAdapter(run)}</p>
                  <p className="row-detail">{connectorRunRuntimeStatus(run)}</p>
                </div>
                <div>
                  <p className="metric-label">External Sync</p>
                  <p className="row-title">
                    {connectorRunExternalSyncStarted(run) ? "started" : "not started"}
                  </p>
                  <p className="row-detail">{connectorRunRuntimeEvidence(run)}</p>
                </div>
                <div>
                  <p className="metric-label">Requested By</p>
                  <p className="row-title">{run.requested_by}</p>
                  <p className="row-detail">{run.created_at}</p>
                </div>
                <div>
                  <p className="metric-label">Audit Event</p>
                  <p className="row-title">{run.audit_event_type}</p>
                  <p className="row-detail">{run.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="metric-label">Credential Handles</p>
                  <p className="row-title">{run.credential_handle_ids.length}</p>
                  <p className="row-detail">referenced by id only</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Ontology Proposals</p>
                <h3 className="subsection-title">
                  {selectedOntologyProposals.length} review-only proposal
                </h3>
                <p className="row-detail">no graph mutation applied</p>
              </div>
              <Database size={18} />
            </div>
            <div className="payload-grid">
              {selectedOntologyProposals.map((proposal) => (
                <div className="payload-row" key={proposal.proposal_id}>
                  <span>
                    <span className="metric-label">{proposal.proposal_id}</span>
                    <span className="row-detail">{proposal.audit_event_type}</span>
                  </span>
                  <span className="mono">{proposal.graph_mutation_status}</span>
                </div>
              ))}
            </div>
            {selectedOntologyProposals.map((proposal) => (
              <div className="audit-detail-grid" key={`${proposal.proposal_id}-summary`}>
                <div>
                  <p className="metric-label">Node</p>
                  <p className="row-title">{proposal.node_id}</p>
                  <p className="row-detail">{proposal.ontology_type}</p>
                </div>
                <div>
                  <p className="metric-label">Write Mode</p>
                  <p className="row-title">{proposal.write_mode}</p>
                  <p className="row-detail">{proposal.status}</p>
                </div>
                <div>
                  <p className="metric-label">Promotion</p>
                  <p className="row-title">{proposal.promotion_id ?? "pending"}</p>
                  <p className="row-detail">
                    {proposal.ontology_mutation?.status ?? proposal.graph_mutation_status}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Policy</p>
                  <p className="row-title">{proposal.policy_id ?? "not requested"}</p>
                  <p className="row-detail">
                    {proposal.policy_decision?.status ?? "policy_not_requested"}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Policy Result</p>
                  <p className="row-title">
                    {proposal.policy_decision?.reason ?? "no policy evidence"}
                  </p>
                  <p className="row-detail">
                    {proposal.policy_decision?.matched_constraints.selection_mode
                      ? `${proposal.policy_decision.enforcement_mode} / ${proposal.policy_decision.matched_constraints.selection_mode}`
                      : (proposal.policy_decision?.enforcement_mode ?? "not enforced")}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Promoted By</p>
                  <p className="row-title">{proposal.promoted_by ?? "unassigned"}</p>
                  <p className="row-detail">
                    {proposal.ontology_mutation?.mutation_ref ?? "no graph mutation"}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Audit Event</p>
                  <p className="row-title">{proposal.audit_event_type}</p>
                  <p className="row-detail">{proposal.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="metric-label">Source</p>
                  <p className="row-title">{proposal.source_file_name}</p>
                  <p className="row-detail">{proposal.source_run_id ?? "preview only"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Manual Imports</p>
                <h3 className="subsection-title">
                  {selectedManualImports.length} approval-gated request
                </h3>
                <p className="row-detail">workflow and idempotency controls recorded</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="payload-grid">
              {selectedManualImports.map((manualImport) => (
                <div className="payload-row" key={manualImport.import_id}>
                  <span>
                    <span className="metric-label">{manualImport.import_id}</span>
                    <span className="row-detail">{manualImport.audit_event_type}</span>
                  </span>
                  <span className="mono">{manualImport.status}</span>
                </div>
              ))}
            </div>
            {selectedManualImports.map((manualImport) => (
              <div className="audit-detail-grid" key={`${manualImport.import_id}-summary`}>
                <div>
                  <p className="metric-label">Approval</p>
                  <p className="row-title">{manualImport.approval_id}</p>
                  <p className="row-detail">{manualImport.owner_role}</p>
                </div>
                <div>
                  <p className="metric-label">Workflow</p>
                  <p className="row-title">{manualImport.workflow_id}</p>
                  <p className="row-detail">{manualImport.workflow_signal_status}</p>
                </div>
                <div>
                  <p className="metric-label">Decision</p>
                  <p className="row-title">{manualImport.decision ?? "pending"}</p>
                  <p className="row-detail">{manualImport.decision_actor_id ?? "unassigned"}</p>
                </div>
                <div>
                  <p className="metric-label">Signal</p>
                  <p className="row-title">
                    {manualImport.workflow_signal?.signal_name ?? "pending"}
                  </p>
                  <p className="row-detail">
                    {manualImport.workflow_signal?.adapter ?? "runtime not signaled"}
                  </p>
                </div>
                <div>
                  <p className="metric-label">Idempotency</p>
                  <p className="row-title">{manualImport.idempotency_key}</p>
                  <p className="row-detail">{manualImport.import_mode}</p>
                </div>
                <div>
                  <p className="metric-label">Graph</p>
                  <p className="row-title">{manualImport.graph_mutation_status}</p>
                  <p className="row-detail">
                    {manualImport.proposal_ids.length} linked proposal
                  </p>
                </div>
                <div>
                  <p className="metric-label">Audit Event</p>
                  <p className="row-title">{manualImport.audit_event_type}</p>
                  <p className="row-detail">{manualImport.audit_event_id ?? "pending"}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Promotion Policies</p>
                <h3 className="subsection-title">
                  {selectedPromotionPolicies.length} promotion policy
                </h3>
                <p className="row-detail">authoring and enforcement evidence recorded</p>
              </div>
              <ScrollText size={18} />
            </div>
            <form
              aria-label="Promotion policy authoring"
              className="policy-authoring-form"
              onSubmit={authorPromotionPolicy}
            >
              <label>
                <span className="metric-label">Policy ID</span>
                <input
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
              </label>
              <label>
                <span className="metric-label">Status</span>
                <select
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
                </select>
              </label>
              <label>
                <span className="metric-label">Enforcement</span>
                <select
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
                </select>
              </label>
              <button
                className="command-button"
                disabled={policyAuthoringStatus === "saving"}
                type="submit"
              >
                <ScrollText size={15} />
                {policyAuthoringStatus === "saving" ? "Authoring" : "Author policy"}
              </button>
            </form>
            {policyAuthoringStatus !== "idle" ? (
              <p className="row-detail">
                {policyAuthoringStatus === "api_created"
                  ? "API policy authored"
                  : policyAuthoringStatus === "saving"
                    ? "Policy authoring pending"
                    : "Policy authoring rejected"}
              </p>
            ) : null}
            <form
              aria-label="Promotion policy enablement"
              className="policy-authoring-form"
              onSubmit={enablePromotionPolicy}
            >
              <label>
                <span className="metric-label">Enable Policy ID</span>
                <input
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
              </label>
              <label>
                <span className="metric-label">Approval ID</span>
                <input
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
              </label>
              <button
                className="command-button"
                disabled={policyEnableStatus === "saving"}
                type="submit"
              >
                <ShieldCheck size={15} />
                {policyEnableStatus === "saving" ? "Enabling" : "Enable policy"}
              </button>
            </form>
            {policyEnableStatus !== "idle" ? (
              <p className="row-detail">
                {policyEnableStatus === "api_enabled"
                  ? "API policy enabled"
                  : policyEnableStatus === "saving"
                    ? "Policy enable pending"
                    : "Policy enable rejected"}
              </p>
            ) : null}
            <div className="payload-grid">
              {selectedPromotionPolicies.map((policy) => (
                <div className="payload-row" key={policy.policy_id}>
                  <span>
                    <span className="metric-label">{policy.policy_id}</span>
                    <span className="row-detail">{policy.audit_event_type}</span>
                  </span>
                  <span className="mono">{policy.status}</span>
                </div>
              ))}
            </div>
            {selectedPromotionPolicies.map((policy) => (
              <div className="audit-detail-grid" key={`${policy.policy_id}-summary`}>
                <div>
                  <p className="metric-label">Authoring</p>
                  <p className="row-title">{policy.created_by}</p>
                  <p className="row-detail">{policy.required_authoring_scope}</p>
                </div>
                <div>
                  <p className="metric-label">Promotion Scope</p>
                  <p className="row-title">{policy.required_scopes.join(", ")}</p>
                  <p className="row-detail">{policy.enforcement_mode}</p>
                </div>
                <div>
                  <p className="metric-label">Manual Import</p>
                  <p className="row-title">{policy.required_manual_import_status}</p>
                  <p className="row-detail">{policy.required_workflow_signal_status}</p>
                </div>
                <div>
                  <p className="metric-label">Risk</p>
                  <p className="row-title">{policy.allowed_risk_levels.join(", ")}</p>
                  <p className="row-detail">{policy.allowed_ontology_types.join(", ")}</p>
                </div>
                <div>
                  <p className="metric-label">Review Window</p>
                  <p className="row-title">{policy.review_window_hours}h</p>
                  <p className="row-detail">{policy.permission_decision.reason}</p>
                </div>
                <div>
                  <p className="metric-label">Audit Event</p>
                  <p className="row-title">{policy.audit_event_type}</p>
                  <p className="row-detail">{policy.audit_event_id ?? "pending"}</p>
                </div>
                <div>
                  <p className="metric-label">Revision Lineage</p>
                  <p className="row-title">
                    {policy.revises_policy_id ?? policy.replaced_by_policy_id ?? "none"}
                  </p>
                  <p className="row-detail">{policy.revision_idempotency_key ?? "not replayed"}</p>
                </div>
                <div>
                  <p className="metric-label">Revision Evidence</p>
                  <p className="row-title">{policy.revision_workflow_signal_status ?? "none"}</p>
                  <p className="row-detail">
                    {policy.revision_approval_id ?? policy.revision_decision ?? "not required"}
                  </p>
                </div>
              </div>
            ))}
          </section>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Schema Mapping</p>
                <h3 className="subsection-title">{selectedConnector.preview_sample.file_name}</h3>
              </div>
              <FileText size={18} />
            </div>
            <div className="payload-grid">
              {manifest.schema_fields.map((field) => (
                <div className="payload-row" key={field.source_column}>
                  <span className="metric-label">{field.source_column}</span>
                  <span className="mono">{field.target_field}</span>
                </div>
              ))}
            </div>
          </section>

          {csvPreviewApplies ? (
            <section className="simulation-policy-band">
              <div>
                <p className="section-label">CSV Preview</p>
                <h3 className="subsection-title">{preview.audit_event_preview.event_type}</h3>
                <p className="row-detail">
                  {preview.audit_event_preview.result} / {preview.audit_event_preview.scope}
                </p>
              </div>
              <div className="payload-grid">
                {preview.proposed_entities.map((entity) => (
                  <div className="payload-row" key={entity.node_id}>
                    <span className="metric-label">{entity.node_id}</span>
                    <span className="mono">{entity.ontology_type}</span>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="stack">
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
              <p className="row-detail" key={`${note}-${index}`}>
                {note}
              </p>
              ))}
          </div>
        </section>
      </div>
    </div>
  );
}
