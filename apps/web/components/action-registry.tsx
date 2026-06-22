"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Filter, RadioTower, RotateCcw, Send, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { getApiBaseUrl } from "@/lib/api-status";
import { buildAxisAuthInit } from "@/lib/oidc-session";
import {
  actionRunWorkflowSignalLabel,
  allActionFilter,
  buildActionRunRequest,
  countApprovalGatedActions,
  filterActions,
  findActionById,
  formatActionLabel,
  formatSchemaFields,
  type ActionFilters,
  type ActionRegistryEntry,
  type ActionRunPersistenceResult,
  type ManufacturingActionRegistry,
} from "@/lib/action-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

type ActionSource = "loading" | "api" | "unavailable";
type ActionRunSource = "api";

type LocalActionRunResult = {
  source: ActionRunSource;
  status: string;
  actionRunId: string;
  idempotencyKey: string;
  detail: string;
  auditEventType?: string;
  permissionDetail?: string;
  workflowSignalDetail?: string;
};

const defaultFilters: ActionFilters = {
  domain: allActionFilter,
  riskLevel: allActionFilter,
  approvalMode: allActionFilter,
  status: allActionFilter,
};

function sourceLabel(source: ActionSource): string {
  if (source === "api") {
    return "API action registry";
  }

  return source === "loading" ? "Loading action API" : "Action API unavailable";
}

function riskClass(action: ActionRegistryEntry): string {
  if (action.definition.risk_level === "critical" || action.definition.risk_level === "high") {
    return "signal-action-required";
  }

  return action.definition.risk_level === "medium" ? "signal-watch" : "signal-ready";
}

function approvalClass(action: ActionRegistryEntry): string {
  return action.definition.approval_mode === "not_required" ? "signal-ready" : "signal-watch";
}

function PayloadRows({ payload }: { payload: Record<string, string> }) {
  return (
    <div className="payload-grid">
      {Object.entries(payload).map(([key, value]) => (
        <div className="payload-row" key={key}>
          <p className="metric-label">{formatActionLabel(key)}</p>
          <p className="row-detail">{value}</p>
        </div>
      ))}
    </div>
  );
}

