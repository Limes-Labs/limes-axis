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
import { Button, type ButtonVariant } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
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
  type ApprovalInboxItem,
  type ManufacturingApprovalInbox,
} from "@/lib/approval-demo";
import { cn } from "@/lib/cn";
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

type RailStageState = "done" | "current" | "pending";

type RailStage = {
  label: string;
  detail: string;
  state: RailStageState;
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

function decisionVariant(decision: ApprovalDecision): ButtonVariant {
  if (decision === "approve") {
    return "primary";
  }

  return decision === "reject" ? "destructive" : "secondary";
}

function countLocalDecisions(
  inbox: ManufacturingApprovalInbox,
  localDecisions: Record<string, LocalApprovalDecision>,
): number {
  const approvalIds = new Set(inbox.approvals.map((approval) => approval.approval_id));

  return Object.keys(localDecisions).filter((approvalId) => approvalIds.has(approvalId)).length;
}

/**
 * Stage rail derived from the real approval record: submission metadata,
 * the attached policy controls, the human decision, and the persisted audit
 * evidence returned by the decision API.
 */
function buildDecisionRail(
  approval: ApprovalInboxItem,
  decision: LocalApprovalDecision | undefined,
): RailStage[] {
  const decided = Boolean(decision);
  const recorded = decision?.storage === "persisted";

  return [
    {
      label: "Submitted",
      detail: `${approval.requested_by} / due ${approval.due}`,
      state: "done",
    },
    {
      label: "Policy evaluation",
      detail: `${approval.required_permission} / ${approval.model_policy}`,
      state: "done",
    },
    {
      label: "Approval",
      detail: decision
        ? approvalDecisionLabel(decision.decision)
        : `${approval.owner_role} decision pending`,
      state: decided ? "done" : "current",
    },
    {
      label: "Recorded",
      detail: recorded
        ? (decision?.auditEventId ?? approval.audit_event_preview.event)
        : decided
          ? "Persisting audit evidence"
          : approval.audit_event_preview.event,
      state: recorded ? "done" : decided ? "current" : "pending",
    },
  ];
}

function RailMarker({ state }: { state: RailStageState }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-2.5 shrink-0 rotate-45",
        state === "done" && "bg-signal",
        state === "current" && "border-2 border-signal bg-transparent",
        state === "pending" && "border border-mist bg-transparent dark:border-white/25",
      )}
      style={
        state === "current"
          ? { animation: "tick-pulse 1.6s ease-in-out infinite" }
          : undefined
      }
    />
  );
}

