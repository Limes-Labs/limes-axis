"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  CircleX,
  FileClock,
  MessageSquare,
  RadioTower,
  ShieldAlert,
} from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { axisFetchJson } from "@/lib/axis-api";
import {
  approvalDecisionLabel,
  approvalDecisionActorId,
  approvalRiskClass,
  buildApprovalDecisionPayload,
  findApprovalById,
  type ApprovalDecision,
  type ApprovalDecisionOption,
  type ApprovalDecisionPersistenceResult,
  type ManufacturingApprovalInbox,
} from "@/lib/approval-demo";
import { formatOverviewTimestamp, platformStatusClass } from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

type LocalApprovalDecision = {
  decision: ApprovalDecision;
  label: string;
  decidedAt: string;
  auditResult: string;
  storage: "persisting" | "persisted";
  actorId: string;
  auditEventId?: string;
  workflowSignalStatus?: string;
  persistenceDetail?: string;
  permissionDetail?: string;
  workflowSignalDetail?: string;
};

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API approval queue";
  }

  return source === "loading" ? "Loading approval API" : "Approval API unavailable";
}

function persistedAuditResult(result: ApprovalDecisionPersistenceResult): string {
  return `${result.audit_event_type} / ${result.workflow_signal_status}`;
}

function DecisionIcon({ decision }: { decision: ApprovalDecision }) {
  if (decision === "approve") {
    return <CheckCircle2 size={17} />;
  }

  return decision === "reject" ? <CircleX size={17} /> : <MessageSquare size={17} />;
}

function countLocalDecisions(
  inbox: ManufacturingApprovalInbox,
  localDecisions: Record<string, LocalApprovalDecision>,
): number {
  const approvalIds = new Set(inbox.approvals.map((approval) => approval.approval_id));

  return Object.keys(localDecisions).filter((approvalId) => approvalIds.has(approvalId)).length;
}