export function ActionRegistry() {
  const [registry, setRegistry] = useState<ManufacturingActionRegistry | null>(null);
  const [source, setSource] = useState<ActionSource>("loading");
  const [filters, setFilters] = useState<ActionFilters>(defaultFilters);
  const [selectedActionId, setSelectedActionId] = useState("");
  const [actionRunResults, setActionRunResults] = useState<Record<string, LocalActionRunResult>>(
    {},
  );
  const [actionRunErrors, setActionRunErrors] = useState<Record<string, string>>({});
  const [submittingActionId, setSubmittingActionId] = useState<string | null>(null);
  const apiBaseUrl = getApiBaseUrl();
  const { session } = useOidcConsoleSession();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchActions() {
      try {
        const response = await fetch(
          `${apiBaseUrl}/demo/manufacturing/actions`,
          buildAxisAuthInit(
            {
              signal: controller.signal,
              cache: "no-store",
            },
            session,
          ),
        );

        if (!response.ok) {
          throw new Error(`Action registry request failed with ${response.status}`);
        }

        const nextRegistry = (await response.json()) as ManufacturingActionRegistry;
        setRegistry(nextRegistry);
        setSelectedActionId(nextRegistry.actions[0]?.definition.action_id ?? "");
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setRegistry(null);
          setSelectedActionId("");
          setSource("unavailable");
        }
      }
    }

    void fetchActions();

    return () => controller.abort();
  }, [apiBaseUrl, session]);

  const filteredActions = useMemo(
    () => (registry ? filterActions(registry, filters) : []),
    [registry, filters],
  );
  const effectiveSelectedActionId = filteredActions.some(
    (action) => action.definition.action_id === selectedActionId,
  )
    ? selectedActionId
    : (filteredActions[0]?.definition.action_id ?? registry?.actions[0]?.definition.action_id ?? "");

  const selectedAction = useMemo(
    () =>
      registry && registry.actions.length > 0
        ? findActionById(registry, effectiveSelectedActionId)
        : null,
    [registry, effectiveSelectedActionId],
  );
  const gatedActions = registry ? countApprovalGatedActions(registry) : 0;
  const selectedRunResult = selectedAction
    ? actionRunResults[selectedAction.definition.action_id]
    : undefined;
  const selectedRunError = selectedAction
    ? actionRunErrors[selectedAction.definition.action_id]
    : undefined;

  function updateFilter(filterName: keyof ActionFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [filterName]: value,
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  async function requestActionRun(action: ActionRegistryEntry) {
    if (!registry) {
      return;
    }

    const request = buildActionRunRequest(registry, action);
    setSubmittingActionId(action.definition.action_id);
    setActionRunErrors((current) => {
      const next = { ...current };
      delete next[action.definition.action_id];
      return next;
    });

    try {
      const response = await fetch(
        `${apiBaseUrl}/demo/manufacturing/actions/${action.definition.action_id}/runs`,
        buildAxisAuthInit(
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(request),
          },
          session,
        ),
      );

      if (!response.ok) {
        throw new Error(`Action run request failed with ${response.status}`);
      }

      const result = (await response.json()) as ActionRunPersistenceResult;
      setActionRunResults((current) => ({
        ...current,
        [action.definition.action_id]: {
          source: "api",
          status: result.status,
          actionRunId: result.action_run_id,
          idempotencyKey: result.idempotency_key,
          detail: result.idempotent_replay
            ? "Idempotent replay returned the existing action run."
            : "Persisted through the action run API.",
          auditEventType: result.audit_event_type ?? "no new audit event",
          permissionDetail: `Permission ${result.permission_decision.reason}.`,
          workflowSignalDetail: actionRunWorkflowSignalLabel(result),
        },
      }));
    } catch (error) {
      setActionRunErrors((current) => ({
        ...current,
        [action.definition.action_id]:
          error instanceof Error
            ? error.message
            : "Action run API persistence is unavailable.",
      }));
    } finally {
      setSubmittingActionId(null);
    }
  }

  if (!registry) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed action records. Local fallback action records are disabled."
        endpoint="/demo/manufacturing/actions"
        title={source === "loading" ? "Loading action API" : "Action API unavailable"}
      />
    );
  }

  if (!selectedAction) {
    return (
      <ApiRequiredState
        detail="The action API responded without registry records for this tenant."
        endpoint="/demo/manufacturing/actions"
        title="Action API returned no records"
      />
    );
  }

  return (
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Action Registry</p>
          <h2 className="panel-title">{registry.plant_name}</h2>
          <p className="row-detail">
            {registry.scenario} / schema {registry.schema_version}
          </p>
        </div>
        <div className="overview-meta" aria-label="Action source and registry status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
            <FileText size={15} />
            {platformStatusLabel(registry.registry_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(registry.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        {registry.metrics.map((metric) => (
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

      <section className="panel action-filter-panel">
        <div>
          <p className="section-label">Filters</p>
          <h2 className="panel-title">Action registry</h2>
        </div>
        <div className="action-filters">
          <label>
            <span className="metric-label">Domain</span>
            <select
              value={filters.domain}
              onChange={(event) => updateFilter("domain", event.target.value)}
            >
              <option value={allActionFilter}>All domains</option>
              {registry.filter_options.domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Risk</span>
            <select
              value={filters.riskLevel}
              onChange={(event) => updateFilter("riskLevel", event.target.value)}
            >
              <option value={allActionFilter}>All risks</option>
              {registry.filter_options.risk_levels.map((risk) => (
                <option key={risk} value={risk}>
                  {formatActionLabel(risk)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Approval</span>
            <select
              value={filters.approvalMode}
              onChange={(event) => updateFilter("approvalMode", event.target.value)}
            >
              <option value={allActionFilter}>All modes</option>
              {registry.filter_options.approval_modes.map((mode) => (
                <option key={mode} value={mode}>
                  {formatActionLabel(mode)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Status</span>
            <select
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value={allActionFilter}>All statuses</option>
              {registry.filter_options.statuses.map((status) => (
                <option key={status} value={status}>
                  {formatActionLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={resetFilters} title="Reset action filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <div className="action-layout">
        <section className="panel">
          <div className="action-list-header">
            <div>
              <p className="section-label">Actions</p>
              <h2 className="panel-title">{filteredActions.length} visible</h2>
            </div>
            <span className="status-pill signal-watch">
              <Filter size={15} />
              {gatedActions} gated
            </span>
          </div>
          <div className="action-list">
            {filteredActions.map((action) => {
              const isSelected =
                action.definition.action_id === selectedAction.definition.action_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`action-list-item${isSelected ? " active" : ""}`}
                  key={action.definition.action_id}
                  onClick={() => setSelectedActionId(action.definition.action_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{action.definition.display_name}</span>
                    <span className="row-detail">
                      {action.definition.domain} / {action.owner_role}
                    </span>
                    <span className="row-detail">{formatActionLabel(action.status)}</span>
                  </span>
                  <span className={`status-pill ${riskClass(action)}`}>
                    {formatActionLabel(action.definition.risk_level)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel action-detail">
          <div className="action-detail-header">
            <div>
              <p className="section-label">{selectedAction.definition.domain}</p>
              <h2 className="panel-title">{selectedAction.definition.display_name}</h2>
              <p className="row-detail">{selectedAction.description}</p>
            </div>
            <div className="status-stack">
              <span className={`status-pill ${riskClass(selectedAction)}`}>
                {formatActionLabel(selectedAction.definition.risk_level)}
              </span>
              <span className={`status-pill ${approvalClass(selectedAction)}`}>
                {formatActionLabel(selectedAction.definition.approval_mode)}
              </span>
            </div>
          </div>

          <div className="action-detail-grid">
            <div>
              <p className="metric-label">Action ID</p>
              <p className="row-title mono">{selectedAction.definition.action_id}</p>
              <p className="row-detail">{formatActionLabel(selectedAction.status)}</p>
            </div>
            <div>
              <p className="metric-label">Owner</p>
              <p className="row-title">{selectedAction.owner_role}</p>
              <p className="row-detail">Approval role {selectedAction.policy.approval_role}</p>
            </div>
            <div>
              <p className="metric-label">Runtime</p>
              <p className="row-title">{selectedAction.policy.runtime_adapter}</p>
              <p className="row-detail">{formatActionLabel(selectedAction.policy.execution_mode)}</p>
            </div>
            <div>
              <p className="metric-label">Autonomy</p>
              <p className="row-title">{selectedAction.policy.autonomy_ceiling}</p>
              <p className="row-detail">Ceiling for agent draft/execution</p>
            </div>
          </div>

          <div className="action-policy-band">
            <section>
              <p className="section-label">Policy</p>
              <div className="tag-list">
                <span className="tag">{selectedAction.policy.model_egress_policy}</span>
                <span className="tag">{selectedAction.policy.audit_event_type}</span>
                <span className="tag">
                  idempotency {selectedAction.policy.idempotency_required ? "required" : "optional"}
                </span>
                <span className="tag">
                  dry-run {selectedAction.policy.dry_run_supported ? "supported" : "blocked"}
                </span>
              </div>
            </section>
            <section>
              <p className="section-label">Required Permissions</p>
              <div className="tag-list">
                {selectedAction.definition.required_permissions.map((permission) => (
                  <span className="tag" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <div className="action-columns">
            <section>
              <p className="section-label">Connected Agents</p>
              <div className="tag-list">
                {selectedAction.connected_agents.map((agent) => (
                  <span className="tag" key={agent}>
                    {agent}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Workflow Bindings</p>
              <div className="tag-list">
                {selectedAction.workflow_bindings.map((workflow) => (
                  <span className="tag" key={workflow}>
                    {workflow}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Approval Refs</p>
              <div className="tag-list">
                {selectedAction.approval_refs.length > 0 ? (
                  selectedAction.approval_refs.map((approval) => (
                    <span className="tag" key={approval}>
                      {approval}
                    </span>
                  ))
                ) : (
                  <span className="tag">not_required</span>
                )}
              </div>
            </section>
          </div>

          <div className="action-columns">
            <section>
              <p className="section-label">Input Schema</p>
              <ul className="clean-list">
                {formatSchemaFields(selectedAction.definition.input_schema).map((field) => (
                  <li key={field}>{field}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Output Schema</p>
              <ul className="clean-list">
                {formatSchemaFields(selectedAction.definition.output_schema).map((field) => (
                  <li key={field}>{field}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Side Effects</p>
              <p className="row-detail">{selectedAction.side_effects}</p>
            </section>
          </div>

          <div className="action-columns">
            <section>
              <p className="section-label">Guardrails</p>
              <ul className="clean-list">
                {selectedAction.guardrails.map((guardrail) => (
                  <li key={guardrail}>{guardrail}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Validation Checks</p>
              <ul className="clean-list">
                {selectedAction.validation_checks.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Blocked Conditions</p>
              <ul className="clean-list">
                {selectedAction.blocked_conditions.map((condition) => (
                  <li key={condition}>{condition}</li>
                ))}
              </ul>
            </section>
          </div>

          <section className="action-schema-panel">
            <div className="action-schema-header">
              <div>
                <p className="section-label">Payload Preview</p>
                <h3 className="subsection-title">API dry-run payload</h3>
              </div>
              <div className="toolbar-actions">
                <button
                  className="command-button"
                  disabled={submittingActionId === selectedAction.definition.action_id}
                  onClick={() => void requestActionRun(selectedAction)}
                  type="button"
                >
                  <Send size={16} />
                  {submittingActionId === selectedAction.definition.action_id
                    ? "Requesting"
                    : "Request dry-run"}
                </button>
                <ShieldCheck size={18} />
              </div>
            </div>
            <div className="action-sample-grid">
              <section>
                <p className="section-label">Sample Input</p>
                <PayloadRows payload={selectedAction.sample_input} />
              </section>
              <section>
                <p className="section-label">Sample Output</p>
                <PayloadRows payload={selectedAction.sample_output} />
              </section>
            </div>
            {selectedRunResult ? (
              <section className="action-run-result" aria-label="Action run result">
                <div>
                  <p className="section-label">Persisted Action Run</p>
                  <h3 className="subsection-title">
                    {formatActionLabel(selectedRunResult.status)}
                  </h3>
                  <p className="row-detail">{selectedRunResult.detail}</p>
                </div>
                <div className="payload-grid">
                  <div className="payload-row">
                    <p className="metric-label">Run ID</p>
                    <p className="row-detail mono">{selectedRunResult.actionRunId}</p>
                  </div>
                  <div className="payload-row">
                    <p className="metric-label">Idempotency</p>
                    <p className="row-detail mono">{selectedRunResult.idempotencyKey}</p>
                  </div>
                  {selectedRunResult.auditEventType ? (
                    <div className="payload-row">
                      <p className="metric-label">Audit</p>
                      <p className="row-detail">{selectedRunResult.auditEventType}</p>
                    </div>
                  ) : null}
                  {selectedRunResult.permissionDetail ? (
                    <div className="payload-row">
                      <p className="metric-label">Permission</p>
                      <p className="row-detail">{selectedRunResult.permissionDetail}</p>
                    </div>
                  ) : null}
                  {selectedRunResult.workflowSignalDetail ? (
                    <div className="payload-row">
                      <p className="metric-label">Workflow Signal</p>
                      <p className="row-detail">{selectedRunResult.workflowSignalDetail}</p>
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}
            {selectedRunError ? (
              <section className="action-run-result" aria-label="Action run persistence error">
                <div>
                  <p className="section-label">Action Run Error</p>
                  <h3 className="subsection-title">Persistence unavailable</h3>
                  <p className="row-detail">{selectedRunError}</p>
                </div>
              </section>
            ) : null}
          </section>
        </section>
      </div>

      <section className="panel">
        <p className="section-label">Registry Notes</p>
        <div className="stack">
          {registry.registry_notes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
