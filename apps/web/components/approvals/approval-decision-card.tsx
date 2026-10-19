"use client";

import { useCallback, useId, useRef, useState, type RefObject } from "react";
import Link from "next/link";
import { CheckCircle2, CircleX, MessageSquare, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Eyebrow } from "@/components/ui/eyebrow";
import { ErrorPanel } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import {
  axisFetchParsedJson,
  toAxisOperatorError,
  type AxisOperatorError,
} from "@/lib/axis-api";
import {
  approvalDecisionActorId,
  approvalDecisionLabel,
  approvalRiskClass,
  buildApprovalDecisionPayload,
  decisionRequiresRationale,
  type ApprovalDecision,
  type ApprovalDecisionOption,
  type ApprovalDecisionPersistenceResult,
  type ApprovalInboxItem,
} from "@/lib/approval-demo";
import { cn } from "@/lib/cn";
import { deriveGovernedActor } from "@/lib/governed-action";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { useStrings } from "@/providers/locale-provider";
import { parseApprovalDecisionPersistenceResult } from "@/lib/runtime-contracts/approvals";
import { buildTenantScopedPath, DEMO_TENANT_ID, OPERATIONS_API_PREFIX } from "@/lib/tenant-scope";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useTenantVocabulary } from "@/providers/tenant-vocabulary-provider";
import { consoleDateTimeFormat } from "@/lib/format";

/*
 * The decision block of the approval flow: option buttons with their
 * consequence always visible, a confirm dialog that names the action on its
 * confirm button, restates the consequence, risk, cost and due date, and takes
 * a rationale (required for rejections and high-risk approvals), and the
 * persisted result with a deep link
 * to the created audit event. Exported standalone so the overview's
 * needs-attention strip can reuse the exact same confirm flow. Like every
 * governed write surface, submissions are blocked before they can fail
 * server-side when the deployment enforces SSO and no session exists.
 */

const DECISION_NOTE_MAX_LENGTH = 600;

/** Local decision lifecycle for one approval, keyed by the parent. */
export type ApprovalDecisionRecord = {
  decision: ApprovalDecision;
  label: string;
  decidedAt: string;
  storage: "persisting" | "persisted";
  actorId: string;
  auditEventId?: string;
  workflowSignalStatus?: string;
  permissionDetail?: string;
  workflowSignalDetail?: string;
};

export interface ApprovalDecisionCardProps {
  approval: ApprovalInboxItem;
  /** Current decision lifecycle for this approval; undefined = pending. */
  decision?: ApprovalDecisionRecord;
  /** Last persistence error for this approval. */
  error?: AxisOperatorError;
  /** Verified identity session from the host's `/identity/session` read. */
  identitySession: IdentitySessionReadModel | null;
  tenantId?: string;
  actor?: { actorId: string; scopes: string[] };
  onDecisionChange: (approvalId: string, record: ApprovalDecisionRecord | null) => void;
  onErrorChange?: (approvalId: string, error: AxisOperatorError | null) => void;
}

/**
 * Per-approval decision/error maps for hosts rendering one or more
 * `ApprovalDecisionCard`s (approval inbox, overview needs-attention strip).
 */
export function useApprovalDecisionState() {
  const [decisions, setDecisions] = useState<Record<string, ApprovalDecisionRecord>>({});
  const [errors, setErrors] = useState<Record<string, AxisOperatorError>>({});

  const setDecision = useCallback(
    (approvalId: string, record: ApprovalDecisionRecord | null) => {
      setDecisions((current) => {
        if (record === null) {
          const next = { ...current };
          delete next[approvalId];
          return next;
        }
        return { ...current, [approvalId]: record };
      });
    },
    [],
  );

  const setError = useCallback((approvalId: string, error: AxisOperatorError | null) => {
    setErrors((current) => {
      if (error === null) {
        const next = { ...current };
        delete next[approvalId];
        return next;
      }
      return { ...current, [approvalId]: error };
    });
  }, []);

  return { decisions, errors, setDecision, setError };
}