function DecisionRail({
  approval,
  decision,
}: {
  approval: ApprovalInboxItem;
  decision: LocalApprovalDecision | undefined;
}) {
  const stages = buildDecisionRail(approval, decision);
  const currentIndex = stages.findIndex((stage) => stage.state === "current");

  return (
    <div className="grid gap-2" aria-label="Decision stage rail">
      <div className="flex items-center gap-2">
        {stages.map((stage, index) => (
          <div
            className={cn("flex items-center gap-2", index > 0 && "min-w-0 flex-1")}
            key={stage.label}
          >
            {index > 0 ? (
              <div className="rule-dotted relative h-px min-w-6 flex-1 overflow-hidden">
                {index === currentIndex ? (
                  <span
                    className="absolute top-1/2 left-0 h-[3px] w-1/5 -translate-y-1/2 rounded-full bg-signal"
                    style={{ animation: "rail-pulse 1.8s linear infinite" }}
                  />
                ) : null}
              </div>
            ) : null}
            <RailMarker state={stage.state} />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-2">
        {stages.map((stage) => (
          <div className="grid min-w-0 gap-0.5" key={stage.label}>
            <p
              className={cn(
                "m-0 font-mono text-[10.5px] tracking-[0.14em] uppercase",
                stage.state === "pending" ? "text-muted" : "text-signal",
              )}
            >
              {stage.label}
            </p>
            <p className="m-0 truncate text-xs text-muted" title={stage.detail}>
              {stage.detail}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card className="grid content-start gap-2 p-5">
      <Eyebrow>{label}</Eyebrow>
      <p className="font-display m-0 text-3xl text-ink">{value}</p>
      <div aria-hidden="true" className="rule-dotted" />
      <p className="m-0 text-xs text-muted">{detail}</p>
    </Card>
  );
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
    if (source === "loading") {
      return (
        <div className="grid gap-5" aria-busy="true" aria-label="Loading approval API">
          <Skeleton className="h-28" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
          <div className="grid gap-4 xl:grid-cols-[2fr_3fr]">
            <Skeleton className="h-96" />
            <Skeleton className="h-96" />
          </div>
        </div>
      );
    }

    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed approval records. Local fallback approval records are disabled."
        endpoint="/demo/manufacturing/approvals"
        title="Approval API unavailable"
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
    <div className="grid gap-5">
      <div
        aria-label="Approval source and status"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm break-words text-muted">
          {inbox.plant_name} / {inbox.scenario} / {inbox.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(inbox.queue_status)}`}>
            <ShieldAlert size={15} />
            {pendingCount} pending
          </span>
          <span className="font-mono text-xs text-muted">
            {formatOverviewTimestamp(inbox.as_of)}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <ApprovalMetric
          detail="Human-gated decisions in the demo queue"
          label="Pending"
          value={String(pendingCount)}
        />
        <ApprovalMetric
          detail="Actions that cannot execute without owner approval"
          label="High Risk"
          value={String(highRiskCount)}
        />
        <ApprovalMetric
          detail="Persisted through the API when available"
          label="Decisions"
          value={String(localDecisionCount)}
        />
        <ApprovalMetric
          detail="Agent proposals remain under human approval"
          label="Policy"
          value="L2"
        />
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[2fr_3fr]">
        <Card className="grid content-start gap-4">
          <div className="grid gap-1">
            <Eyebrow>Queue</Eyebrow>
            <h2 className="font-display m-0 text-xl text-ink">Approval inbox</h2>
          </div>
          <div className="grid gap-2">
            {inbox.approvals.map((approval) => {
              const localDecision = localDecisions[approval.approval_id];
              const isSelected = approval.approval_id === selectedApproval.approval_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={cn(
                    "flex w-full items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
                    isSelected
                      ? "border-signal/60 bg-tint-100 dark:bg-signal/15"
                      : "border-line bg-transparent hover:border-signal/40 hover:bg-tint-50 dark:border-white/10 dark:hover:bg-white/5",
                  )}
                  key={approval.approval_id}
                  onClick={() => setSelectedApprovalId(approval.approval_id)}
                  type="button"
                >
                  <span className="grid min-w-0 gap-0.5">
                    <span className="text-sm font-medium text-ink">{approval.action}</span>
                    <span className="text-xs text-muted">
                      {approval.domain} / {approval.owner_role}
                    </span>
                    <span className="font-mono text-xs text-muted">Due {approval.due}</span>
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
        </Card>

        <Card className="grid content-start gap-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="grid max-w-xl gap-1">
              <Eyebrow>{selectedApproval.domain}</Eyebrow>
              <h2 className="font-display m-0 text-xl text-ink">{selectedApproval.action}</h2>
              <p className="m-0 text-sm text-muted">{selectedApproval.summary}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <span className={`status-pill ${approvalRiskClass(selectedApproval.risk_level)}`}>
                {selectedApproval.risk_level}
              </span>
              <span className="status-pill status-checking">{selectedApproval.status}</span>
            </div>
          </div>

          <DecisionRail approval={selectedApproval} decision={selectedDecision} />

          <div aria-hidden="true" className="rule-dotted" />

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div className="grid gap-1">
              <Eyebrow>Workflow</Eyebrow>
              <p className="m-0 font-mono text-sm break-words text-ink">
                {selectedApproval.workflow_id}
              </p>
            </div>
            <div className="grid gap-1">
              <Eyebrow>Requested By</Eyebrow>
              <p className="m-0 text-sm text-ink">{selectedApproval.requested_by}</p>
            </div>
            <div className="grid gap-1">
              <Eyebrow>Owner</Eyebrow>
              <p className="m-0 text-sm text-ink">{selectedApproval.owner_role}</p>
            </div>
            <div className="grid gap-1">
              <Eyebrow>Cost Exposure</Eyebrow>
              <p className="m-0 text-sm text-ink">{selectedApproval.estimated_cost}</p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <section className="grid content-start gap-2">
              <Eyebrow>Evidence</Eyebrow>
              <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
                {selectedApproval.evidence.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="grid content-start gap-2">
              <Eyebrow>Risks</Eyebrow>
              <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
                {selectedApproval.risks.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="grid content-start gap-2">
              <Eyebrow>Alternatives</Eyebrow>
              <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
                {selectedApproval.alternatives.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          </div>

          <div className="grid gap-4 rounded-2xl border border-line bg-tint-50 p-4 sm:grid-cols-2 dark:border-white/10 dark:bg-white/5">
            <div className="grid content-start gap-2">
              <Eyebrow>Data Accessed</Eyebrow>
              <div className="flex flex-wrap gap-2">
                {selectedApproval.data_accessed.map((item) => (
                  <span
                    className="inline-flex items-center rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted dark:border-white/15 dark:bg-transparent"
                    key={item}
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
            <div className="grid content-start gap-2">
              <Eyebrow>Controls</Eyebrow>
              <p className="m-0 font-mono text-xs break-words text-muted">
                {selectedApproval.required_permission} / {selectedApproval.model_policy}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="grid gap-1">
              <Eyebrow>Decision</Eyebrow>
              <h3 className="font-display m-0 text-lg text-ink">
                {selectedDecision
                  ? approvalDecisionLabel(selectedDecision.decision)
                  : "Pending review"}
              </h3>
              {selectedDecision ? (
                <p className="m-0 text-xs text-muted">
                  {selectedDecision.label} / {selectedDecision.decidedAt}
                </p>
              ) : null}
              {selectedDecision ? (
                <p className="m-0 text-xs text-muted">
                  {selectedDecision.storage === "persisted"
                    ? "Persisted decision"
                    : "Recording decision"}
                </p>
              ) : null}
              {selectedDecisionError ? (
                <p className="m-0 text-xs text-danger">
                  Decision persistence error: {selectedDecisionError}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedApproval.decision_options.map((option) => (
                <Button
                  className="px-4 py-2 text-sm"
                  disabled={selectedDecision?.storage === "persisting"}
                  key={option.decision}
                  onClick={() => void recordDecision(option)}
                  title={option.consequence}
                  variant={decisionVariant(option.decision)}
                >
                  <DecisionIcon decision={option.decision} />
                  {option.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-2xl border border-line p-4 dark:border-white/10">
            <FileClock className="mt-0.5 shrink-0 text-signal" size={18} />
            <div className="grid min-w-0 gap-1">
              <p className="m-0 font-mono text-sm break-words text-ink">
                {selectedApproval.audit_event_preview.event}
              </p>
              <p className="m-0 text-xs text-muted">
                {selectedApproval.audit_event_preview.actor_role} /{" "}
                {selectedApproval.audit_event_preview.scope} /{" "}
                {selectedDecision?.auditResult ?? selectedApproval.audit_event_preview.result}
              </p>
              {selectedDecision?.auditEventId ? (
                <p className="m-0 font-mono text-xs break-words text-muted">
                  {selectedDecision.auditEventId}
                </p>
              ) : null}
              {selectedDecision?.persistenceDetail ? (
                <p className="m-0 text-xs text-muted">{selectedDecision.persistenceDetail}</p>
              ) : null}
              {selectedDecision?.permissionDetail ? (
                <p className="m-0 text-xs text-muted">{selectedDecision.permissionDetail}</p>
              ) : null}
              {selectedDecision?.workflowSignalDetail ? (
                <p className="m-0 text-xs text-muted">{selectedDecision.workflowSignalDetail}</p>
              ) : null}
              {selectedDecisionError ? (
                <p className="m-0 text-xs text-danger">{selectedDecisionError}</p>
              ) : null}
            </div>
          </div>
        </Card>
      </div>

      <Card className="grid content-start gap-3">
        <Eyebrow>Policy Notes</Eyebrow>
        <div className="grid gap-2">
          {inbox.policy_notes.map((note) => (
            <p className="m-0 text-sm text-muted" key={note}>
              {note}
            </p>
          ))}
        </div>
      </Card>
    </div>
  );
}
