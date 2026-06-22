"use client";

import { useEffect, useMemo, useState } from "react";
import { Cable, Database, FileText, ShieldCheck } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api-status";
import {
  buildDefaultCsvPreviewRequest,
  defaultConnectorConfigurationRegistry,
  defaultManufacturingConnectorPreview,
  defaultManufacturingConnectorRegistry,
  findConnectorById,
  formatConnectorLabel,
  type ConnectorCsvPreviewResult,
  type ManufacturingConnectorConfigurationRegistry,
  type ManufacturingConnectorRegistry,
} from "@/lib/connectors-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";

type ConnectorSource = "loading" | "api" | "fallback";

function sourceLabel(source: ConnectorSource): string {
  if (source === "api") {
    return "API connector manifest";
  }

  return source === "loading" ? "Loading connectors" : "Fallback connector seed";
}

export function ConnectorConsole() {
  const [registry, setRegistry] = useState<ManufacturingConnectorRegistry>(
    defaultManufacturingConnectorRegistry,
  );
  const [preview, setPreview] = useState<ConnectorCsvPreviewResult>(
    defaultManufacturingConnectorPreview,
  );
  const [configurationRegistry, setConfigurationRegistry] =
    useState<ManufacturingConnectorConfigurationRegistry>(
      defaultConnectorConfigurationRegistry,
    );
  const [source, setSource] = useState<ConnectorSource>("loading");
  const [selectedConnectorId, setSelectedConnectorId] = useState(
    defaultManufacturingConnectorRegistry.connectors[0].manifest.connector_id,
  );
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
      const response = await fetch(`${apiBaseUrl}${path}`, {
        ...init,
        signal: controller.signal,
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

    async function loadConnectors() {
      try {
        const [registryData, previewData, configurationData] = await Promise.all([
          fetchJson<ManufacturingConnectorRegistry>("/demo/manufacturing/connectors"),
          fetchJson<ConnectorCsvPreviewResult>(
            "/demo/manufacturing/connectors/file-csv/preview",
            {
              body: JSON.stringify(buildDefaultCsvPreviewRequest()),
              method: "POST",
            },
          ),
          fetchJson<ManufacturingConnectorConfigurationRegistry>(
            "/demo/manufacturing/connectors/configurations",
          ),
        ]);
        if (registryData.connectors.length > 0) {
          setRegistry(registryData);
          setConfigurationRegistry(configurationData);
          setSelectedConnectorId(registryData.connectors[0].manifest.connector_id);
          setPreview(previewData);
          setSource("api");
          return;
        }

        setSource("fallback");
      } catch {
        if (!controller.signal.aborted) {
          setRegistry(defaultManufacturingConnectorRegistry);
          setConfigurationRegistry(defaultConnectorConfigurationRegistry);
          setPreview(defaultManufacturingConnectorPreview);
          setSelectedConnectorId(
            defaultManufacturingConnectorRegistry.connectors[0].manifest.connector_id,
          );
          setSource("fallback");
        }
      }
    }

    void loadConnectors();

    return () => controller.abort();
  }, [apiBaseUrl]);

  const selectedConnector = useMemo(
    () => findConnectorById(registry, selectedConnectorId),
    [registry, selectedConnectorId],
  );
  const selectedConfiguration = useMemo(
    () =>
      configurationRegistry.configurations.find(
        (configuration) => configuration.connector_id === selectedConnectorId,
      ) ?? configurationRegistry.configurations[0],
    [configurationRegistry.configurations, selectedConnectorId],
  );
  const manifest = selectedConnector.manifest;

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
          <span className="status-pill signal-ready">
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
        {registry.metrics.concat(configurationRegistry.metrics).map((metric) => (
          <article className="metric-card compact-card" key={metric.label}>
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
              <p className="row-title">{formatConnectorLabel(preview.sync_mode)}</p>
              <p className="row-detail">{manifest.sync_modes.join(", ")}</p>
            </div>
            <div>
              <p className="metric-label">Rows</p>
              <p className="row-title">{preview.record_count}</p>
              <p className="row-detail">
                {preview.accepted_record_count} accepted / {preview.rejected_record_count} rejected
              </p>
            </div>
            <div>
              <p className="metric-label">Credentials</p>
              <p className="row-title">{manifest.credential_requirements.storage}</p>
              <p className="row-detail">no stored credentials</p>
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

          <div className="stack">
            {registry.connector_notes
              .concat(configurationRegistry.configuration_notes)
              .concat(selectedConfiguration?.notes ?? [])
              .concat(preview.preview_notes)
              .map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
              ))}
          </div>
        </section>
      </div>
    </div>
  );
}
