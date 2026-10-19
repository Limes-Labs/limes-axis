"use client";

import { useState, type FormEvent } from "react";
import { GitBranchPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PolicyConditionFields } from "@/components/policy-condition-fields";
import { Field } from "@/components/ui/field";
import { InlineOperatorError } from "@/components/ui/inline-operator-error";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { toAxisOperatorError, type AxisOperatorError } from "@/lib/axis-api";
import { deriveGovernedActor } from "@/lib/governed-action";
import {
  buildPolicyRevisePayload,
  draftFromPolicyRecord,
  platformPolicyEffects,
  platformPolicyReviseScope,
  policyEffectLabel,
  policyScopeLabel,
  policyWriteOperatorError,
  revisePlatformPolicy,
  validatePolicyDraft,
  type PlatformPolicyRecord,
  type PolicyConditionsFormState,
  type PolicyDraftFieldErrors,
  type PolicyDraftFormState,
} from "@/lib/platform-policies";
import { safeRandomUuid } from "@/lib/ids";
import { opaqueStringUrlField, useConsoleUrlState } from "@/lib/console-url-state";
import { useStrings } from "@/providers/locale-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useIdentitySession } from "@/lib/use-identity-session";
import { useConsole } from "@/providers/console-provider";

type SubmissionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "created"; record: PlatformPolicyRecord }
  | { phase: "replayed"; record: PlatformPolicyRecord }
  | { phase: "conflict"; error: AxisOperatorError }
  | { phase: "failed"; error: AxisOperatorError };

