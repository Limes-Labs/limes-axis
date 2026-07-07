"use client";

import { useState, type FormEvent } from "react";
import { FlaskConical } from "lucide-react";

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
  | { phase: "failed"; message: string };

type PolicyEvaluationPanelProps = {
  tenantId: string;
  scope: PlatformPolicyScope;
  scopeLocked?: boolean;
  draftConditions?: PlatformPolicyRuleConditions | null;
  formLabel: string;
};

function DecisionResult({ decision }: { decision: PlatformPolicyDecision }) {
  const matchedPolicies = decision.matched_policies ?? [];
  const evidenceEntries = Object.entries(decision.evidence ?? {});

  return (
    <div className="stack">
      <div className="row">
        <div>
          <p className="metric-label">Decision</p>
          <p className="row-title">{policyEffectLabel(decision.effect)}</p>
          <p className="row-detail">
            {decision.matched && decision.matched_policy_id
              ? `Matched ${decision.matched_policy_id} r${decision.matched_revision_number} / ${decision.matched_policy_version}`
              : "No active policy matched this context"}
          </p>
          <p className="row-detail">
            {decision.evaluated_policy_count} active policies evaluated
            {decision.precedence_rule ? ` / ${decision.precedence_rule}` : ""}
          </p>
        </div>
        <span className={`status-pill ${policyEffectClass(decision.effect)}`}>
          {policyEffectLabel(decision.effect)}
        </span>
      </div>

      {matchedPolicies.length > 0 ? (
        <div>
          <p className="metric-label">Matched Policies</p>
          <div className="payload-grid">
            {matchedPolicies.map((match) => (
              <div className="payload-row" key={`${match.policy_id}-${match.revision_number}`}>
                <span>
                  <span className="metric-label">{match.policy_id}</span>
                  <span className="row-detail">
                    r{match.revision_number} / {match.policy_version}
                  </span>
                </span>
                <span className="mono">{match.effect}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {evidenceEntries.length > 0 ? (
        <div>
          <p className="metric-label">Evidence Payload</p>
          <div className="payload-grid">
            {evidenceEntries.map(([key, value]) => (
              <div className="payload-row" key={key}>
                <span className="metric-label">{key}</span>
                <span className="mono">{JSON.stringify(value)}</span>
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
      setEvaluation({ phase: "failed", message: parsedAmount.message });
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
    } catch (error) {
      setEvaluation({
        phase: "failed",
        message:
          error instanceof Error ? error.message : "Policy evaluation API is unavailable.",
      });
    }
  }

  return (
    <>
      <form
        aria-label={formLabel}
        className="policy-authoring-form"
        onSubmit={(event) => void runEvaluation(event)}
      >
        <label>
          <span className="metric-label">Scope</span>
          <select
            aria-label="Evaluation scope"
            disabled={scopeLocked}
            onChange={(event) => updateField("scope", event.target.value)}
            value={form.scope}
          >
            {platformPolicyScopes.map((scopeOption) => (
              <option key={scopeOption} value={scopeOption}>
                {policyScopeLabel(scopeOption)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="metric-label">Action Domain</span>
          <input
            aria-label="Action domain"
            onChange={(event) => updateField("actionDomain", event.target.value)}
            placeholder="Operations"
            type="text"
            value={form.actionDomain}
          />
        </label>
        <label>
          <span className="metric-label">Risk Level</span>
          <select
            aria-label="Risk level"
            onChange={(event) => updateField("riskLevel", event.target.value)}
            value={form.riskLevel}
          >
            <option value="">Not set</option>
            {platformPolicyRiskLevels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="metric-label">Autonomy Level</span>
          <select
            aria-label="Autonomy level"
            onChange={(event) => updateField("autonomyLevel", event.target.value)}
            value={form.autonomyLevel}
          >
            <option value="">Not set</option>
            {platformPolicyAutonomyLevels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="metric-label">Requested Amount</span>
          <input
            aria-label="Requested amount"
            min="0"
            onChange={(event) => updateField("requestedAmount", event.target.value)}
            placeholder="Optional"
            step="any"
            type="number"
            value={form.requestedAmount}
          />
        </label>
        <button
          className="command-button"
          disabled={evaluation.phase === "evaluating"}
          type="submit"
        >
          <FlaskConical size={15} />
          {evaluation.phase === "evaluating" ? "Evaluating" : "Run dry-run evaluation"}
        </button>
      </form>

      {evaluation.phase === "failed" ? (
        <p className="row-detail" role="alert">
          Dry-run evaluation failed: {evaluation.message}
        </p>
      ) : null}
      {evaluation.phase === "decided" ? (
        <>
          {evaluation.draftMatch !== null ? (
            <p className="row-detail">
              Advisory draft check: the drafted conditions{" "}
              {evaluation.draftMatch ? "would match" : "would not match"} this sample context.
              The decision below only evaluates policies already persisted for the tenant.
            </p>
          ) : null}
          <DecisionResult decision={evaluation.decision} />
        </>
      ) : null}
    </>
  );
}