export function ApprovalInbox() {
  const { data: inbox, source } = useAxisQuery<ManufacturingApprovalInbox>(
    "/demo/manufacturing/approvals",
  );
  const [selectedApprovalId, setSelectedApprovalId] = useState("");
  const [localDecisions, setLocalDecisions] = useState<Record<string, LocalApprovalDecision>>({});
  const [decisionErrors, setDecisionErrors] = useState<Record<string, string>>({});
  const { session } = useOidcConsoleSession();

  useEffect(() => {
    if (inbox?.approvals[0]) {
      setSelectedApprovalId(inbox.approvals[0].approval_id);
    }
  }, [inbox]);

  const selectedApproval = useMemo(
    () =>
      inbox && inbox.approvals.length > 0 ? findApprovalById(inbox, selectedApprovalId) : null,
    [inbox, selectedApprovalId],
  );
  const selectedDecision = selectedApproval
    ? localDecisions[selectedApproval.approval_id]
    : undefined;
  const selectedDecisionError = selectedApproval
    ? decisionErrors[selectedApproval.approval_id]
    : undefined;
  const localDecisionCount = inbox ? countLocalDecisions(inbox, localDecisions) : 0;
  const pendingCount = inbox ? inbox.approvals.length - localDecisionCount : 0;
  const highRiskCount = inbox
    ? inbox.approvals.filter((approval) => approval.risk_level === "high").length
    : 0;

  function updateDecisionState(
    approvalId: string,
    decision: LocalApprovalDecision,
  ) {
    setLocalDecisions((current) => ({
      ...current,
      [approvalId]: decision,
    }));
  }

  async function recordDecision(option: ApprovalDecisionOption) {
    if (!selectedApproval) {
      return;
    }

    const approvalId = selectedApproval.approval_id;
    const decidedAt = new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date());
    const actorId = approvalDecisionActorId(selectedApproval);

    updateDecisionState(approvalId, {
      decision: option.decision,
      label: option.label,
      decidedAt,
      auditResult: "persisting_decision",
      storage: "persisting",
      actorId,
      persistenceDetail: "Recording decision through the API.",
    });
    setDecisionErrors((current) => {
      const next = { ...current };
      delete next[approvalId];
      return next;
    });

    try {
      const result = await axisFetchJson<ApprovalDecisionPersistenceResult>(
        `/demo/manufacturing/approvals/${approvalId}/decision`,
        {
          session,
          method: "POST",
          body: buildApprovalDecisionPayload(selectedApproval, option.decision),
        },
      );
      updateDecisionState(approvalId, {
        decision: result.decision,
        label: option.label,
        decidedAt,
        auditResult: persistedAuditResult(result),
        storage: "persisted",
        actorId: result.actor_id,
        auditEventId: result.audit_event_id,
        workflowSignalStatus: result.workflow_signal_status,
        persistenceDetail: "Persisted through the approval decision API.",
        permissionDetail: `Permission ${result.permission_decision.reason}.`,
        workflowSignalDetail: `${result.workflow_signal.adapter} / ${result.workflow_signal.signal_name}`,
      });
    } catch (error) {
      setLocalDecisions((current) => {
        const next = { ...current };
        delete next[approvalId];
        return next;
      });
      setDecisionErrors((current) => ({
        ...current,
        [approvalId]:
          error instanceof Error
            ? error.message
            : "Approval decision API persistence is unavailable.",
      }));
    }
  }

  if (!inbox) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed approval records. Local fallback approval records are disabled."
        endpoint="/demo/manufacturing/approvals"
        title={source === "loading" ? "Loading approval API" : "Approval API unavailable"}
      />
    );
  }

  if (!selectedApproval) {
    return (
      <ApiRequiredState
        detail="The approval API responded without queue records for this tenant."
        endpoint="/demo/manufacturing/approvals"
        title="Approval API returned no records"
      />
    );
  }

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Approval Queue</p>
          <h2 className="panel-title">{inbox.plant_name}</h2>
          <p className="row-detail">
            {inbox.scenario} / {inbox.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Approval source and status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(inbox.queue_status)}`}>
            <ShieldAlert size={15} />
            {pendingCount} pending
          </span>
          <span className="mono">{formatOverviewTimestamp(inbox.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        <article className="metric-card compact-card">
          <p className="metric-label">Pending</p>
          <p className="metric-value">{pendingCount}</p>
          <p className="metric-detail">Human-gated decisions in the demo queue</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">High Risk</p>
          <p className="metric-value">{highRiskCount}</p>
          <p className="metric-detail">Actions that cannot execute without owner approval</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Decisions</p>
          <p className="metric-value">{localDecisionCount}</p>
          <p className="metric-detail">Persisted through the API when available</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Policy</p>
          <p className="metric-value">L2</p>
          <p className="metric-detail">Agent proposals remain under human approval</p>
        </article>
      </div>

      <div className="approval-layout">
        <section className="panel">
          <p className="section-label">Queue</p>
          <h2 className="panel-title">Approval inbox</h2>
          <div className="approval-list">
            {inbox.approvals.map((approval) => {
              const localDecision = localDecisions[approval.approval_id];
              const isSelected = approval.approval_id === selectedApproval.approval_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`approval-list-item${isSelected ? " active" : ""}`}
                  key={approval.approval_id}
                  onClick={() => setSelectedApprovalId(approval.approval_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{approval.action}</span>
                    <span className="row-detail">
                      {approval.domain} / {approval.owner_role}
                    </span>
                    <span className="row-detail">Due {approval.due}</span>
                  </span>
                  <span
                    className={`status-pill ${
                      localDecision ? "signal-ready" : approvalRiskClass(approval.risk_level)
                    }`}
                  >
                    {localDecision
                      ? approvalDecisionLabel(localDecision.decision)
                      : approval.risk_level}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel approval-detail">
          <div className="approval-detail-header">
            <div>
              <p className="section-label">{selectedApproval.domain}</p>
              <h2 className="panel-title">{selectedApproval.action}</h2>
              <p className="row-detail">{selectedApproval.summary}</p>
            </div>
            <div className="status-stack">
              <span className={`status-pill ${approvalRiskClass(selectedApproval.risk_level)}`}>
                {selectedApproval.risk_level}
              </span>
              <span className="status-pill status-checking">{selectedApproval.status}</span>
            </div>
          </div>

          <div className="approval-detail-grid">
            <div>
              <p className="metric-label">Workflow</p>
              <p className="row-title mono">{selectedApproval.workflow_id}</p>
            </div>
            <div>
              <p className="metric-label">Requested By</p>
              <p className="row-title">{selectedApproval.requested_by}</p>
            </div>
            <div>
              <p className="metric-label">Owner</p>
              <p className="row-title">{selectedApproval.owner_role}</p>
            </div>
            <div>
              <p className="metric-label">Cost Exposure</p>
              <p className="row-title">{selectedApproval.estimated_cost}</p>
            </div>
          </div>

          <div className="approval-columns">
            <section>
              <p className="section-label">Evidence</p>
              <ul className="clean-list">
                {selectedApproval.evidence.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Risks</p>
              <ul className="clean-list">
                {selectedApproval.risks.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Alternatives</p>
              <ul className="clean-list">
                {selectedApproval.alternatives.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          </div>

          <div className="approval-policy-band">
            <div>
              <p className="metric-label">Data Accessed</p>
              <div className="tag-list">
                {selectedApproval.data_accessed.map((item) => (
                  <span className="tag" key={item}>
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="metric-label">Controls</p>
              <p className="row-detail">
                {selectedApproval.required_permission} / {selectedApproval.model_policy}
              </p>
            </div>
          </div>

          <div className="decision-panel">
            <div>
              <p className="section-label">Decision</p>
              <h3 className="subsection-title">
                {selectedDecision
                  ? approvalDecisionLabel(selectedDecision.decision)
                  : "Pending review"}
              </h3>
              {selectedDecision ? (
                <p className="row-detail">
                  {selectedDecision.label} / {selectedDecision.decidedAt}
                </p>
              ) : null}
              {selectedDecision ? (
                <p className="row-detail">
                  {selectedDecision.storage === "persisted"
                    ? "Persisted decision"
                    : "Recording decision"}
                </p>
              ) : null}
              {selectedDecisionError ? (
                <p className="row-detail">Decision persistence error: {selectedDecisionError}</p>
              ) : null}
            </div>
            <div className="decision-toolbar">
              {selectedApproval.decision_options.map((option) => (
                <button
                  className="command-button decision-command"
                  disabled={selectedDecision?.storage === "persisting"}
                  key={option.decision}
                  onClick={() => void recordDecision(option)}
                  title={option.consequence}
                  type="button"
                >
                  <DecisionIcon decision={option.decision} />
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="audit-preview">
            <FileClock size={19} />
            <div>
              <p className="row-title mono">{selectedApproval.audit_event_preview.event}</p>
              <p className="row-detail">
                {selectedApproval.audit_event_preview.actor_role} /{" "}
                {selectedApproval.audit_event_preview.scope} /{" "}
                {selectedDecision?.auditResult ?? selectedApproval.audit_event_preview.result}
              </p>
              {selectedDecision?.auditEventId ? (
                <p className="row-detail mono">{selectedDecision.auditEventId}</p>
              ) : null}
              {selectedDecision?.persistenceDetail ? (
                <p className="row-detail">{selectedDecision.persistenceDetail}</p>
              ) : null}
              {selectedDecision?.permissionDetail ? (
                <p className="row-detail">{selectedDecision.permissionDetail}</p>
              ) : null}
              {selectedDecision?.workflowSignalDetail ? (
                <p className="row-detail">{selectedDecision.workflowSignalDetail}</p>
              ) : null}
              {selectedDecisionError ? (
                <p className="row-detail">{selectedDecisionError}</p>
              ) : null}
            </div>
          </div>
        </section>
      </div>

      <section className="panel">
        <p className="section-label">Policy Notes</p>
        <div className="stack">
          {inbox.policy_notes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
