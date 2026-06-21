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

import {
  approvalDecisionLabel,
  approvalRiskClass,
  defaultManufacturingApprovalInbox,
  findApprovalById,
  type ApprovalDecision,
  type ApprovalDecisionOption,
  type ManufacturingApprovalInbox,
} from "@/lib/approval-demo";
import { getApiBaseUrl } from "@/lib/api-status";
import { formatOverviewTimestamp, platformStatusClass } from "@/lib/platform-overview";

type ApprovalSource = "loading" | "api" | "fallback";

type LocalApprovalDecision = {
  decision: ApprovalDecision;
  label: string;
  decidedAt: string;
  auditResult: string;
};

function sourceLabel(source: ApprovalSource): string {
  if (source === "api") {
    return "Live approval seed";
  }

  return source === "loading" ? "Loading approval seed" : "Fallback approval seed";
}

function decisionAuditResult(decision: ApprovalDecision): string {
  if (decision === "approve") {
    return "approved_preview";
  }

  return decision === "reject" ? "rejected_preview" : "changes_requested_preview";
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
  const [inbox, setInbox] = useState<ManufacturingApprovalInbox>(
    defaultManufacturingApprovalInbox,
  );
  const [source, setSource] = useState<ApprovalSource>("loading");
  const [selectedApprovalId, setSelectedApprovalId] = useState(
    defaultManufacturingApprovalInbox.approvals[0].approval_id,
  );
  const [localDecisions, setLocalDecisions] = useState<Record<string, LocalApprovalDecision>>({});
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchApprovals() {
      try {
        const response = await fetch(`${apiBaseUrl}/demo/manufacturing/approvals`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Approval inbox request failed with ${response.status}`);
        }

        const nextInbox = (await response.json()) as ManufacturingApprovalInbox;
        setInbox(nextInbox);
        setSelectedApprovalId(nextInbox.approvals[0].approval_id);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setInbox(defaultManufacturingApprovalInbox);
          setSelectedApprovalId(defaultManufacturingApprovalInbox.approvals[0].approval_id);
          setSource("fallback");
        }
      }
    }

    void fetchApprovals();

    return () => controller.abort();
  }, [apiBaseUrl]);

  const selectedApproval = useMemo(
    () => findApprovalById(inbox, selectedApprovalId),
    [inbox, selectedApprovalId],
  );
  const selectedDecision = localDecisions[selectedApproval.approval_id];
  const localDecisionCount = countLocalDecisions(inbox, localDecisions);
  const pendingCount = inbox.approvals.length - localDecisionCount;
  const highRiskCount = inbox.approvals.filter((approval) => approval.risk_level === "high").length;

  function recordDecision(option: ApprovalDecisionOption) {
    setLocalDecisions((current) => ({
      ...current,
      [selectedApproval.approval_id]: {
        decision: option.decision,
        label: option.label,
        decidedAt: new Intl.DateTimeFormat("en", {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(new Date()),
        auditResult: decisionAuditResult(option.decision),
      },
    }));
  }

  return (
    <div className="stack">
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
          <p className="metric-detail">Local review states recorded in this browser session</p>
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
            </div>
            <div className="decision-toolbar">
              {selectedApproval.decision_options.map((option) => (
                <button
                  className="command-button decision-command"
                  key={option.decision}
                  onClick={() => recordDecision(option)}
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
