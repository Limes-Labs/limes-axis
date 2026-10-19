"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { FilePlus2, FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PolicyConditionFields } from "@/components/policy-condition-fields";
import { PolicyEvaluationPanel } from "@/components/policy-evaluation-panel";
import { Field } from "@/components/ui/field";
import { InlineOperatorError } from "@/components/ui/inline-operator-error";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { toAxisOperatorError, type AxisOperatorError } from "@/lib/axis-api";
import { deriveGovernedActor } from "@/lib/governed-action";
import {
  buildPolicyConditionsPayload,
  buildPolicyCreatePayload,
  createPlatformPolicy,
  emptyPolicyDraft,
  platformPolicyAuthorActorId,
  platformPolicyAuthorScope,
  platformPolicyEffects,
  platformPolicyIdPattern,
  platformPolicyScopes,
  policyEffectLabel,
  policyScopeLabel,
  policyWriteOperatorError,
  validatePolicyDraft,
  type PlatformPolicyRecord,
  type PlatformPolicyScope,
  type PolicyConditionsFormState,
  type PolicyDraftFieldErrors,
  type PolicyDraftFormState,
} from "@/lib/platform-policies";
import { opaqueStringUrlField, useConsoleUrlState } from "@/lib/console-url-state";
import { useStrings } from "@/providers/locale-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useIdentitySession } from "@/lib/use-identity-session";
import { useConsole } from "@/providers/console-provider";

type SubmissionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "created"; record: PlatformPolicyRecord }
  | { phase: "failed"; error: AxisOperatorError };

