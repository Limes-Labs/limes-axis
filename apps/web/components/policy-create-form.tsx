"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { FilePlus2, FlaskConical } from "lucide-react";

import { PolicyConditionFields } from "@/components/policy-condition-fields";
import { PolicyEvaluationPanel } from "@/components/policy-evaluation-panel";
import {
  buildPolicyConditionsPayload,
  buildPolicyCreatePayload,
  createPlatformPolicy,
  emptyPolicyDraft,
  platformPolicyAuthorScope,
  platformPolicyEffects,
  platformPolicyIdPattern,
  platformPolicyScopes,
  policyEffectLabel,
  policyScopeLabel,
  validatePolicyDraft,
  type PlatformPolicyRecord,
  type PlatformPolicyScope,
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
  | { phase: "failed"; message: string };

export function PolicyCreateForm({ tenantId }: { tenantId: string }) {
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const [draft, setDraft] = useState<PolicyDraftFormState>(emptyPolicyDraft);
  const [fieldErrors, setFieldErrors] = useState<PolicyDraftFieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({ phase: "idle" });

  function updateDraft(patch: Partial<PolicyDraftFormState>) {
    setDraft((current) => ({ ...current, ...patch }));
  }

  function updateConditions(conditions: PolicyConditionsFormState) {
    updateDraft({ conditions });
  }

  async function submitPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationErrors = validatePolicyDraft(draft);
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
      const result = await createPlatformPolicy(buildPolicyCreatePayload(tenantId, draft), {
        session,
      });

      if (result.kind === "created") {
        setDraft(emptyPolicyDraft());
        setFieldErrors({});
        setSubmission({ phase: "created", record: result.record });
        triggerRefresh();
        return;
      }

      if (result.kind === "conflict") {
        setFieldErrors({ policyId: result.message });
        setSubmission({ phase: "failed", message: result.message });
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

      setSubmission({
        phase: "failed",
        message:
          result.kind === "failed" ? result.message : "Policy authoring returned an unexpected result.",
      });
    } catch {
      setSubmission({ phase: "failed", message: "Policy authoring API is unavailable." });
    }
  }

  const draftConditions = buildPolicyConditionsPayload(draft.conditions);
  const hasDraftConditions = Object.keys(draftConditions).length > 0;

  return (
    <section className="panel">
      <div className="row">
        <div>
          <p className="section-label">Author Policy</p>
          <h2 className="panel-title">New policy</h2>
          <p className="row-detail">
            Creates revision 1 through POST /platform/policies. The API enforces the{" "}
            {platformPolicyAuthorScope} scope and records authoring audit evidence.
          </p>
        </div>
        <FilePlus2 size={18} />
      </div>

      <form
        aria-label="Platform policy authoring"
        className="policy-authoring-form"
        noValidate
        onSubmit={(event) => void submitPolicy(event)}
      >
        <label>
          <span className="metric-label">Policy ID</span>
          <input
            aria-label="New policy id"
            onChange={(event) => updateDraft({ policyId: event.target.value })}
            pattern={platformPolicyIdPattern}
            placeholder="deny_critical_actions"
            required
            type="text"
            value={draft.policyId}
          />
        </label>
        <label>
          <span className="metric-label">Policy Version</span>
          <input
            aria-label="New policy version"
            onChange={(event) => updateDraft({ policyVersion: event.target.value })}
            required
            type="text"
            value={draft.policyVersion}
          />
        </label>
        <label>
          <span className="metric-label">Scope</span>
          <select
            aria-label="New policy scope"
            onChange={(event) =>
              updateDraft({ scope: event.target.value as PlatformPolicyScope })
            }
            value={draft.scope}
          >
            {platformPolicyScopes.map((scope) => (
              <option key={scope} value={scope}>
                {policyScopeLabel(scope)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="metric-label">Effect</span>
          <select
            aria-label="New policy effect"
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
            aria-label="New policy display name"
            onChange={(event) => updateDraft({ displayName: event.target.value })}
            placeholder="Deny critical actions"
            required
            type="text"
            value={draft.displayName}
          />
        </label>
        <label className="field-wide">
          <span className="metric-label">Description</span>
          <input
            aria-label="New policy description"
            onChange={(event) => updateDraft({ description: event.target.value })}
            placeholder="What this policy gates and why"
            required
            type="text"
            value={draft.description}
          />
        </label>
        {fieldErrors.policyId ? (
          <p className="row-detail field-wide" role="alert">
            {fieldErrors.policyId}
          </p>
        ) : null}
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
          labelPrefix="New policy"
          onChange={updateConditions}
        />
        <label className="field-wide">
          <span className="metric-label">Notes (one per line)</span>
          <textarea
            aria-label="New policy notes"
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
          <FilePlus2 size={15} />
          {submission.phase === "saving" ? "Authoring" : "Author policy"}
        </button>
      </form>

      {submission.phase === "failed" ? (
        <p className="row-detail" role="alert">
          Policy authoring failed: {submission.message}
        </p>
      ) : null}
      {submission.phase === "created" ? (
        <p className="row-detail" role="status">
          Policy created as r{submission.record.revision_number} /{" "}
          {submission.record.policy_version}.{" "}
          <Link className="text-link" href={`/policies/${submission.record.policy_id}`}>
            Open {submission.record.policy_id}
          </Link>
        </p>
      ) : null}

      <div className="row">
        <div>
          <p className="section-label">Preview Evaluation</p>
          <h3 className="subsection-title">Advisory dry run for the drafted scope</h3>
          <p className="row-detail">
            Runs POST /platform/policies/evaluate against the policies already persisted for
            this tenant, plus a client-side check of whether the drafted conditions would match
            the sample context. Advisory only: the draft is not evaluated by the API until it
            is authored.
          </p>
        </div>
        <FlaskConical size={18} />
      </div>
      <PolicyEvaluationPanel
        draftConditions={hasDraftConditions ? draftConditions : null}
        formLabel="Draft policy preview evaluation"
        scope={draft.scope}
        scopeLocked
        tenantId={tenantId}
      />
    </section>
  );
}
