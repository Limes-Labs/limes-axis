"use client";

import { useState, type FormEvent } from "react";
import { FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { InlineOperatorError } from "@/components/ui/inline-operator-error";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { toAxisOperatorError, type AxisOperatorError } from "@/lib/axis-api";
import {
  buildPolicyEvaluationPayload,
  draftConditionsMatchContext,
  evaluatePlatformPolicy,
  parseRequestedAmount,
  platformPolicyAutonomyLevels,
  platformPolicyRiskLevels,
  platformPolicyScopes,
  policyEffectClass,
  policyEffectLabel,
  policyScopeLabel,
  type PlatformPolicyDecision,
  type PlatformPolicyRuleConditions,
  type PlatformPolicyScope,
} from "@/lib/platform-policies";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useStrings } from "@/providers/locale-provider";

type EvaluationFormFields = {
  scope: PlatformPolicyScope;
  actionDomain: string;
  riskLevel: string;
  autonomyLevel: string;
  requestedAmount: string;
};

type EvaluationState =
  | { phase: "idle" }
  | { phase: "evaluating" }
  | { phase: "decided"; decision: PlatformPolicyDecision; draftMatch: boolean | null }
  | { phase: "failed"; error: AxisOperatorError };

type PolicyEvaluationPanelProps = {
  tenantId: string;
  scope: PlatformPolicyScope;
  scopeLocked?: boolean;
  draftConditions?: PlatformPolicyRuleConditions | null;
  formLabel: string;
};

