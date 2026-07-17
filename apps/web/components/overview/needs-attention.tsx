"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, CircleCheckBig, GitBranch, TriangleAlert } from "lucide-react";

import {
  ApprovalDecisionCard,
  useApprovalDecisionState,
} from "@/components/approvals/approval-decision-card";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  approvalDecisionLabel,
  approvalRiskClass,
  type ApprovalInboxItem,
  type ManufacturingApprovalInbox,
} from "@/lib/approval-demo";
import { cn } from "@/lib/cn";
import type { ManufacturingOverview, RiskSignal, WorkflowSummary } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { buildTenantScopedPath, DEMO_TENANT_ID } from "@/lib/tenant-scope";
import { parseManufacturingApprovalInbox } from "@/lib/runtime-contracts/approvals";
import { useAxisQuery } from "@/lib/use-axis-query";

import { normalizeLabel, PanelHeader, StatusDot, type OverviewQuery } from "./overview-shared";

/*
 * The needs-attention strip: everything currently waiting on a human, each
 * as one line with one action. Approvals reuse the exact decision card (and
 * its confirm dialog) from the approvals page inside a Sheet, so a decision
 * taken here follows the same governed persistence path.
 */

export const APPROVALS_ENDPOINT = "/demo/manufacturing/approvals";

const APPROVAL_LIMIT = 3;

function isBlockedWorkflow(workflow: WorkflowSummary): boolean {
  return workflow.blocker !== null || workflow.state.includes("waiting");
}

function pendingRiskSignals(overview: ManufacturingOverview): RiskSignal[] {
  return overview.risk_signals.filter((signal) => signal.severity !== "ready");
}

function AttentionRow({
  tone,
  title,
  detail,
  action,
}: {
  tone: React.ReactNode;
  title: string;
  detail: string;
  action: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-line px-4 py-3 dark:border-white/10">
      {tone}
      <div className="grid min-w-0 flex-1 gap-0.5">
        <p className="m-0 text-sm font-medium break-words text-ink">{title}</p>
        <p className="m-0 text-xs text-muted">{detail}</p>
      </div>
      {action}
    </div>
  );
}

function rowLinkClass(): string {
  return cn(
    "inline-flex items-center rounded-full border border-line px-3.5 py-1.5 text-xs font-medium",
    "text-ink transition-colors hover:border-signal/50 hover:text-signal dark:border-white/15",
  );
}

function ApprovalAttentionRow({ approval }: { approval: ApprovalInboxItem }) {
  const [open, setOpen] = useState(false);
  const { decisions, errors, setDecision, setError } = useApprovalDecisionState();
  const decision = decisions[approval.approval_id];

  return (
    <>
      <AttentionRow
        action={
          <span className="flex items-center gap-2">
            {decision ? (
              <span className="status-pill signal-ready">
                {approvalDecisionLabel(decision.decision)}
              </span>
            ) : (
              <span className={`status-pill ${approvalRiskClass(approval.risk_level)}`}>
                {approval.risk_level}
              </span>
            )}
            <button className={rowLinkClass()} onClick={() => setOpen(true)} type="button">
              {strings.overview.needsAttention.review}
            </button>
          </span>
        }
        detail={`${approval.domain} / due ${approval.due}`}
        title={approval.action}
        tone={<StatusDot status={approval.risk_level === "high" ? "action_required" : "watch"} />}
      />
      <Sheet onOpenChange={setOpen} open={open}>
        <SheetContent aria-describedby={undefined}>
          <div className="grid gap-1 pr-8">
            <Eyebrow>{approval.domain}</Eyebrow>
            <SheetTitle className="font-display m-0 text-xl text-ink">
              {approval.action}
            </SheetTitle>
            <SheetDescription className="m-0 text-sm text-muted">
              {approval.summary}
            </SheetDescription>
          </div>
          <ApprovalDecisionCard
            approval={approval}
            decision={decision}
            error={errors[approval.approval_id]}
            onDecisionChange={setDecision}
            onErrorChange={setError}
          />
          <Link
            className="inline-flex w-fit items-center text-sm font-medium text-signal hover:underline"
            href="/approvals"
          >
            Open the full approval inbox
          </Link>
        </SheetContent>
      </Sheet>
    </>
  );
}

function SourceUnavailableNote({ message }: { message: string }) {
  return (
    <p className="m-0 flex items-center gap-2 text-xs text-danger">
      <TriangleAlert aria-hidden="true" size={14} />
      {message}
    </p>
  );
}

export function NeedsAttention({
  overview,
  tenantId = DEMO_TENANT_ID,
}: {
  overview: OverviewQuery<ManufacturingOverview>;
  tenantId?: string;
}) {
  const approvalsQuery = useAxisQuery<ManufacturingApprovalInbox>(
    buildTenantScopedPath(APPROVALS_ENDPOINT, tenantId),
    { expectedTenantId: tenantId, parse: parseManufacturingApprovalInbox },
  );
  const copy = strings.overview.needsAttention;

  if (!overview.data && !approvalsQuery.data) {
    if (overview.source === "loading" || approvalsQuery.source === "loading") {
      return <LoadingPanel rows={3} />;
    }

    return (
      <ErrorPanel
        detail={copy.error.detail}
        endpoint={`${APPROVALS_ENDPOINT} + /demo/manufacturing/overview`}
        title={copy.error.title}
      />
    );
  }

  const approvals = approvalsQuery.data?.approvals.slice(0, APPROVAL_LIMIT) ?? [];
  const blockedWorkflows = overview.data?.workflows.filter(isBlockedWorkflow) ?? [];
  const riskSignals = overview.data ? pendingRiskSignals(overview.data) : [];
  const approvalsFailed = !approvalsQuery.data && approvalsQuery.source === "unavailable";
  const overviewFailed = !overview.data && overview.source === "unavailable";
  const itemCount = approvals.length + blockedWorkflows.length + riskSignals.length;

  if (itemCount === 0 && !approvalsFailed && !overviewFailed) {
    return (
      <EmptyPanel detail={copy.allClear.detail} icon={CircleCheckBig} title={copy.allClear.title} />
    );
  }

  return (
    <section aria-label={copy.eyebrow} className="grid gap-3">
      <PanelHeader eyebrow={copy.eyebrow} />
      {approvalsFailed ? <SourceUnavailableNote message={copy.approvalsUnavailable} /> : null}
      {overviewFailed ? <SourceUnavailableNote message={copy.overviewUnavailable} /> : null}
      <Card className="grid gap-2 p-4">
        {approvals.map((approval) => (
          <ApprovalAttentionRow approval={approval} key={approval.approval_id} />
        ))}
        {blockedWorkflows.map((workflow) => (
          <AttentionRow
            action={
              <Link className={rowLinkClass()} href="/workflows">
                {copy.openWorkflows}
              </Link>
            }
            detail={workflow.blocker ?? normalizeLabel(workflow.state)}
            key={workflow.workflow_id}
            title={workflow.name}
            tone={<GitBranch aria-hidden="true" className="shrink-0 text-warning" size={16} />}
          />
        ))}
        {riskSignals.map((signal) => (
          <AttentionRow
            action={
              <Link className={rowLinkClass()} href="/audit">
                {copy.openAudit}
              </Link>
            }
            detail={`${signal.domain} / ${normalizeLabel(signal.owner_role)}`}
            key={signal.title}
            title={signal.title}
            tone={
              <AlertTriangle
                aria-hidden="true"
                className={cn(
                  "shrink-0",
                  signal.severity === "action_required" ? "text-danger" : "text-warning",
                )}
                size={16}
              />
            }
          />
        ))}
      </Card>
    </section>
  );
}
