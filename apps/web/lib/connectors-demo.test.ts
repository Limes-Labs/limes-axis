import { describe, expect, it } from "vitest";

import {
  buildDefaultConnectorConfigurationRequest,
  buildDefaultCsvPreviewRequest,
  defaultConnectorConfigurationRegistry,
  defaultConnectorCredentialHandleRegistry,
  defaultConnectorManualImportRegistry,
  defaultConnectorOntologyProposalRegistry,
  defaultConnectorPromotionPolicyRegistry,
  defaultConnectorRunRegistry,
  defaultManufacturingConnectorRegistry,
  defaultManufacturingConnectorPreview,
  findConnectorById,
  formatConnectorLabel,
} from "./connectors-demo";

describe("manufacturing connector demo contract", () => {
  it("keeps a public-safe file CSV connector manifest available without the API", () => {
    expect(defaultManufacturingConnectorRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultManufacturingConnectorRegistry.connectors).toHaveLength(1);

    const connector = defaultManufacturingConnectorRegistry.connectors[0];
    expect(connector.manifest.connector_id).toBe("file_csv_manufacturing_assets");
    expect(connector.manifest.connector_type).toBe("file_csv");
    expect(connector.manifest.sync_modes).toEqual(["preview", "manual_import"]);
    expect(connector.manifest.credential_requirements.storage).toBe("none");
    expect(connector.manifest.schema_fields.map((field) => field.source_column)).toEqual([
      "asset_id",
      "asset_name",
      "domain",
      "station",
      "risk_level",
    ]);
    expect(JSON.stringify(defaultManufacturingConnectorRegistry)).not.toContain("@");
    expect(JSON.stringify(defaultManufacturingConnectorRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultManufacturingConnectorRegistry).toLowerCase()).not.toContain(
      "api_key",
    );
  });

  it("keeps a preview-only CSV mapping result", () => {
    expect(defaultManufacturingConnectorPreview.preview_status).toBe("ready");
    expect(defaultManufacturingConnectorPreview.sync_mode).toBe("preview_only");
    expect(defaultManufacturingConnectorPreview.record_count).toBe(2);
    expect(defaultManufacturingConnectorPreview.proposed_entities[0]).toMatchObject({
      node_id: "asset_line_2_packaging",
      ontology_type: "manufacturing_asset",
    });
    expect(defaultManufacturingConnectorPreview.audit_event_preview.event_type).toBe(
      "connector.preview.generated",
    );
    expect(JSON.stringify(defaultManufacturingConnectorPreview)).not.toContain("csv_content");
  });

  it("builds the demo preview request without credentials", () => {
    expect(buildDefaultCsvPreviewRequest()).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      file_name: "manufacturing-assets-demo.csv",
    });
    expect(buildDefaultCsvPreviewRequest().csv_content).toContain("asset_id,asset_name");
    expect(buildDefaultCsvPreviewRequest().csv_content.toLowerCase()).not.toContain("password");
  });

  it("keeps tenant-scoped connector configuration fallback public-safe", () => {
    expect(defaultConnectorConfigurationRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorConfigurationRegistry.configurations).toHaveLength(1);
    expect(defaultConnectorConfigurationRegistry.metrics[0]).toMatchObject({
      label: "Configured Connectors",
      value: "1",
    });

    const configuration = defaultConnectorConfigurationRegistry.configurations[0];
    expect(configuration.connector_id).toBe("file_csv_manufacturing_assets");
    expect(configuration.status).toBe("configured_preview_only");
    expect(configuration.sync_mode).toBe("preview");
    expect(configuration.runtime_boundary).toBe("axis-connector-sandbox");
    expect(configuration.credential_ref_ids).toEqual([]);
    expect(configuration.configuration_payload).toMatchObject({
      file_name_pattern: "*.csv",
      mapping_profile: "manufacturing_asset_v1",
    });
    expect(JSON.stringify(defaultConnectorConfigurationRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorConfigurationRegistry).toLowerCase()).not.toContain(
      "api_key",
    );
    expect(JSON.stringify(defaultConnectorConfigurationRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("builds the demo connector configuration request without raw credentials", () => {
    const request = buildDefaultConnectorConfigurationRequest();

    expect(request).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      display_name: "Manufacturing assets CSV intake",
      sync_mode: "preview",
      created_by: "plant-operations-owner-role",
      credential_ref_ids: [],
    });
    expect(request.configuration_payload).toMatchObject({
      file_name_pattern: "*.csv",
      mapping_profile: "manufacturing_asset_v1",
    });
    expect(JSON.stringify(request).toLowerCase()).not.toContain("password");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("api_key");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("credential_value");
  });

  it("keeps credential handle fallback metadata-only and rotation-aware", () => {
    expect(defaultConnectorCredentialHandleRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorCredentialHandleRegistry.handles).toHaveLength(1);
    expect(defaultConnectorCredentialHandleRegistry.metrics[0]).toMatchObject({
      label: "Credential Handles",
      value: "1",
    });

    const handle = defaultConnectorCredentialHandleRegistry.handles[0];
    expect(handle.handle_id).toBe("cred_file_csv_readonly");
    expect(handle.secret_provider).toBe("external_vault");
    expect(handle.secret_ref).toBe("vault://axis/demo/connectors/file-csv-readonly");
    expect(handle.rotation_status).toBe("healthy");
    expect(handle.rotation_count).toBe(1);
    expect(handle.last_rotation?.evidence_ref).toBe("change-window-2026-06-22");
    expect(JSON.stringify(defaultConnectorCredentialHandleRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorCredentialHandleRegistry).toLowerCase()).not.toContain(
      "api_key",
    );
    expect(JSON.stringify(defaultConnectorCredentialHandleRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("keeps connector run fallback audit-backed and redacted", () => {
    expect(defaultConnectorRunRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorRunRegistry.runs).toHaveLength(1);
    expect(defaultConnectorRunRegistry.metrics[0]).toMatchObject({
      label: "Connector Runs",
      value: "1",
    });

    const run = defaultConnectorRunRegistry.runs[0];
    expect(run.run_id).toBe("run_file_csv_assets_preview_20260622");
    expect(run.status).toBe("recorded_preview_only");
    expect(run.audit_event_type).toBe("connector.run.recorded");
    expect(run.credential_handle_ids).toEqual(["cred_file_csv_readonly"]);
    expect(JSON.stringify(defaultConnectorRunRegistry).toLowerCase()).not.toContain("csv_content");
    expect(JSON.stringify(defaultConnectorRunRegistry).toLowerCase()).not.toContain("password");
    expect(JSON.stringify(defaultConnectorRunRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("keeps connector ontology proposal fallback review-only and redacted", () => {
    expect(defaultConnectorOntologyProposalRegistry.tenant_id).toBe(
      "tenant_demo_manufacturing",
    );
    expect(defaultConnectorOntologyProposalRegistry.proposals).toHaveLength(2);
    expect(defaultConnectorOntologyProposalRegistry.metrics[0]).toMatchObject({
      label: "Ontology Proposals",
      value: "2",
    });
    expect(defaultConnectorOntologyProposalRegistry.metrics[1]).toMatchObject({
      label: "Pending Review",
      value: "1",
    });
    expect(defaultConnectorOntologyProposalRegistry.metrics[2]).toMatchObject({
      label: "Graph Mutations",
      value: "1",
    });

    const proposal = defaultConnectorOntologyProposalRegistry.proposals[0];
    expect(proposal.proposal_id).toBe("proposal_asset_line_2_packaging");
    expect(proposal.status).toBe("promoted_to_graph");
    expect(proposal.write_mode).toBe("proposal_only");
    expect(proposal.graph_mutation_status).toBe("type_db_mutation_applied");
    expect(proposal.audit_event_type).toBe("connector.ontology_promotion.applied");
    expect(proposal.promotion_id).toBe("promote_asset_line_2_packaging_20260622");
    expect(proposal.promoted_by).toBe("plant-operations-owner-role");
    expect(proposal.ontology_mutation?.status).toBe("type_db_mutation_applied");
    expect(proposal.ontology_mutation?.payload.manual_import_id).toBe(
      "import_assets_manual_20260622",
    );
    expect(JSON.stringify(defaultConnectorOntologyProposalRegistry).toLowerCase()).not.toContain(
      "csv_content",
    );
    expect(JSON.stringify(defaultConnectorOntologyProposalRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorOntologyProposalRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("keeps connector manual import request fallback approval-gated and workflow-signaled", () => {
    expect(defaultConnectorManualImportRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorManualImportRegistry.imports).toHaveLength(1);
    expect(defaultConnectorManualImportRegistry.metrics[0]).toMatchObject({
      label: "Manual Imports",
      value: "1",
    });
    expect(defaultConnectorManualImportRegistry.metrics[1]).toMatchObject({
      label: "Approval Required",
      value: "0",
    });
    expect(defaultConnectorManualImportRegistry.metrics[2]).toMatchObject({
      label: "Workflow Signals",
      value: "1",
    });
    expect(defaultConnectorManualImportRegistry.metrics[3]).toMatchObject({
      label: "Graph Mutations",
      value: "0",
    });

    const manualImport = defaultConnectorManualImportRegistry.imports[0];
    expect(manualImport.import_id).toBe("import_assets_manual_20260622");
    expect(manualImport.status).toBe("approval_approved");
    expect(manualImport.import_mode).toBe("manual_import_request");
    expect(manualImport.idempotency_key).toBe("manual-import-assets-20260622");
    expect(manualImport.approval_id).toBe("appr_connector_import_assets_20260622");
    expect(manualImport.workflow_id).toBe("wf_connector_manual_import_review");
    expect(manualImport.proposal_ids).toEqual(["proposal_asset_line_2_packaging"]);
    expect(manualImport.graph_mutation_status).toBe("not_applied");
    expect(manualImport.workflow_signal_status).toBe("manual_import_signal_requested");
    expect(manualImport.audit_event_type).toBe("connector.manual_import.decision_recorded");
    expect(manualImport.decision).toBe("approve");
    expect(manualImport.decision_actor_id).toBe("plant-operations-owner-role");
    expect(manualImport.workflow_signal?.signal_name).toBe("connector_manual_import_decided");
    expect(manualImport.workflow_signal?.payload.graph_mutation_status).toBe("not_applied");
    expect(JSON.stringify(defaultConnectorManualImportRegistry).toLowerCase()).not.toContain(
      "csv_content",
    );
    expect(JSON.stringify(defaultConnectorManualImportRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorManualImportRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("keeps connector promotion policy fallback scoped and audit-backed", () => {
    expect(defaultConnectorPromotionPolicyRegistry.tenant_id).toBe(
      "tenant_demo_manufacturing",
    );
    expect(defaultConnectorPromotionPolicyRegistry.policies).toHaveLength(1);
    expect(defaultConnectorPromotionPolicyRegistry.metrics[0]).toMatchObject({
      label: "Promotion Policies",
      value: "1",
    });
    expect(defaultConnectorPromotionPolicyRegistry.metrics[1]).toMatchObject({
      label: "Draft Policies",
      value: "1",
    });

    const policy = defaultConnectorPromotionPolicyRegistry.policies[0];
    expect(policy.policy_id).toBe("policy_connector_asset_promotion_v1");
    expect(policy.status).toBe("draft");
    expect(policy.enforcement_mode).toBe("advisory");
    expect(policy.created_by).toBe("platform-governance-owner-role");
    expect(policy.required_authoring_scope).toBe("connectors:promotion_policy:author");
    expect(policy.required_scopes).toEqual(["connectors:ontology:promote"]);
    expect(policy.required_manual_import_status).toBe("approval_approved");
    expect(policy.required_workflow_signal_status).toBe("manual_import_signal_requested");
    expect(policy.allowed_risk_levels).toEqual(["high", "medium"]);
    expect(policy.allowed_ontology_types).toEqual(["manufacturing_asset"]);
    expect(policy.audit_event_type).toBe("connector.promotion_policy.authored");
    expect(JSON.stringify(defaultConnectorPromotionPolicyRegistry).toLowerCase()).not.toContain(
      "csv_content",
    );
    expect(JSON.stringify(defaultConnectorPromotionPolicyRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorPromotionPolicyRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("finds connectors and formats connector labels", () => {
    expect(
      findConnectorById(defaultManufacturingConnectorRegistry, "file_csv_manufacturing_assets")
        .manifest.display_name,
    ).toBe("Manufacturing assets CSV");
    expect(
      findConnectorById(defaultManufacturingConnectorRegistry, "missing").manifest.connector_id,
    ).toBe("file_csv_manufacturing_assets");
    expect(formatConnectorLabel("file_csv")).toBe("File Csv");
  });
});