export function PolicyCreateForm({ tenantId }: { tenantId: string }) {
  const strings = useStrings();
  const { session } = useOidcConsoleSession();
  const identity = useIdentitySession();
  // The API rebinds created_by to the verified OIDC principal and rejects
  // impersonation, so submissions carry the session-derived actor id.
  const { actorId, ssoBlocked } = deriveGovernedActor(
    identity.data ?? null,
    platformPolicyAuthorActorId,
  );
  const { triggerRefresh } = useConsole();
  const [draft, setDraft] = useState<PolicyDraftFormState>(emptyPolicyDraft);
  const [fieldErrors, setFieldErrors] = useState<PolicyDraftFieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({ phase: "idle" });
  // The durable authoring confirmation lives in the registry banner (server
  // truth via ?authored=); this form also carries the marker write.
  const [, setAuthoredMarker] = useConsoleUrlState({
    authored: opaqueStringUrlField("authored"),
  });

  function updateDraft(patch: Partial<PolicyDraftFormState>) {
    setDraft((current) => ({ ...current, ...patch }));
  }

  function updateConditions(conditions: PolicyConditionsFormState) {
    updateDraft({ conditions });
  }

  async function submitPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (ssoBlocked) {
      return;
    }

    const validationErrors = validatePolicyDraft(draft);
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
      const result = await createPlatformPolicy(buildPolicyCreatePayload(tenantId, draft, actorId), {
        session,
      });

      if (result.kind === "created") {
        setDraft(emptyPolicyDraft());
        setFieldErrors({});
        setSubmission({ phase: "created", record: result.record });
        setAuthoredMarker({ authored: result.record.policy_id });
        triggerRefresh();
        return;
      }

      if (result.kind === "conflict") {
        setFieldErrors({ policyId: result.message });
        setSubmission({ phase: "failed", error: policyWriteOperatorError(result) });
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

      setSubmission({
        phase: "failed",
        error: policyWriteOperatorError(result),
      });
    } catch (caught) {
      setSubmission({
        phase: "failed",
        error: toAxisOperatorError(caught, "Policy authoring API is unavailable."),
      });
    }
  }

  const draftConditions = buildPolicyConditionsPayload(draft.conditions);
  const hasDraftConditions = Object.keys(draftConditions).length > 0;

  return (
    <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">{strings.ui.policyCreateForm.authorPolicy}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.policyCreateForm.newPolicy}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {strings.policyDetail.authorAccess.summary}{" "}
            {strings.policyDetail.authorAccess.detail}
          </p>
          <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">
            POST /platform/policies — {platformPolicyAuthorScope}
          </p>
        </div>
        <FilePlus2 size={18} />
      </div>

      <form
        aria-label={strings.ui.policyCreateForm.platformPolicyAuthoring}
        className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
        noValidate
        onSubmit={(event) => void submitPolicy(event)}
      >
        <Field label={strings.ui.policyCreateForm.policyId}>
          <Input
            aria-label={strings.ui.policyCreateForm.newPolicyId}
            onChange={(event) => updateDraft({ policyId: event.target.value })}
            pattern={platformPolicyIdPattern}
            placeholder="deny_critical_actions"
            required
            type="text"
            value={draft.policyId}
          />
        </Field>
        <Field label={strings.ui.common.policyVersion}>
          <Input
            aria-label={strings.ui.policyCreateForm.newPolicyVersion}
            onChange={(event) => updateDraft({ policyVersion: event.target.value })}
            required
            type="text"
            value={draft.policyVersion}
          />
        </Field>
        <Field label={strings.ui.common.scope}>
          <Select
            aria-label={strings.ui.policyCreateForm.newPolicyScope}
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
          </Select>
        </Field>
        <Field label={strings.ui.common.effect}>
          <Select
            aria-label={strings.ui.policyCreateForm.newPolicyEffect}
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
            aria-label={strings.ui.policyCreateForm.newPolicyDisplayName}
            onChange={(event) => updateDraft({ displayName: event.target.value })}
            placeholder={strings.ui.policyCreateForm.denyCriticalActions}
            required
            type="text"
            value={draft.displayName}
          />
        </Field>
        <Field className="col-span-full" label={strings.ui.common.description}>
          <Input
            aria-label={strings.ui.policyCreateForm.newPolicyDescription}
            onChange={(event) => updateDraft({ description: event.target.value })}
            placeholder={strings.ui.policyCreateForm.whatThisPolicyGatesAnd}
            required
            type="text"
            value={draft.description}
          />
        </Field>
        {fieldErrors.policyId ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
            {fieldErrors.policyId}
          </p>
        ) : null}
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
          labelPrefix="New policy"
          onChange={updateConditions}
        />
        <Field className="col-span-full" label={strings.ui.common.notesOnePerLine}>
          <Textarea
            aria-label={strings.ui.policyCreateForm.newPolicyNotes}
            onChange={(event) => updateDraft({ notesText: event.target.value })}
            placeholder={strings.ui.common.optionalReviewerNotes}
            rows={2}
            value={draft.notesText}
          />
        </Field>
        {ssoBlocked ? (
          <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
            <FilePlus2 aria-hidden="true" className="shrink-0 text-signal" size={15} />
            {strings.policyDetail.authorAccess.ssoGate}
          </p>
        ) : (
          <Button
            disabled={submission.phase === "saving"}
            type="submit"
          >
            <FilePlus2 size={15} />
            {submission.phase === "saving" ? strings.ui.policyCreateForm.authoring : strings.ui.policyCreateForm.authorPolicy2}
          </Button>
        )}
      </form>

      {submission.phase === "failed" ? (
        <InlineOperatorError error={submission.error} prefix="Policy authoring failed" />
      ) : null}
      {submission.phase === "created" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          Policy created as r{submission.record.revision_number} /{" "}
          {submission.record.policy_version}.{" "}
          <Link className="inline-flex min-h-6 items-center font-medium text-signal underline decoration-1 underline-offset-2" href={`/policies/${submission.record.policy_id}`}>
            Open {submission.record.policy_id}
          </Link>
        </p>
      ) : null}

      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">{strings.ui.policyCreateForm.previewEvaluation}</p>
          <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{strings.ui.policyCreateForm.advisoryDryRunForThe}</h3>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
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
