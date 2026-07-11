"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { ChevronDown, ChevronRight, Inbox, RadioTower, ShieldAlert } from "lucide-react";

import {
  ApprovalDecisionCard,
  useApprovalDecisionState,
  type ApprovalDecisionRecord,
} from "@/components/approvals/approval-decision-card";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { DetailGrid, KeyValueRow } from "@/components/ui/detail-grid";
import { Eyebrow } from "@/components/ui/eyebrow";
import { InspectDrawer } from "@/components/ui/inspect-drawer";
import { MasterDetail } from "@/components/ui/master-detail";
import { MetricStrip, type Metric } from "@/components/ui/metric-strip";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  approvalDecisionLabel,
  approvalRiskClass,
  findApprovalById,
  type ApprovalInboxItem,
  type ManufacturingApprovalInbox,
} from "@/lib/approval-demo";
import { cn } from "@/lib/cn";
import { formatOverviewTimestamp, platformStatusClass } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";

const APPROVALS_ENDPOINT = "/demo/manufacturing/approvals";

type RailStageState = "done" | "current" | "pending";

type RailStage = {
  label: string;
  detail: string;
  state: RailStageState;
};

/**
 * Stage rail derived from the real approval record: submission metadata,
 * the attached policy controls, the human decision, and the persisted audit
 * evidence returned by the decision API.
 */