export function PolicyReviseForm({
  tenantId,
  current,
}: {
  tenantId: string;
  current: PlatformPolicyRecord;
}) {
  const strings = useStrings();
  const { session } = useOidcConsoleSession();
  const identity = useIdentitySession();
  // The API rebinds updated_by to the verified OIDC principal and rejects
  // impersonation, so submissions carry the session-derived actor id.
  const { actorId, ssoBlocked } = deriveGovernedActor(
    identity.data ?? null,
    "platform-policy-author",
  );
  const { triggerRefresh } = useConsole();
  const [draft, setDraft] = useState<PolicyDraftFormState>(() =>
    draftFromPolicyRecord(current),
  );
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => safeRandomUuid());
  // Durable revision confirmation marker (?revised=) read by the revisions
  // tab banner; local state alone cannot survive the refresh this triggers.
  const [, setRevisedMarker] = useConsoleUrlState({
    revised: opaqueStringUrlField("revised"),
  });
  const [fieldErrors, setFieldErrors] = useState<PolicyDraftFieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({ phase: "idle" });

  function updateDraft(patch: Partial<PolicyDraftFormState>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...patch }));
  }

  function updateConditions(conditions: PolicyConditionsFormState) {
    updateDraft({ conditions });
  }

  async function submitRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (ssoBlocked) {
      return;
    }

    const validationErrors = validatePolicyDraft(draft, { requirePolicyId: false });
    setFieldErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      setSubmission({
        phase: "failed",
        error: toAxisOperatorError(
          null,
          "Fix the highlighted fields; nothing was sent to the API.",
        ),
      });
      return;
    }

    setSubmission({ phase: "saving" });

    try {
      const result = await revisePlatformPolicy(
        current.policy_id,
        buildPolicyRevisePayload(tenantId, current.policy_id, draft, idempotencyKey, actorId),
        { session },
      );

      if (result.kind === "created") {
        setFieldErrors({});
        setSubmission({ phase: "created", record: result.record });
        setRevisedMarker({ revised: String(result.record.revision_number) });
        // A fresh key for the next revision; the applied one is spent.
        setIdempotencyKey(safeRandomUuid());
        triggerRefresh();
        return;
      }

      if (result.kind === "replayed") {
        setSubmission({ phase: "replayed", record: result.record });
        setRevisedMarker({ revised: String(result.record.revision_number) });
        return;
      }

      if (result.kind === "conflict") {
        // The key was already used with a different payload; retrying with the
        // same key can never succeed, so rotate it and tell the operator.
        setIdempotencyKey(safeRandomUuid());
        setSubmission({
          phase: "conflict",
          error: policyWriteOperatorError(
            result,
            `${result.message} A fresh idempotency key was generated for the next attempt.`,
          ),
        });
        return;
      }

      if (result.kind === "invalid") {
        setFieldErrors(result.fieldErrors);
        setSubmission({ phase: "failed", error: policyWriteOperatorError(result) });
        return;
      }

      if (result.kind === "forbidden") {
        setSubmission({
          phase: "failed",
          error: policyWriteOperatorError(
            result,
            result.requiredPermission
              ? `${result.message} Required permission: ${result.requiredPermission}.`
              : result.message,
          ),
        });
        return;
      }

      setSubmission({ phase: "failed", error: policyWriteOperatorError(result) });
    } catch (caught) {
      setSubmission({
        phase: "failed",
        error: toAxisOperatorError(caught, "Policy revision API is unavailable."),
      });
    }
  }

  return (
    <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">{strings.ui.policyReviseForm.revisePolicy}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Append a revision to r{current.revision_number}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {strings.policyDetail.reviseAccess.summary} Pre-filled from the current revision;
            scope stays {policyScopeLabel(current.scope)}.{" "}
            {strings.policyDetail.reviseAccess.detail}
          </p>
          <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">
            POST /platform/policies/{current.policy_id}/revisions — {platformPolicyReviseScope}
          </p>
          <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">Idempotency key {idempotencyKey}</p>
        </div>
        <GitBranchPlus size={18} />
      </div>

      <form
        aria-label={strings.ui.policyReviseForm.platformPolicyRevision}
        className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
        noValidate
        onSubmit={(event) => void submitRevision(event)}
      >
        <Field label={strings.ui.common.policyVersion}>
          <Input
            aria-label={strings.ui.policyReviseForm.revisionPolicyVersion}
            onChange={(event) => updateDraft({ policyVersion: event.target.value })}
            required
            type="text"
            value={draft.policyVersion}
          />
        </Field>
        <Field label={strings.ui.common.effect}>
          <Select
            aria-label={strings.ui.policyReviseForm.revisionEffect}
            onChange={(event) =>
              updateDraft({ effect: event.target.value as PolicyDraftFormState["effect"] })
            }
            value={draft.effect}
          >
            {platformPolicyEffects.map((effect) => (
              <option key={effect} value={effect}>
                {policyEffectLabel(effect)}
              </option>
            ))}
          </Select>
        </Field>
        <Field className="col-span-full" label={strings.ui.common.displayName}>
          <Input
            aria-label={strings.ui.policyReviseForm.revisionDisplayName}
            onChange={(event) => updateDraft({ displayName: event.target.value })}
            required
            type="text"
            value={draft.displayName}
          />
        </Field>
        <Field className="col-span-full" label={strings.ui.common.description}>
          <Input
            aria-label={strings.ui.policyReviseForm.revisionDescription}
            onChange={(event) => updateDraft({ description: event.target.value })}
            required
            type="text"
            value={draft.description}
          />
        </Field>
        {fieldErrors.policyVersion ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
            {fieldErrors.policyVersion}
          </p>
        ) : null}
        {fieldErrors.displayName ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
            {fieldErrors.displayName}
          </p>
        ) : null}
        {fieldErrors.description ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
            {fieldErrors.description}
          </p>
        ) : null}
        <PolicyConditionFields
          conditions={draft.conditions}
          errors={fieldErrors}
          labelPrefix="Revision"
          onChange={updateConditions}
        />
        <Field className="col-span-full" label={strings.ui.common.notesOnePerLine}>
          <Textarea
            aria-label={strings.ui.policyReviseForm.revisionNotes}
            onChange={(event) => updateDraft({ notesText: event.target.value })}
            placeholder={strings.ui.common.optionalReviewerNotes}
            rows={2}
            value={draft.notesText}
          />
        </Field>
        {ssoBlocked ? (
          <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
            <GitBranchPlus aria-hidden="true" className="shrink-0 text-signal" size={15} />
            {strings.policyDetail.reviseAccess.ssoGate}
          </p>
        ) : (
          <Button
            disabled={submission.phase === "saving"}
            type="submit"
          >
            <GitBranchPlus size={15} />
            {submission.phase === "saving" ? strings.ui.policyReviseForm.appending : strings.ui.policyReviseForm.appendRevision}
          </Button>
        )}
      </form>

      {submission.phase === "created" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          Revision created: r{submission.record.revision_number} /{" "}
          {submission.record.policy_version} is now the active revision.
        </p>
      ) : null}
      {submission.phase === "replayed" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          Revision already applied: the API replayed r{submission.record.revision_number} /{" "}
          {submission.record.policy_version} for this idempotency key without writing a new
          revision.
        </p>
      ) : null}
      {submission.phase === "conflict" ? (
        <InlineOperatorError error={submission.error} prefix="Revision conflict" />
      ) : null}
      {submission.phase === "failed" ? (
        <InlineOperatorError error={submission.error} prefix="Policy revision failed" />
      ) : null}
    </section>
  );
}
