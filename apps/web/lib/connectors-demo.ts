import type { PlatformStatus } from "./platform-overview";

export type ConnectorCredentialRequirements = {
  storage: string;
  required_secret_refs: string[];
  notes: string[];
};

export type ConnectorSchemaField = {
  source_column: string;
  target_field: string;
  ontology_target: string;
  data_type: string;
  required: boolean;
  description: string;
};

export type ConnectorManifest = {
  connector_id: string;
  display_name: string;
  connector_type: string;
  version: string;
  source_type: string;
  sync_modes: string[];
  runtime_boundary: string;
  required_permissions: string[];
  credential_requirements: ConnectorCredentialRequirements;
  schema_fields: ConnectorSchemaField[];
  mapping_notes: string[];
};

export type ConnectorRuntimePolicy = {
  allowed_operations: string[];
  blocked_operations: string[];
  egress_policy: string;
  max_file_size_mb: number;
  row_limit: number;
  payload_policy: string;
};

export type ConnectorPreviewSample = {
  file_name: string;
  record_count: number;
  headers: string[];
  sample_rows: Record<string, string>[];
};

export type ConnectorRegistryItem = {
  manifest: ConnectorManifest;
  runtime_policy: ConnectorRuntimePolicy;
  preview_sample: ConnectorPreviewSample;
  connector_status: PlatformStatus;
};

export type ManufacturingConnectorRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  connectors: ConnectorRegistryItem[];
  connector_notes: string[];
};

export type ConnectorCsvPreviewRequest = {
  tenant_id: string;
  connector_id: string;
  file_name: string;
  csv_content: string;
};

export type ProposedOntologyEntity = {
  node_id: string;
  node_type: string;
  ontology_type: string;
  field_summary: Record<string, string>;
  evidence_refs: string[];
};

export type ConnectorAuditEventPreview = {
  event_type: string;
  scope: string;
  actor_id: string;
  result: string;
  evidence_refs: string[];
  payload_preview: Record<string, string>;
};

export type ConnectorCsvPreviewResult = {
  tenant_id: string;
  connector_id: string;
  file_name: string;
  preview_status: string;
  sync_mode: string;
  record_count: number;
  accepted_record_count: number;
  rejected_record_count: number;
  validation_issues: string[];
  proposed_entities: ProposedOntologyEntity[];
  audit_event_preview: ConnectorAuditEventPreview;
  preview_notes: string[];
};

export const defaultManufacturingConnectorRegistry: ManufacturingConnectorRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "watch",
  metrics: [
    {
      label: "Connector Manifests",
      value: "1",
      detail: "Public-safe connector manifest available for preview",
      status: "ready",
    },
    {
      label: "CSV Preview",
      value: "Ready",
      detail: "File connector can validate and map local CSV rows",
      status: "ready",
    },
    {
      label: "Live Sync",
      value: "Blocked",
      detail: "No live connector mutation is enabled in this foundation slice",
      status: "watch",
    },
  ],
  connectors: [
    {
      connector_status: "watch",
      manifest: {
        connector_id: "file_csv_manufacturing_assets",
        display_name: "Manufacturing assets CSV",
        connector_type: "file_csv",
        version: "2026-06-22",
        source_type: "file",
        sync_modes: ["preview", "manual_import"],
        runtime_boundary: "axis-connector-sandbox",
        required_permissions: ["connectors:read", "connectors:file_csv:preview"],
        credential_requirements: {
          storage: "none",
          required_secret_refs: [],
          notes: [
            "Local CSV preview does not require stored credentials.",
            "Future connector runs must reference credential handles, not raw values.",
          ],
        },
        schema_fields: [
          {
            source_column: "asset_id",
            target_field: "node_id",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Stable asset identifier used as the ontology node id.",
          },
          {
            source_column: "asset_name",
            target_field: "display_name",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Human-readable manufacturing asset name.",
          },
          {
            source_column: "domain",
            target_field: "domain",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Operational domain such as Operations, Quality or Maintenance.",
          },
          {
            source_column: "station",
            target_field: "source_system_ref",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Plant station, line or source-system reference.",
          },
          {
            source_column: "risk_level",
            target_field: "risk_level",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Public-safe risk posture used for demo governance checks.",
          },
        ],
        mapping_notes: [
          "CSV preview maps rows to ontology entity proposals only.",
          "Manual import remains disabled until connector permissions and audit writes mature.",
          "Raw file content is never returned in API responses.",
        ],
      },
      runtime_policy: {
        allowed_operations: ["schema_validate", "preview_mapping", "dry_run_diff"],
        blocked_operations: ["live_write", "credential_capture", "external_egress"],
        egress_policy: "no-external-egress",
        max_file_size_mb: 5,
        row_limit: 500,
        payload_policy: "redacted-preview-only",
      },
      preview_sample: {
        file_name: "manufacturing-assets-demo.csv",
        record_count: 3,
        headers: ["asset_id", "asset_name", "domain", "station", "risk_level"],
        sample_rows: [
          {
            asset_id: "asset_line_2_packaging",
            asset_name: "Line 2 Packaging",
            domain: "Operations",
            station: "Line 2",
            risk_level: "high",
          },
          {
            asset_id: "asset_press_4",
            asset_name: "Press 4",
            domain: "Maintenance",
            station: "Press 4",
            risk_level: "medium",
          },
        ],
      },
    },
  ],
  connector_notes: [
    "Connector manifests are public-safe and preview-only.",
    "The file/CSV connector maps rows to ontology proposals without writing data.",
    "Credential storage, scheduled sync and production connector runs remain future work.",
  ],
};

