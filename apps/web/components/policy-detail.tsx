"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, FlaskConical, RadioTower, ScrollText, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import {
  buildPlatformPolicyDetailPath,
  buildPolicyEvaluationPayload,
  evaluatePlatformPolicy,
  fetchPlatformPolicyDetail,
  parseRequestedAmount,
  platformPolicyAutonomyLevels,
  platformPolicyPrecedenceSteps,
  platformPolicyRiskLevels,
  platformPolicyScopes,
  policyEffectClass,
  policyEffectLabel,
  policyScopeLabel,
  policyStatusClass,
  policyStatusLabel,
  summarizePolicyConditions,
  type PlatformPolicyDecision,
  type PlatformPolicyDetail,
  type PlatformPolicyRecord,
  type PlatformPolicyScope,
} from "@/lib/platform-policies";
import { formatOverviewTimestamp } from "@/lib/platform-overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type DetailSource = "loading" | "api" | "unavailable" | "missing";

type EvaluationFormFields = {
  scope: PlatformPolicyScope;
  actionId: string;
  actionDomain: string;
  riskLevel: string;
  autonomyLevel: string;
  requestedAmount: string;
};

type EvaluationState =
  | { phase: "idle" }
  | { phase: "evaluating" }
  | { phase: "decided"; decision: PlatformPolicyDecision }
  | { phase: "failed"; message: string };

function sourceLabel(source: DetailSource): string {
  if (source === "api") {
    return "API policy detail";
  }

  if (source === "missing") {
    return "Policy not found";
  }

  return source === "loading" ? "Loading policy API" : "Policy API unavailable";
}

function ConditionTagList({ items, anyLabel }: { items: string[]; anyLabel: string }) {
  return (
    <div className="tag-list">
      {items.length > 0 ? (
        items.map((item) => (
          <span className="tag" key={item}>
            {item}
          </span>
        ))
      ) : (
        <span className="tag">{anyLabel}</span>
      )}
    </div>
  );
}

