"use client";

import { useState, type FormEvent } from "react";
import { GitBranchPlus } from "lucide-react";

import { PolicyConditionFields } from "@/components/policy-condition-fields";
import {
  buildPolicyRevisePayload,
  draftFromPolicyRecord,
  platformPolicyEffects,
  platformPolicyReviseScope,
  policyEffectLabel,
  policyScopeLabel,
  revisePlatformPolicy,
  validatePolicyDraft,
  type PlatformPolicyRecord,
  type PolicyConditionsFormState,
  type PolicyDraftFieldErrors,
  type PolicyDraftFormState,
} from "@/lib/platform-policies";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type SubmissionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "created"; record: PlatformPolicyRecord }
  | { phase: "replayed"; record: PlatformPolicyRecord }
  | { phase: "conflict"; message: string }
  | { phase: "failed"; message: string };

export function PolicyReviseForm({
  tenantId,
  current,
}: {
  tenantId: string;
  current: PlatformPolicyRecord;
}) {
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const [draft, setDraft] = useState<PolicyDraftFormState>(() =>
    draftFromPolicyRecord(current),
  );
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => crypto.randomUUID());
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

    const validationErrors = validatePolicyDraft(draft, { requirePolicyId: false });
    setFieldErrors(validationErrors);

    if (Object.keys(validationErrors).length > 0) {
      setSubmission({
        phase: "failed",
        message: "Fix the highlighted fields; nothing was sent to the API.",
      });
      return;
    }

    setSubmission({ phase: "saving" });

    try {
      const result = await revisePlatformPolicy(
        current.policy_id,
        buildPolicyRevisePayload(tenantId, current.policy_id, draft, idempotencyKey),
        { session },
      );

      if (result.kind === "created") {
        setFieldErrors({});
        setSubmission({ phase: "created", record: result.record });
        // A fresh key for the next revision; the applied one is spent.
        setIdempotencyKey(crypto.randomUUID());
        triggerRefresh();
        return;
      }

      if (result.kind === "replayed") {
        setSubmission({ phase: "replayed", record: result.record });
        return;
      }

      if (result.kind === "conflict") {
        // The key was already used with a different payload; retrying with the
        // same key can never succeed, so rotate it and tell the operator.
        setIdempotencyKey(crypto.randomUUID());
        setSubmission({
          phase: "conflict",
          message: `${result.message} A fresh idempotency key was generated for the next attempt.`,
        });
        return;
      }

      if (result.kind === "invalid") {
        setFieldErrors(result.fieldErrors);
        setSubmission({ phase: "failed", message: result.message });
        return;
      }

      if (result.kind === "forbidden") {
        setSubmission({
          phase: "failed",
          message: result.requiredPermission
            ? `${result.message} Required permission: ${result.requiredPermission}.`
            : result.message,
        });
        return;
      }

      setSubmission({ phase: "failed", message: result.message });
    } catch {
      setSubmission({ phase: "failed", message: "Policy revision API is unavailable." });
    }
  }

  return (
    <section className="panel">
      <div className="row">
        <div>
          <p className="section-label">Revise Policy</p>
          <h2 className="panel-title">Append a revision to r{current.revision_number}</h2>
          <p className="row-detail">
            Pre-filled from the current revision. Appends through POST
            /platform/policies/{current.policy_id}/revisions with an idempotency key; the API
            enforces the {platformPolicyReviseScope} scope. Scope stays{" "}
            {policyScopeLabel(current.scope)} — the policy scope is fixed at authoring time.
          </p>
          <p className="row-detail mono">Idempotency key {idempotencyKey}</p>
        </div>
        <GitBranchPlus size={18} />
      </div>

      <form
        aria-label="Platform policy revision"
        className="policy-authoring-form"
        noValidate
        onSubmit={(event) => void submitRevision(event)}
      >
        <label>
          <span className="metric-label">Policy Version</span>
          <input
            aria-label="Revision policy version"
            onChange={(event) => updateDraft({ policyVersion: event.target.value })}
            required
            type="text"
            value={draft.policyVersion}
          />
        </label>
        <label>
          <span className="metric-label">Effect</span>
          <select
            aria-label="Revision effect"
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
          </select>
        </label>
        <label className="field-wide">
          <span className="metric-label">Display Name</span>
          <input
            aria-label="Revision display name"
            onChange={(event) => updateDraft({ displayName: event.target.value })}
            required
            type="text"
            value={draft.displayName}
          />
        </label>
        <label className="field-wide">
          <span className="metric-label">Description</span>
          <input
            aria-label="Revision description"
            onChange={(event) => updateDraft({ description: event.target.value })}
            required
            type="text"
            value={draft.description}
          />
        </label>
        {fieldErrors.policyVersion ? (
          <p className="row-detail field-wide" role="alert">
            {fieldErrors.policyVersion}
          </p>
        ) : null}
        {fieldErrors.displayName ? (
          <p className="row-detail field-wide" role="alert">
            {fieldErrors.displayName}
          </p>
        ) : null}
        {fieldErrors.description ? (
          <p className="row-detail field-wide" role="alert">
            {fieldErrors.description}
          </p>
        ) : null}
        <PolicyConditionFields
          conditions={draft.conditions}
          errors={fieldErrors}
          labelPrefix="Revision"
          onChange={updateConditions}
        />
        <label className="field-wide">
          <span className="metric-label">Notes (one per line)</span>
          <textarea
            aria-label="Revision notes"
            onChange={(event) => updateDraft({ notesText: event.target.value })}
            placeholder="Optional reviewer notes"
            rows={2}
            value={draft.notesText}
          />
        </label>
        <button
          className="command-button"
          disabled={submission.phase === "saving"}
          type="submit"
        >
          <GitBranchPlus size={15} />
          {submission.phase === "saving" ? "Appending" : "Append revision"}
        </button>
      </form>

      {submission.phase === "created" ? (
        <p className="row-detail" role="status">
          Revision created: r{submission.record.revision_number} /{" "}
          {submission.record.policy_version} is now the active revision.
        </p>
      ) : null}
      {submission.phase === "replayed" ? (
        <p className="row-detail" role="status">
          Revision already applied: the API replayed r{submission.record.revision_number} /{" "}
          {submission.record.policy_version} for this idempotency key without writing a new
          revision.
        </p>
      ) : null}
      {submission.phase === "conflict" ? (
        <p className="row-detail" role="alert">
          Revision conflict: {submission.message}
        </p>
      ) : null}
      {submission.phase === "failed" ? (
        <p className="row-detail" role="alert">
          Policy revision failed: {submission.message}
        </p>
      ) : null}
    </section>
  );
}
