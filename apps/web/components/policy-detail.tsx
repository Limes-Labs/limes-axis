"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, FlaskConical, GitCompareArrows, RadioTower, ScrollText, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { PolicyEvaluationPanel } from "@/components/policy-evaluation-panel";
import { PolicyReviseForm } from "@/components/policy-revise-form";
import { PolicyRevisionCompare } from "@/components/policy-revision-compare";
import {
  buildPlatformPolicyDetailPath,
  fetchPlatformPolicyDetail,
  platformPolicyPrecedenceSteps,
  policyEffectClass,
  policyEffectLabel,
  policyScopeLabel,
  policyStatusClass,
  policyStatusLabel,
  summarizePolicyConditions,
  type PlatformPolicyDetail,
  type PlatformPolicyRecord,
} from "@/lib/platform-policies";
import { formatOverviewTimestamp } from "@/lib/platform-overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type DetailSource = "loading" | "api" | "unavailable" | "missing";

function sourceLabel(source: DetailSource): string {
  if (source === "api") {
    return "API policy detail";
  }

  if (source === "missing") {
    return "Policy not found";
  }

  return source === "loading" ? "Loading policy API" : "Policy API unavailable";
}

function ConditionTagList({ items, anyLabel }: { items?: string[]; anyLabel: string }) {
  const values = items ?? [];

  return (
    <div className="tag-list">
      {values.length > 0 ? (
        values.map((item) => (
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
                {revision.revises_revision_number != null ? (
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
                {revision.replaced_by_revision_number != null ? (
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

export function PolicyDetail({ policyId }: { policyId: string }) {
  const [detail, setDetail] = useState<PlatformPolicyDetail | null>(null);
  const [source, setSource] = useState<DetailSource>("loading");
  const [compareRevisionNumber, setCompareRevisionNumber] = useState("");
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();

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
  const compareCandidates = detail.revisions.filter(
    (revision) => revision.revision_number !== current.revision_number,
  );
  const compareRevision =
    compareCandidates.find(
      (revision) => String(revision.revision_number) === compareRevisionNumber,
    ) ?? null;

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
              {current.conditions.requested_amount_at_least != null
                ? `>= ${current.conditions.requested_amount_at_least}`
                : "No amount gate"}
            </p>
            <p className="row-detail">Malformed amounts fail closed</p>
          </div>
        </div>
        {current.notes && current.notes.length > 0 ? (
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

      <PolicyReviseForm
        current={current}
        key={`revise-${current.revision_number}`}
        tenantId={detail.tenant_id}
      />

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
            <p className="section-label">Revision Compare</p>
            <h2 className="panel-title">Diff a revision against the current one</h2>
            <p className="row-detail">
              Field-level compare of name, description, effect and typed conditions.
            </p>
          </div>
          <GitCompareArrows size={18} />
        </div>
        {compareCandidates.length > 0 ? (
          <div className="policy-authoring-form">
            <label>
              <span className="metric-label">Compare Revision</span>
              <select
                aria-label="Revision to compare"
                onChange={(event) => setCompareRevisionNumber(event.target.value)}
                value={compareRevisionNumber}
              >
                <option value="">Select a revision</option>
                {compareCandidates.map((revision) => (
                  <option key={revision.revision_number} value={revision.revision_number}>
                    r{revision.revision_number} / {revision.policy_version}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <p className="row-detail">
            Only the initial revision exists; append a revision to compare definitions.
          </p>
        )}
        {compareRevision ? (
          <PolicyRevisionCompare base={compareRevision} target={current} />
        ) : null}
      </section>

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
        <PolicyEvaluationPanel
          formLabel="Policy dry-run evaluation"
          scope={current.scope}
          tenantId={detail.tenant_id}
        />
      </section>
    </div>
  );
}