function RevisionHistoryTable({ revisions }: { revisions: PlatformPolicyRecord[] }) {
  return (
    <section className="table-panel">
      <table className="data-table">
        <thead>
          <tr>
            <th>Revision</th>
            <th>Effect</th>
            <th>Conditions</th>
            <th>Status</th>
            <th>Authored</th>
          </tr>
        </thead>
        <tbody>
          {revisions.map((revision) => (
            <tr key={revision.revision_number}>
              <td>
                <span className="mono">
                  r{revision.revision_number} / {revision.policy_version}
                </span>
                {revision.revises_revision_number !== null ? (
                  <p className="row-detail">Revises r{revision.revises_revision_number}</p>
                ) : (
                  <p className="row-detail">Initial revision</p>
                )}
              </td>
              <td>
                <span className={`status-pill ${policyEffectClass(revision.effect)}`}>
                  {policyEffectLabel(revision.effect)}
                </span>
              </td>
              <td>
                <p className="row-detail">{summarizePolicyConditions(revision.conditions)}</p>
              </td>
              <td>
                <span className={`status-pill ${policyStatusClass(revision.status)}`}>
                  {policyStatusLabel(revision.status)}
                </span>
                {revision.replaced_by_revision_number !== null ? (
                  <p className="row-detail">
                    Superseded by r{revision.replaced_by_revision_number}
                  </p>
                ) : null}
              </td>
              <td>
                <p className="row-detail">{revision.created_by}</p>
                <p className="row-detail">{formatOverviewTimestamp(revision.created_at)}</p>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function DecisionResult({ decision }: { decision: PlatformPolicyDecision }) {
  const evidenceEntries = Object.entries(decision.evidence);

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
            {decision.evaluated_policy_count} active policies evaluated /{" "}
            {decision.precedence_rule}
          </p>
        </div>
        <span className={`status-pill ${policyEffectClass(decision.effect)}`}>
          {policyEffectLabel(decision.effect)}
        </span>
      </div>

      {decision.matched_policies.length > 0 ? (
        <div>
          <p className="metric-label">Matched Policies</p>
          <div className="payload-grid">
            {decision.matched_policies.map((match) => (
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

export function PolicyDetail({ policyId }: { policyId: string }) {
  const [detail, setDetail] = useState<PlatformPolicyDetail | null>(null);
  const [source, setSource] = useState<DetailSource>("loading");
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();

  const [evaluationForm, setEvaluationForm] = useState<EvaluationFormFields>({
    scope: "action_execution",
    actionId: "",
    actionDomain: "",
    riskLevel: "",
    autonomyLevel: "",
    requestedAmount: "",
  });
  const [evaluation, setEvaluation] = useState<EvaluationState>({ phase: "idle" });

  useEffect(() => {
    const controller = new AbortController();

    async function fetchPolicy() {
      try {
        const policyDetail = await fetchPlatformPolicyDetail(policyId, {
          session,
          signal: controller.signal,
        });

        if (policyDetail === null) {
          setDetail(null);
          setSource("missing");
          return;
        }

        setDetail(policyDetail);
        setSource("api");
        setEvaluationForm((current) => ({
          ...current,
          scope: policyDetail.current_revision.scope,
        }));
      } catch {
        if (!controller.signal.aborted) {
          setDetail(null);
          setSource("unavailable");
        }
      }
    }

    void fetchPolicy();

    return () => controller.abort();
  }, [policyId, session, refreshNonce]);

  function updateEvaluationField(field: keyof EvaluationFormFields, value: string) {
    setEvaluationForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function runEvaluation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!detail) {
      return;
    }

    const parsedAmount = parseRequestedAmount(evaluationForm.requestedAmount);

    if (!parsedAmount.ok) {
      setEvaluation({ phase: "failed", message: parsedAmount.message });
      return;
    }

    setEvaluation({ phase: "evaluating" });

    try {
      const decision = await evaluatePlatformPolicy(
        buildPolicyEvaluationPayload(detail.tenant_id, {
          scope: evaluationForm.scope,
          actionId: evaluationForm.actionId,
          actionDomain: evaluationForm.actionDomain,
          riskLevel: evaluationForm.riskLevel,
          autonomyLevel: evaluationForm.autonomyLevel,
          requestedAmount: parsedAmount.amount,
        }),
        { session },
      );
      setEvaluation({ phase: "decided", decision });
    } catch (error) {
      setEvaluation({
        phase: "failed",
        message:
          error instanceof Error ? error.message : "Policy evaluation API is unavailable.",
      });
    }
  }

  if (!detail) {
    if (source !== "missing") {
      return (
        <ApiRequiredState
          detail="Axis did not receive an API-backed platform policy. Local fallback policy records are disabled."
          endpoint={buildPlatformPolicyDetailPath(policyId)}
          title={source === "loading" ? "Loading policy API" : "Policy API unavailable"}
        />
      );
    }

    return (
      <div className="console-stack">
        <section className="panel overview-context">
          <div>
            <p className="section-label">Platform Policy</p>
            <h2 className="panel-title">Policy not found</h2>
            <p className="row-detail mono">{policyId}</p>
          </div>
          <Link className="command-button" href="/policies">
            <ArrowLeft size={17} />
            Policies
          </Link>
        </section>
      </div>
    );
  }

  const current = detail.current_revision;

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">{policyScopeLabel(current.scope)}</p>
          <h2 className="panel-title">{current.display_name}</h2>
          <p className="row-detail">{current.description}</p>
          <p className="row-detail mono">
            {detail.policy_id} / {detail.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Policy source and status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${policyEffectClass(current.effect)}`}>
            <ShieldCheck size={15} />
            {policyEffectLabel(current.effect)}
          </span>
          <Link className="command-button" href="/policies">
            <ArrowLeft size={17} />
            Policies
          </Link>
        </div>
      </section>

      <div className="metric-grid">
        <article className="metric-card compact-card">
          <p className="metric-label">Current Revision</p>
          <p className="metric-value mono">r{current.revision_number}</p>
          <p className="metric-detail">{current.policy_version}</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Status</p>
          <p className="metric-value">{policyStatusLabel(current.status)}</p>
          <p className="metric-detail">Only the active revision is evaluated</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Authored By</p>
          <p className="metric-value">{current.created_by}</p>
          <p className="metric-detail">{formatOverviewTimestamp(current.created_at)}</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Authoring Scope</p>
          <p className="metric-value mono">{current.required_authoring_scope}</p>
          <p className="metric-detail">{current.audit_event_type}</p>
        </article>
      </div>

      <section className="panel">
        <p className="section-label">Rule Conditions</p>
        <h2 className="panel-title">{summarizePolicyConditions(current.conditions)}</h2>
        <div className="approval-detail-grid">
          <div>
            <p className="metric-label">Action Domains</p>
            <ConditionTagList anyLabel="Any domain" items={current.conditions.action_domains} />
          </div>
          <div>
            <p className="metric-label">Risk Levels</p>
            <ConditionTagList anyLabel="Any risk level" items={current.conditions.risk_levels} />
          </div>
          <div>
            <p className="metric-label">Autonomy Levels</p>
            <ConditionTagList
              anyLabel="Any autonomy level"
              items={current.conditions.autonomy_levels}
            />
          </div>
          <div>
            <p className="metric-label">Amount Threshold</p>
            <p className="row-title mono">
              {current.conditions.requested_amount_at_least !== null
                ? `>= ${current.conditions.requested_amount_at_least}`
                : "No amount gate"}
            </p>
            <p className="row-detail">Malformed amounts fail closed</p>
          </div>
        </div>
        {current.notes.length > 0 ? (
          <div className="stack">
            {current.notes.map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel">
        <p className="section-label">Evaluation Precedence</p>
        <h2 className="panel-title">Deterministic decision order</h2>
        <div className="stack">
          {platformPolicyPrecedenceSteps.map((step) => (
            <p className="row-detail" key={step}>
              {step}
            </p>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="row">
          <div>
            <p className="section-label">Revision History</p>
            <h2 className="panel-title">{detail.revisions.length} append-only revisions</h2>
            <p className="row-detail">
              Superseded revisions stay readable but are never evaluated.
            </p>
          </div>
          <ScrollText size={18} />
        </div>
      </section>
      <RevisionHistoryTable revisions={detail.revisions} />

      <section className="panel">
        <div className="row">
          <div>
            <p className="section-label">Dry-Run Evaluation</p>
            <h2 className="panel-title">Evaluate a context against tenant policies</h2>
            <p className="row-detail">
              Dry run only: evaluation is deterministic, records no audit event and never
              mutates state.
            </p>
          </div>
          <FlaskConical size={18} />
        </div>
        <form
          aria-label="Policy dry-run evaluation"
          className="policy-authoring-form"
          onSubmit={(event) => void runEvaluation(event)}
        >
          <label>
            <span className="metric-label">Scope</span>
            <select
              aria-label="Evaluation scope"
              onChange={(event) => updateEvaluationField("scope", event.target.value)}
              value={evaluationForm.scope}
            >
              {platformPolicyScopes.map((scope) => (
                <option key={scope} value={scope}>
                  {policyScopeLabel(scope)}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Action Domain</span>
            <input
              aria-label="Action domain"
              onChange={(event) => updateEvaluationField("actionDomain", event.target.value)}
              placeholder="Operations"
              type="text"
              value={evaluationForm.actionDomain}
            />
          </label>
          <label>
            <span className="metric-label">Risk Level</span>
            <select
              aria-label="Risk level"
              onChange={(event) => updateEvaluationField("riskLevel", event.target.value)}
              value={evaluationForm.riskLevel}
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
              onChange={(event) => updateEvaluationField("autonomyLevel", event.target.value)}
              value={evaluationForm.autonomyLevel}
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
              onChange={(event) => updateEvaluationField("requestedAmount", event.target.value)}
              placeholder="Optional"
              step="any"
              type="number"
              value={evaluationForm.requestedAmount}
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
        {evaluation.phase === "decided" ? <DecisionResult decision={evaluation.decision} /> : null}
      </section>
    </div>
  );
}
