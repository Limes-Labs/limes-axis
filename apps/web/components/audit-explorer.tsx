"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Filter, RadioTower, RotateCcw, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { getApiBaseUrl } from "@/lib/api-status";
import {
  allAuditFilter,
  filterAuditEvents,
  findAuditEventById,
  formatAuditLabel,
  resolveAuditEventSelection,
  type AuditFilters,
  type AuditExportBundle,
  type ManufacturingAuditExplorer,
} from "@/lib/audit-demo";
import { buildConnectorSnapshotHref } from "@/lib/connectors-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";

type AuditSource = "loading" | "persisted" | "api" | "unavailable";

const defaultFilters: AuditFilters = {
  tenant: allAuditFilter,
  eventType: allAuditFilter,
  scope: allAuditFilter,
};

function sourceLabel(source: AuditSource): string {
  if (source === "persisted") {
    return "Persisted audit events";
  }

  if (source === "api") {
    return "API audit records";
  }

  return source === "loading" ? "Loading audit API" : "Audit API unavailable";
}

function formatAuditTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function AuditExplorer() {
  const [auditData, setAuditData] = useState<ManufacturingAuditExplorer | null>(null);
  const [auditExport, setAuditExport] = useState<AuditExportBundle | null>(null);
  const [source, setSource] = useState<AuditSource>("loading");
  const [filters, setFilters] = useState<AuditFilters>(defaultFilters);
  const [requestedEventId, setRequestedEventId] = useState<string | null>(() =>
    typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("event_id"),
  );
  const [selectedEventId, setSelectedEventId] = useState("");
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchAuditData(path: string): Promise<ManufacturingAuditExplorer> {
      const response = await fetch(`${apiBaseUrl}${path}`, {
        signal: controller.signal,
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Audit explorer request failed with ${response.status}`);
      }

      return (await response.json()) as ManufacturingAuditExplorer;
    }

    async function fetchAuditExport(): Promise<AuditExportBundle> {
      const params = new URLSearchParams({
        tenant_id: "tenant_demo_manufacturing",
        limit: "100",
        export_reason: "console-review",
      });
      const response = await fetch(`${apiBaseUrl}/demo/manufacturing/audit/export?${params}`, {
        signal: controller.signal,
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Audit export request failed with ${response.status}`);
      }

      return (await response.json()) as AuditExportBundle;
    }

    async function loadAuditExport() {
      try {
        const exportData = await fetchAuditExport();
        if (!controller.signal.aborted) {
          setAuditExport(exportData);
        }
      } catch {
        if (!controller.signal.aborted) {
          setAuditExport(null);
        }
      }
    }

    async function fetchAudit() {
      try {
        const persistedAuditData = await fetchAuditData(
          "/demo/manufacturing/audit/events?tenant_id=tenant_demo_manufacturing&limit=100",
        );
        await loadAuditExport();
        if (persistedAuditData.events.length > 0) {
          setAuditData(persistedAuditData);
          setSelectedEventId(persistedAuditData.events[0]?.audit_event_id ?? "");
          setSource("persisted");
          return;
        }

        const seedAuditData = await fetchAuditData("/demo/manufacturing/audit");
        setAuditData(seedAuditData);
        setSelectedEventId(seedAuditData.events[0]?.audit_event_id ?? "");
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setAuditData(null);
          setAuditExport(null);
          setSelectedEventId("");
          setSource("unavailable");
        }
      }
    }

    void fetchAudit();

    return () => controller.abort();
  }, [apiBaseUrl]);

  const filteredEvents = useMemo(
    () => (auditData ? filterAuditEvents(auditData, filters) : []),
    [auditData, filters],
  );
  const effectiveSelectedEventId = auditData
    ? resolveAuditEventSelection({
        explorer: auditData,
        filteredEvents,
        requestedEventId,
        selectedEventId,
      })
    : "";

  const selectedEvent = useMemo(
    () =>
      auditData && auditData.events.length > 0
        ? findAuditEventById(auditData, effectiveSelectedEventId)
        : null,
    [auditData, effectiveSelectedEventId],
  );
  const selectedEventConnectorSnapshotHref =
    selectedEvent?.event_type === "connector.evidence_invariants.snapshot_persisted" &&
    selectedEvent.payload_preview.snapshot_id
      ? buildConnectorSnapshotHref({
          snapshotId: selectedEvent.payload_preview.snapshot_id,
          connectorId: selectedEvent.payload_preview.connector_id ?? null,
        })
      : null;

  function updateFilter(filterName: keyof AuditFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [filterName]: value,
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  if (!auditData) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed audit records. Local fallback audit records are disabled."
        endpoint="/demo/manufacturing/audit/events"
        title={source === "loading" ? "Loading audit API" : "Audit API unavailable"}
      />
    );
  }

  if (!selectedEvent) {
    return (
      <ApiRequiredState
        detail="The audit API responded without ledger records for this tenant."
        endpoint="/demo/manufacturing/audit/events"
        title="Audit API returned no records"
      />
    );
  }

  return (
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Audit Ledger</p>
          <h2 className="panel-title">{auditData.plant_name}</h2>
          <p className="row-detail">
            {auditData.scenario} / {auditData.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Audit source and ledger status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(auditData.ledger_status)}`}>
            <ShieldCheck size={15} />
            {platformStatusLabel(auditData.ledger_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(auditData.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        {auditData.metrics.map((metric) => (
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

      <section className="panel audit-filter-panel">
        <div>
          <p className="section-label">Filters</p>
          <h2 className="panel-title">Audit explorer</h2>
        </div>
        <div className="audit-filters">
          <label>
            <span className="metric-label">Tenant</span>
            <select value={filters.tenant} onChange={(event) => updateFilter("tenant", event.target.value)}>
              <option value={allAuditFilter}>All tenants</option>
              {auditData.filter_options.tenants.map((tenant) => (
                <option key={tenant} value={tenant}>
                  {tenant}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Event</span>
            <select
              value={filters.eventType}
              onChange={(event) => updateFilter("eventType", event.target.value)}
            >
              <option value={allAuditFilter}>All events</option>
              {auditData.filter_options.event_types.map((eventType) => (
                <option key={eventType} value={eventType}>
                  {formatAuditLabel(eventType)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Scope</span>
            <select value={filters.scope} onChange={(event) => updateFilter("scope", event.target.value)}>
              <option value={allAuditFilter}>All scopes</option>
              {auditData.filter_options.scopes.map((scope) => (
                <option key={scope} value={scope}>
                  {scope}
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={resetFilters} title="Reset filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <div className="audit-layout">
        <section className="panel">
          <div className="audit-list-header">
            <div>
              <p className="section-label">Events</p>
              <h2 className="panel-title">{filteredEvents.length} visible</h2>
            </div>
            <span className="status-pill signal-ready">
              <Filter size={15} />
              {auditData.events.length} total
            </span>
          </div>
          <div className="audit-list">
            {filteredEvents.map((event) => {
              const isSelected = event.audit_event_id === selectedEvent.audit_event_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`audit-list-item${isSelected ? " active" : ""}`}
                  key={event.audit_event_id}
                  onClick={() => {
                    setRequestedEventId(null);
                    setSelectedEventId(event.audit_event_id);
                  }}
                  type="button"
                >
                  <span>
                    <span className="row-title mono">{event.event_type}</span>
                    <span className="row-detail">
                      {formatAuditTime(event.occurred_at)} / {event.actor_id}
                    </span>
                    <span className="row-detail">{event.scope}</span>
                  </span>
                  <span className={`status-pill ${platformStatusClass(event.severity)}`}>
                    {event.result}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel audit-detail">
          <div className="audit-detail-header">
            <div>
              <p className="section-label">{selectedEvent.category}</p>
              <h2 className="panel-title">{formatAuditLabel(selectedEvent.event_type)}</h2>
              <p className="row-detail">{selectedEvent.summary}</p>
            </div>
            <div className="status-stack">
              <span className={`status-pill ${platformStatusClass(selectedEvent.severity)}`}>
                {platformStatusLabel(selectedEvent.severity)}
              </span>
              <span className="status-pill status-checking">{selectedEvent.result}</span>
            </div>
          </div>

          <div className="audit-detail-grid">
            <div>
              <p className="metric-label">Audit Event</p>
              <p className="row-title mono">{selectedEvent.audit_event_id}</p>
              <p className="row-detail">{selectedEvent.event_type}</p>
            </div>
            <div>
              <p className="metric-label">Actor</p>
              <p className="row-title">{selectedEvent.actor_id}</p>
              <p className="row-detail">{selectedEvent.actor_type}</p>
            </div>
            <div>
              <p className="metric-label">Scope</p>
              <p className="row-title mono">{selectedEvent.scope}</p>
              <p className="row-detail">{selectedEvent.permission_scope}</p>
            </div>
            <div>
              <p className="metric-label">Source</p>
              <p className="row-title">{selectedEvent.source}</p>
              <p className="row-detail">{selectedEvent.domain}</p>
            </div>
            <div>
              <p className="metric-label">Occurred</p>
              <p className="row-title">{formatAuditTime(selectedEvent.occurred_at)}</p>
              <p className="row-detail">{selectedEvent.data_classification}</p>
            </div>
          </div>

          <div className="audit-columns">
            <section>
              <p className="section-label">Related</p>
              <div className="tag-list">
                {[
                  selectedEvent.related_workflow_id,
                  selectedEvent.related_approval_id,
                  selectedEvent.related_agent_id,
                ]
                  .filter(Boolean)
                  .map((item) => (
                    <span className="tag" key={item}>
                      {item}
                    </span>
                  ))}
              </div>
            </section>
            <section>
              <p className="section-label">Evidence</p>
              <div className="tag-list">
                {selectedEvent.evidence_refs.map((item) => (
                  <span className="tag" key={item}>
                    {item}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <section className="audit-payload">
            <div className="audit-payload-header">
              <div>
                <p className="section-label">Payload Preview</p>
                <h3 className="subsection-title">Redacted fields</h3>
              </div>
              {selectedEventConnectorSnapshotHref ? (
                <a className="row-detail" href={selectedEventConnectorSnapshotHref}>
                  Connector snapshot
                </a>
              ) : (
                <FileText size={18} />
              )}
            </div>
            <div className="payload-grid">
              {Object.entries(selectedEvent.payload_preview).map(([key, value]) => (
                <div className="payload-row" key={key}>
                  <span className="metric-label">{formatAuditLabel(key)}</span>
                  <span className="mono">{value}</span>
                </div>
              ))}
            </div>
          </section>
        </section>
      </div>

      <section className="panel">
        <p className="section-label">Retention Notes</p>
        <div className="stack">
          {auditData.retention_notes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>

      {auditExport ? (
        <section className="panel audit-detail">
          <div className="audit-detail-header">
            <div>
              <p className="section-label">Export Controls</p>
              <h2 className="panel-title">{auditExport.manifest.export_id}</h2>
              <p className="row-detail">
                {auditExport.export_reason} / {auditExport.manifest.redaction_policy}
              </p>
            </div>
            <span className="status-pill signal-ready">
              <FileText size={15} />
              {auditExport.format.toUpperCase()} export
            </span>
          </div>

          <div className="audit-detail-grid">
            <div>
              <p className="metric-label">Records</p>
              <p className="row-title">{auditExport.manifest.record_count}</p>
              <p className="row-detail">{auditExport.manifest.tenant_id}</p>
            </div>
            <div>
              <p className="metric-label">Retention</p>
              <p className="row-title">{auditExport.retention_policy.retention_days} days</p>
              <p className="row-detail">{auditExport.retention_policy.policy_id}</p>
            </div>
            <div>
              <p className="metric-label">Legal hold</p>
              <p className="row-title">
                {auditExport.retention_policy.legal_hold ? "On" : "Off"}
              </p>
              <p className="row-detail">{auditExport.retention_policy.disposal_action}</p>
            </div>
            <div>
              <p className="metric-label">Checksum</p>
              <p className="row-title mono">
                {auditExport.manifest.checksum_sha256.slice(0, 12)}
              </p>
              <p className="row-detail">{auditExport.manifest.format}</p>
            </div>
            <div>
              <p className="metric-label">Retention Enforced</p>
              <p className="row-title">
                {auditExport.manifest.retention_enforced ? "Yes" : "No"}
              </p>
              <p className="row-detail">
                {auditExport.manifest.excluded_record_count} excluded
              </p>
            </div>
            <div>
              <p className="metric-label">Hash Chain</p>
              <p className="row-title mono">
                {auditExport.manifest.integrity_chain_tip_sha256.slice(0, 12)}
              </p>
              <p className="row-detail">{auditExport.integrity_proof.algorithm}</p>
            </div>
            <div>
              <p className="metric-label">Ledger Signature</p>
              <p className="row-title">
                {auditExport.ledger_signature.verification_status}
              </p>
              <p className="row-detail">
                {auditExport.ledger_signature.key_id ?? auditExport.ledger_signature.signing_mode}
              </p>
            </div>
            <div>
              <p className="metric-label">Signature Proof</p>
              <p className="row-title mono">
                {(auditExport.ledger_signature.signature ?? "unsigned").slice(0, 12)}
              </p>
              <p className="row-detail">{auditExport.ledger_signature.algorithm}</p>
            </div>
          </div>

          <div className="stack">
            {auditExport.ledger_signature.notes.map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
            ))}
            {auditExport.retention_notes.map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
            ))}
          </div>
        </section>
      ) : (
        <ApiRequiredState
          detail="Axis did not receive an API-backed audit export manifest. Local export manifests are disabled."
          endpoint="/demo/manufacturing/audit/export"
          title="Audit export API unavailable"
        />
      )}
    </div>
  );
}