function DecisionIcon({ decision }: { decision: ApprovalDecision }) {
  if (decision === "approve") {
    return <CheckCircle2 aria-hidden="true" size={16} />;
  }

  return decision === "reject" ? (
    <CircleX aria-hidden="true" size={16} />
  ) : (
    <MessageSquare aria-hidden="true" size={16} />
  );
}

const optionToneClasses: Record<ApprovalDecision, string> = {
  approve:
    "border-signal/45 hover:border-signal hover:bg-tint-50 dark:hover:bg-signal/10 [&_.decision-option-label]:text-signal",
  reject:
    "border-danger/35 hover:border-danger hover:bg-danger/5 dark:hover:bg-danger/10 [&_.decision-option-label]:text-danger",
  request_changes:
    "border-line hover:border-signal/50 hover:bg-tint-50 dark:border-white/15 dark:hover:bg-white/5 [&_.decision-option-label]:text-ink",
};

function DecisionConfirmContent({
  approval,
  domainLabel,
  note,
  noteError,
  noteRef,
  onCancel,
  onConfirm,
  onNoteChange,
  option,
  returnFocusRef,
}: {
  approval: ApprovalInboxItem;
  domainLabel: string;
  note: string;
  noteError: boolean;
  noteRef: RefObject<HTMLTextAreaElement | null>;
  onCancel: () => void;
  onConfirm: () => void;
  onNoteChange: (value: string) => void;
  option: ApprovalDecisionOption;
  returnFocusRef: RefObject<HTMLElement | null>;
}) {
  const strings = useStrings();
  const copy = strings.approvals.decision;
  const rationaleRequired = decisionRequiresRationale(approval, option.decision);
  const hintId = useId();
  const errorId = useId();
  const describedBy = [rationaleRequired ? hintId : null, noteError ? errorId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <DialogContent returnFocusRef={returnFocusRef}>
      <DialogHeader>
        <DialogTitle>
          {copy.confirmTitle}: {option.label}
        </DialogTitle>
        <DialogDescription>{option.consequence}</DialogDescription>
      </DialogHeader>
      <div className="grid gap-2">
        <p className="m-0 text-sm text-muted">
          {approval.action} <span aria-hidden="true">·</span> {domainLabel}
        </p>
        <dl
          aria-label={copy.summaryLabel}
          className="m-0 grid gap-2 rounded-xl border border-line/70 p-3 text-sm sm:grid-cols-3 dark:border-white/10"
          data-decision-summary
        >
          <div className="grid min-w-0 gap-0.5">
            <dt className="text-xs font-medium text-muted">{copy.risk}</dt>
            <dd className="m-0">
              <span className={`status-pill ${approvalRiskClass(approval.risk_level)}`}>
                {copy.riskLevel(approval.risk_level)}
              </span>
            </dd>
          </div>
          <div className="grid min-w-0 gap-0.5">
            <dt className="text-xs font-medium text-muted">{copy.cost}</dt>
            <dd className="m-0 break-words text-ink">{approval.estimated_cost}</dd>
          </div>
          <div className="grid min-w-0 gap-0.5">
            <dt className="text-xs font-medium text-muted">{copy.due}</dt>
            <dd className="m-0 break-words text-ink">{approval.due}</dd>
          </div>
        </dl>
      </div>
      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-muted">
          {rationaleRequired ? copy.rationaleRequiredLabel : copy.rationaleLabel}
        </span>
        <textarea
          aria-describedby={describedBy || undefined}
          aria-invalid={noteError || undefined}
          aria-required={rationaleRequired || undefined}
          className={cn(
            "min-h-20 w-full resize-y rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-signal/60 dark:border-white/15 dark:bg-transparent",
            noteError && "border-danger focus:border-danger",
          )}
          maxLength={DECISION_NOTE_MAX_LENGTH}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder={copy.rationalePlaceholder}
          ref={noteRef}
          value={note}
        />
      </label>
      {rationaleRequired ? (
        <p className="m-0 text-xs text-muted" id={hintId}>
          {option.decision === "reject"
            ? copy.rationaleRequiredReject
            : copy.rationaleRequiredHighRisk}
        </p>
      ) : null}
      {noteError ? (
        <p className="m-0 text-xs font-medium text-danger" id={errorId} role="alert">
          {copy.rationaleMissing}
        </p>
      ) : null}
      <DialogFooter>
        <Button className="px-4 py-2 text-sm" variant="secondary" onClick={onCancel}>
          {copy.cancel}
        </Button>
        <Button
          className="px-4 py-2 text-sm"
          variant={option.decision === "reject" ? "destructive" : "primary"}
          onClick={onConfirm}
        >
          {copy.confirmAction(option.label, approval.action)}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}

export function ApprovalDecisionCard({
  approval,
  actor,
  decision,
  error,
  identitySession,
  onDecisionChange,
  onErrorChange,
  tenantId = DEMO_TENANT_ID,
}: ApprovalDecisionCardProps) {
  const strings = useStrings();
  const [pendingOption, setPendingOption] = useState<ApprovalDecisionOption | null>(null);
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState(false);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  // Focus returns to the option that opened the confirmation; once a decision
  // replaces the options, it falls back to the decision section itself.
  const sectionRef = useRef<HTMLElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const { session } = useOidcConsoleSession();
  const { push } = useToast();
  const { labelDomain } = useTenantVocabulary();
  const copy = strings.approvals.decision;
  // The API re-stamps the actor onto the verified OIDC principal, so the
  // derived id only labels the optimistic "persisting" state; when SSO is
  // enforced and no session exists, decisions are blocked before submit.
  const { actorId, ssoBlocked } = deriveGovernedActor(
    identitySession,
    approvalDecisionActorId(approval),
  );

  function openConfirm(option: ApprovalDecisionOption, opener: HTMLElement) {
    if (ssoBlocked) {
      return;
    }
    returnFocusRef.current = opener;
    setNote("");
    setNoteError(false);
    setPendingOption(option);
  }

  async function confirmDecision() {
    const option = pendingOption;
    if (!option || ssoBlocked) {
      return;
    }
    if (decisionRequiresRationale(approval, option.decision) && !note.trim()) {
      setNoteError(true);
      noteRef.current?.focus();
      return;
    }
    returnFocusRef.current = sectionRef.current;
    setPendingOption(null);

    const approvalId = approval.approval_id;
    const decidedAt = consoleDateTimeFormat({
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date());

    onDecisionChange(approvalId, {
      decision: option.decision,
      label: option.label,
      decidedAt,
      storage: "persisting",
      actorId,
    });
    onErrorChange?.(approvalId, null);

    try {
      const result = await axisFetchParsedJson<ApprovalDecisionPersistenceResult>(
        buildTenantScopedPath(
          `${OPERATIONS_API_PREFIX}/approvals/${approvalId}/decision`,
          tenantId,
        ),
        parseApprovalDecisionPersistenceResult,
        {
          session,
          method: "POST",
          body: buildApprovalDecisionPayload(approval, option.decision, note, actor),
        },
      );
      onDecisionChange(approvalId, {
        decision: result.decision,
        label: option.label,
        decidedAt,
        storage: "persisted",
        actorId: result.actor_id,
        auditEventId: result.audit_event_id,
        workflowSignalStatus: result.workflow_signal_status,
        permissionDetail: `Permission ${result.permission_decision.reason}.`,
        workflowSignalDetail: `${result.workflow_signal.adapter} / ${result.workflow_signal.signal_name}`,
      });
      push({
        title: copy.toastTitle,
        detail: `${option.label} — ${approval.action}`,
        tone: option.decision === "reject" ? "neutral" : "positive",
        ...(result.audit_event_id
          ? {
              href: `/audit?event_id=${encodeURIComponent(result.audit_event_id)}`,
              hrefLabel: copy.auditLink,
            }
          : {}),
      });
    } catch (caught) {
      onDecisionChange(approvalId, null);
      onErrorChange?.(
        approvalId,
        toAxisOperatorError(
          caught,
          "Approval decision API persistence is unavailable.",
        ),
      );
    } finally {
      setNote("");
    }
  }

  // The API reconciles the queue with persisted decision records; an item
  // whose terminal decision already exists must not offer options again.
  const alreadyDecided = approval.status === "decided";
  return (
    <section
      aria-label={strings.ui.common.decision}
      ref={sectionRef}
      tabIndex={-1}
      className="grid content-start gap-3 rounded-2xl border border-signal/25 bg-tint-50 p-4 dark:border-signal/30 dark:bg-signal/8"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Eyebrow>{copy.eyebrow}</Eyebrow>
        {decision ? (
          <span className="text-xs text-muted">
            {decision.storage === "persisted" ? copy.persisted : copy.persisting}
          </span>
        ) : null}
      </div>

      {decision ? (
        <div className="grid gap-1">
          <p className="font-display m-0 text-lg text-ink">
            {approvalDecisionLabel(decision.decision)}
          </p>
          <p className="m-0 text-xs text-muted">
            {decision.label} / {decision.decidedAt} / {decision.actorId}
          </p>
          {decision.permissionDetail ? (
            <p className="m-0 text-xs text-muted">{decision.permissionDetail}</p>
          ) : null}
          {decision.storage === "persisted" && decision.auditEventId ? (
            <Link
              className="mt-1 inline-flex w-fit items-center text-sm font-medium text-signal hover:underline"
              href={`/audit?event_id=${encodeURIComponent(decision.auditEventId)}`}
            >
              {copy.auditLink}
            </Link>
          ) : null}
        </div>
      ) : ssoBlocked ? (
        <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
          <ShieldCheck aria-hidden="true" className="shrink-0 text-signal" size={15} />
          {copy.ssoGate}
        </p>
      ) : alreadyDecided ? (
        <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
          <ShieldCheck aria-hidden="true" className="shrink-0 text-signal" size={15} />
          {copy.alreadyRecorded}
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {approval.decision_options.map((option) => (
            <button
              className={cn(
                "grid min-w-0 cursor-pointer content-start gap-1 rounded-xl border bg-surface px-3.5 py-3 text-left",
                "transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-55 dark:bg-transparent",
                optionToneClasses[option.decision],
              )}
              key={option.decision}
              onClick={(event) => openConfirm(option, event.currentTarget)}
              type="button"
            >
              <span className="decision-option-label flex items-center gap-1.5 text-sm font-medium">
                <DecisionIcon decision={option.decision} />
                {option.label}
              </span>
              <span className="text-xs leading-snug text-muted">{option.consequence}</span>
            </button>
          ))}
        </div>
      )}

      {error ? (
        <ErrorPanel
          detail={error.message}
          reference={error.requestId ?? undefined}
          title={strings.ui.approvalsApprovalDecisionCard.decisionPersistenceError}
        />
      ) : null}

      <Dialog
        open={pendingOption !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPendingOption(null);
          }
        }}
      >
        {pendingOption ? (
          <DecisionConfirmContent
            approval={approval}
            domainLabel={labelDomain(approval.domain)}
            note={note}
            noteError={noteError}
            noteRef={noteRef}
            onCancel={() => setPendingOption(null)}
            onConfirm={() => void confirmDecision()}
            onNoteChange={(value) => {
              setNote(value);
              if (value.trim()) {
                setNoteError(false);
              }
            }}
            option={pendingOption}
            returnFocusRef={returnFocusRef}
          />
        ) : null}
      </Dialog>
    </section>
  );
}