function buildDecisionRail(
  approval: ApprovalInboxItem,
  decision: ApprovalDecisionRecord | undefined,
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
  decision: ApprovalDecisionRecord | undefined;
}) {
  const stages = buildDecisionRail(approval, decision);
  const currentIndex = stages.findIndex((stage) => stage.state === "current");

  return (
    <div className="grid gap-1.5" aria-label="Decision stage rail">
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
                "m-0 font-mono text-[10px] tracking-[0.14em] uppercase",
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

function CollapsibleSection({
  label,
  defaultOpen = false,
  children,
}: {
  label: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const Chevron = open ? ChevronDown : ChevronRight;

  return (
    <Collapsible onOpenChange={setOpen} open={open}>
      <CollapsibleTrigger className="flex cursor-pointer items-center gap-1.5 bg-transparent p-0">
        <Chevron aria-hidden="true" className="text-muted" size={14} />
        <span className="eyebrow">{label}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2 pl-5.5">{children}</CollapsibleContent>
    </Collapsible>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function QueueList({
  inbox,
  selectedApproval,
  decisions,
  onSelect,
}: {
  inbox: ManufacturingApprovalInbox;
  selectedApproval: ApprovalInboxItem;
  decisions: Record<string, ApprovalDecisionRecord>;
  onSelect: (approvalId: string) => void;
}) {
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") {
      return;
    }
    event.preventDefault();

    const index = inbox.approvals.findIndex(
      (approval) => approval.approval_id === selectedApproval.approval_id,
    );
    const nextIndex =
      event.key === "ArrowDown"
        ? Math.min(index + 1, inbox.approvals.length - 1)
        : Math.max(index - 1, 0);
    const next = inbox.approvals[nextIndex];
    if (next && next.approval_id !== selectedApproval.approval_id) {
      onSelect(next.approval_id);
      itemRefs.current.get(next.approval_id)?.focus();
    }
  }

  return (
    <Card className="grid content-start gap-4">
      <div className="grid gap-1">
        <Eyebrow>{strings.approvals.queue.eyebrow}</Eyebrow>
        <h2 className="font-display m-0 text-xl text-ink">{strings.approvals.queue.title}</h2>
      </div>
      {/* Roving arrow-key selection across the queue buttons. */}
      <div className="grid gap-2" onKeyDown={handleKeyDown}>
        {inbox.approvals.map((approval) => {
          const decision = decisions[approval.approval_id];
          const isSelected = approval.approval_id === selectedApproval.approval_id;

          return (
            <button
              aria-pressed={isSelected}
              className={cn(
                "flex w-full cursor-pointer items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
                isSelected
                  ? "border-signal/60 bg-tint-100 dark:bg-signal/15"
                  : "border-line bg-transparent hover:border-signal/40 hover:bg-tint-50 dark:border-white/10 dark:hover:bg-white/5",
              )}
              key={approval.approval_id}
              onClick={() => onSelect(approval.approval_id)}
              ref={(element) => {
                if (element) {
                  itemRefs.current.set(approval.approval_id, element);
                } else {
                  itemRefs.current.delete(approval.approval_id);
                }
              }}
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
                  decision ? "signal-ready" : approvalRiskClass(approval.risk_level)
                }`}
              >
                {decision ? approvalDecisionLabel(decision.decision) : approval.risk_level}
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function ApprovalDetail({
  approval,
  decision,
  error,
  onDecisionChange,
  onErrorChange,
}: {
  approval: ApprovalInboxItem;
  decision: ApprovalDecisionRecord | undefined;
  error: string | undefined;
  onDecisionChange: (approvalId: string, record: ApprovalDecisionRecord | null) => void;
  onErrorChange: (approvalId: string, message: string | null) => void;
}) {
  return (
    <Card className="grid content-start gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid max-w-xl gap-1">
          <Eyebrow>{approval.domain}</Eyebrow>
          <h2 className="font-display m-0 text-xl text-ink">{approval.action}</h2>
          <p className="m-0 text-sm text-muted">{approval.summary}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={`status-pill ${approvalRiskClass(approval.risk_level)}`}>
            {approval.risk_level}
          </span>
          <span className="font-mono text-xs text-muted">Due {approval.due}</span>
        </div>
      </div>

      <ApprovalDecisionCard
        approval={approval}
        decision={decision}
        error={error}
        onDecisionChange={onDecisionChange}
        onErrorChange={onErrorChange}
      />

      <DecisionRail approval={approval} decision={decision} />

      <div aria-hidden="true" className="rule-dotted" />

      <CollapsibleSection defaultOpen label={strings.approvals.sections.evidence}>
        <div className="grid gap-3">
          <BulletList items={approval.evidence} />
          <div className="grid gap-1.5">
            <p className="m-0 text-xs font-medium text-muted">
              {strings.approvals.sections.dataAccessed}
            </p>
            <div className="flex flex-wrap gap-2">
              {approval.data_accessed.map((item) => (
                <span
                  className="inline-flex items-center rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted dark:border-white/15 dark:bg-transparent"
                  key={item}
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        </div>
      </CollapsibleSection>

      <CollapsibleSection label={strings.approvals.sections.risksAlternatives}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid content-start gap-1.5">
            <p className="m-0 text-xs font-medium text-muted">Risks</p>
            <BulletList items={approval.risks} />
          </div>
          <div className="grid content-start gap-1.5">
            <p className="m-0 text-xs font-medium text-muted">Alternatives</p>
            <BulletList items={approval.alternatives} />
          </div>
        </div>
      </CollapsibleSection>

      <div aria-hidden="true" className="rule-dotted" />

      <div className="grid gap-3">
        <DetailGrid>
          <KeyValueRow label="Workflow" mono>
            <span className="block max-w-full truncate" title={approval.workflow_id}>
              {approval.workflow_id}
            </span>
          </KeyValueRow>
          <KeyValueRow label="Requested by">{approval.requested_by}</KeyValueRow>
          <KeyValueRow label="Owner">{approval.owner_role}</KeyValueRow>
          <KeyValueRow label="Cost exposure">{approval.estimated_cost}</KeyValueRow>
        </DetailGrid>
        <InspectDrawer
          record={approval}
          title={approval.action}
          trigger={
            <button
              className="inline-flex w-fit cursor-pointer items-center font-mono text-xs text-muted transition-colors duration-200 hover:text-signal"
              type="button"
            >
              {strings.approvals.sections.inspect}
            </button>
          }
        />
      </div>
    </Card>
  );
}

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API approval queue";
  }

  return source === "loading" ? "Loading approval API" : "Approval API unavailable";
}

export function ApprovalInbox() {
  const { data: inbox, source } = useAxisQuery<ManufacturingApprovalInbox>(APPROVALS_ENDPOINT);
  const [selectedApprovalId, setSelectedApprovalId] = useState("");
  const { decisions, errors, setDecision, setError } = useApprovalDecisionState();

  if (!inbox) {
    if (source === "loading") {
      return (
        <div aria-label="Loading approval API" className="grid gap-4">
          <LoadingPanel layout="metrics" rows={3} />
          <MasterDetail
            detail={<LoadingPanel layout="detail" />}
            list={<LoadingPanel rows={4} />}
          />
        </div>
      );
    }

    return (
      <ErrorPanel
        detail={strings.approvals.error.detail}
        endpoint={APPROVALS_ENDPOINT}
        title={strings.approvals.error.title}
      />
    );
  }

  if (inbox.approvals.length === 0) {
    return (
      <EmptyPanel
        detail={strings.approvals.empty.detail}
        icon={Inbox}
        title={strings.approvals.empty.title}
      />
    );
  }

  // `findApprovalById` falls back to the first approval, so a stale or empty
  // selection always resolves to a real record.
  const selectedApproval = findApprovalById(inbox, selectedApprovalId);
  const decidedCount = inbox.approvals.filter(
    (approval) => decisions[approval.approval_id],
  ).length;
  const pendingCount = inbox.approvals.length - decidedCount;
  const highRiskCount = inbox.approvals.filter(
    (approval) => approval.risk_level === "high" && !decisions[approval.approval_id],
  ).length;

  const metrics: Metric[] = [
    {
      label: strings.approvals.metrics.pending,
      value: pendingCount,
      detail: strings.approvals.metrics.pendingDetail,
      tone: pendingCount > 0 ? "watch" : "ready",
    },
    {
      label: strings.approvals.metrics.highRisk,
      value: highRiskCount,
      detail: strings.approvals.metrics.highRiskDetail,
      tone: highRiskCount > 0 ? "action" : "ready",
    },
    {
      label: strings.approvals.metrics.decided,
      value: decidedCount,
      detail: strings.approvals.metrics.decidedDetail,
      tone: "ready",
    },
  ];

  return (
    <div className="grid gap-4">
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

      <MetricStrip metrics={metrics} />

      <MasterDetail
        detail={
          <ApprovalDetail
            approval={selectedApproval}
            decision={decisions[selectedApproval.approval_id]}
            error={errors[selectedApproval.approval_id]}
            onDecisionChange={setDecision}
            onErrorChange={setError}
          />
        }
        list={
          <QueueList
            decisions={decisions}
            inbox={inbox}
            onSelect={setSelectedApprovalId}
            selectedApproval={selectedApproval}
          />
        }
      />

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