function DecisionResult({ decision }: { decision: PlatformPolicyDecision }) {
  const strings = useStrings();
  const matchedPolicies = decision.matched_policies ?? [];
  const evidenceEntries = Object.entries(decision.evidence ?? {});

  return (
    <div className="grid min-w-0 gap-2.5">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">{strings.ui.common.decision}</p>
          <p className="m-0 font-medium text-ink break-words">{policyEffectLabel(decision.effect, strings)}</p>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {decision.matched && decision.matched_policy_id
              ? strings.ui.policyEvaluationPanel.matchedPolicy(decision.matched_policy_id, decision.matched_revision_number, decision.matched_policy_version)
              : strings.policyDetail.precedence.noMatch}
          </p>
          <p
            className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words"
            title={decision.precedence_rule ?? undefined}
          >
            {strings.policyDetail.precedence.evaluated(decision.evaluated_policy_count)}
          </p>
        </div>
        <span className={`status-pill ${policyEffectClass(decision.effect)}`}>
          {policyEffectLabel(decision.effect, strings)}
        </span>
      </div>

      {matchedPolicies.length > 0 ? (
        <div>
          <p className="eyebrow m-0">{strings.ui.policyEvaluationPanel.matchedPolicies}</p>
          <div className="grid min-w-0 gap-2">
            {matchedPolicies.map((match) => (
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={`${match.policy_id}-${match.revision_number}`}>
                <span>
                  <span className="eyebrow m-0">{match.policy_id}</span>
                  <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                    {strings.ui.common.revisionVersion(match.revision_number, match.policy_version)}
                  </span>
                </span>
                <span className="font-mono text-[13px] break-words">{match.effect}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {evidenceEntries.length > 0 ? (
        <div>
          <p className="eyebrow m-0">{strings.ui.policyEvaluationPanel.evidencePayload}</p>
          <div className="grid min-w-0 gap-2">
            {evidenceEntries.map(([key, value]) => (
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5" key={key}>
                <span className="eyebrow m-0">{key}</span>
                <span className="font-mono text-[13px] break-words">{JSON.stringify(value)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function PolicyEvaluationPanel({
  tenantId,
  scope,
  scopeLocked = false,
  draftConditions = null,
  formLabel,
}: PolicyEvaluationPanelProps) {
  const strings = useStrings();
  const { session } = useOidcConsoleSession();
  const [form, setForm] = useState<EvaluationFormFields>({
    scope,
    actionDomain: "",
    riskLevel: "",
    autonomyLevel: "",
    requestedAmount: "",
  });
  const [evaluation, setEvaluation] = useState<EvaluationState>({ phase: "idle" });
  const [syncedScope, setSyncedScope] = useState(scope);

  if (syncedScope !== scope) {
    // Adjust derived form state during render when the caller-owned scope
    // changes (e.g. the create form's draft scope select).
    setSyncedScope(scope);
    setForm((current) => ({ ...current, scope }));
  }

  function updateField(field: keyof EvaluationFormFields, value: string) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function runEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const parsedAmount = parseRequestedAmount(form.requestedAmount);

    if (!parsedAmount.ok) {
      setEvaluation({
        phase: "failed",
        error: toAxisOperatorError(null, parsedAmount.message),
      });
      return;
    }

    setEvaluation({ phase: "evaluating" });

    const payload = buildPolicyEvaluationPayload(tenantId, {
      scope: form.scope,
      actionDomain: form.actionDomain,
      riskLevel: form.riskLevel,
      autonomyLevel: form.autonomyLevel,
      requestedAmount: parsedAmount.amount,
    });

    try {
      const decision = await evaluatePlatformPolicy(payload, { session });
      setEvaluation({
        phase: "decided",
        decision,
        draftMatch: draftConditions
          ? draftConditionsMatchContext(draftConditions, payload.context)
          : null,
      });
    } catch (caught) {
      setEvaluation({
        phase: "failed",
        error: toAxisOperatorError(caught, "Policy evaluation API is unavailable."),
      });
    }
  }

  return (
    <>
      <form
        aria-label={formLabel}
        className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
        onSubmit={(event) => void runEvaluation(event)}
      >
        <Field label={strings.ui.common.scope}>
          <Select
            aria-label={strings.ui.policyEvaluationPanel.evaluationScope}
            disabled={scopeLocked}
            onChange={(event) => updateField("scope", event.target.value)}
            value={form.scope}
          >
            {platformPolicyScopes.map((scopeOption) => (
              <option key={scopeOption} value={scopeOption}>
                {policyScopeLabel(scopeOption, strings)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={strings.ui.policyEvaluationPanel.actionDomain}>
          <Input
            aria-label={strings.ui.policyEvaluationPanel.actionDomain2}
            onChange={(event) => updateField("actionDomain", event.target.value)}
            placeholder={strings.ui.policyEvaluationPanel.operations}
            type="text"
            value={form.actionDomain}
          />
        </Field>
        <Field label={strings.ui.policyEvaluationPanel.riskLevel}>
          <Select
            aria-label={strings.ui.policyEvaluationPanel.riskLevel2}
            onChange={(event) => updateField("riskLevel", event.target.value)}
            value={form.riskLevel}
          >
            <option value="">{strings.ui.policyEvaluationPanel.notSet}</option>
            {platformPolicyRiskLevels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={strings.ui.policyEvaluationPanel.autonomyLevel}>
          <Select
            aria-label={strings.ui.policyEvaluationPanel.autonomyLevel2}
            onChange={(event) => updateField("autonomyLevel", event.target.value)}
            value={form.autonomyLevel}
          >
            <option value="">{strings.ui.policyEvaluationPanel.notSet}</option>
            {platformPolicyAutonomyLevels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={strings.ui.policyEvaluationPanel.requestedAmount}>
          <Input
            aria-label={strings.ui.policyEvaluationPanel.requestedAmount2}
            min="0"
            onChange={(event) => updateField("requestedAmount", event.target.value)}
            placeholder={strings.ui.common.optional}
            step="any"
            type="number"
            value={form.requestedAmount}
          />
        </Field>
        <Button
          disabled={evaluation.phase === "evaluating"}
          type="submit"
        >
          <FlaskConical size={15} />
          {evaluation.phase === "evaluating" ? strings.ui.policyEvaluationPanel.evaluating : strings.ui.policyEvaluationPanel.runDryRunEvaluation}
        </Button>
      </form>

      {evaluation.phase === "failed" ? (
        <InlineOperatorError error={evaluation.error} prefix={strings.ui.policyEvaluationPanel.dryRunEvaluationFailed} />
      ) : null}
      {evaluation.phase === "decided" ? (
        <>
          {evaluation.draftMatch !== null ? (
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
              {strings.ui.policyEvaluationPanel.draftCheck(evaluation.draftMatch)}
            </p>
          ) : null}
          <DecisionResult decision={evaluation.decision} />
        </>
      ) : null}
    </>
  );
}