export const defaultManufacturingConnectorPreview: ConnectorCsvPreviewResult = {
  tenant_id: "tenant_demo_manufacturing",
  connector_id: "file_csv_manufacturing_assets",
  file_name: "manufacturing-assets-demo.csv",
  preview_status: "ready",
  sync_mode: "preview_only",
  record_count: 2,
  accepted_record_count: 2,
  rejected_record_count: 0,
  validation_issues: [],
  proposed_entities: [
    {
      node_id: "asset_line_2_packaging",
      node_type: "asset",
      ontology_type: "manufacturing_asset",
      field_summary: {
        asset_name: "Line 2 Packaging",
        domain: "Operations",
        station: "Line 2",
        risk_level: "high",
      },
      evidence_refs: ["manufacturing-assets-demo.csv", "asset_line_2_packaging"],
    },
    {
      node_id: "asset_press_4",
      node_type: "asset",
      ontology_type: "manufacturing_asset",
      field_summary: {
        asset_name: "Press 4",
        domain: "Maintenance",
        station: "Press 4",
        risk_level: "medium",
      },
      evidence_refs: ["manufacturing-assets-demo.csv", "asset_press_4"],
    },
  ],
  audit_event_preview: {
    event_type: "connector.preview.generated",
    scope: "file_csv_manufacturing_assets",
    actor_id: "connector-preview-service",
    result: "ready",
    evidence_refs: ["manufacturing-assets-demo.csv", "file_csv_manufacturing_assets"],
    payload_preview: {
      file_name: "manufacturing-assets-demo.csv",
      record_count: "2",
      accepted_record_count: "2",
      rejected_record_count: "0",
    },
  },
  preview_notes: [
    "CSV content is parsed only for preview and is not persisted.",
    "Mapped rows become ontology proposals, not live graph mutations.",
    "Connector sync, credential handles and audit writes remain future work.",
  ],
};

export function buildDefaultCsvPreviewRequest(): ConnectorCsvPreviewRequest {
  return {
    tenant_id: "tenant_demo_manufacturing",
    connector_id: "file_csv_manufacturing_assets",
    file_name: "manufacturing-assets-demo.csv",
    csv_content:
      "asset_id,asset_name,domain,station,risk_level\n" +
      "asset_line_2_packaging,Line 2 Packaging,Operations,Line 2,high\n" +
      "asset_press_4,Press 4,Maintenance,Press 4,medium\n",
  };
}

export function findConnectorById(
  registry: ManufacturingConnectorRegistry,
  connectorId: string,
): ConnectorRegistryItem {
  return (
    registry.connectors.find((connector) => connector.manifest.connector_id === connectorId) ??
    registry.connectors[0]
  );
}

export function formatConnectorLabel(value: string): string {
  return value
    .split(/[._:-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
