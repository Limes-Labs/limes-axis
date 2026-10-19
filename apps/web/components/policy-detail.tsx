"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowLeft,
  FlaskConical,
  GitCompareArrows,
  ScrollText,
  ShieldCheck,
} from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Disclosure } from "@/components/ui/disclosure";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import { toAxisOperatorError } from "@/lib/axis-api";
import { SourcePill } from "@/components/ui/source-pill";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PolicyEvaluationPanel } from "@/components/policy-evaluation-panel";
import { PolicyReviseForm } from "@/components/policy-revise-form";
import { PolicyRevisionCompare } from "@/components/policy-revision-compare";
import {
  buildPlatformPolicyDetailPath,
  fetchPlatformPolicyDetail,
  policyEffectClass,
  policyEffectLabel,
  policyScopeLabel,
  policyStatusClass,
  policyStatusLabel,
  summarizePolicyConditions,
  type PlatformPolicyDetail,
  type PlatformPolicyRecord,
} from "@/lib/platform-policies";
import { formatTimestamp } from "@/lib/format";
import {
  enumUrlField,
  opaqueStringUrlField,
  stringUrlField,
  useConsoleUrlState,
} from "@/lib/console-url-state";
import { deriveSourceState, PROVENANCE_NOT_APPLICABLE } from "@/lib/source-state";
import { useStrings } from "@/providers/locale-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { StatCard } from "@/components/ui/stat-card";
import {
  IDENTITY_SESSION_ENDPOINT,
  useConsoleTenantScope,
} from "@/lib/use-console-tenant-scope";

type DetailSource = "loading" | "api" | "unavailable" | "missing";

const policyDetailTabs = ["conditions", "revisions", "evaluate"] as const;
type PolicyDetailTab = (typeof policyDetailTabs)[number];
const policyDetailUrlSchema = {
  tab: enumUrlField("tab", policyDetailTabs, "conditions"),
  compareRevisionNumber: stringUrlField("compare_revision"),
  // Revision confirmation marker: the durable feedback is derived from the
  // refetched detail record through this marker, surviving the query refresh
  // that recording a revision triggers.
  revisedRevisionNumber: opaqueStringUrlField("revised"),
};

type DetailResult = {
  tenantId: string;
  detail: PlatformPolicyDetail | null;
  errorRequestId: string | null;
  source: Exclude<DetailSource, "loading">;
};

function ConditionTagList({ items, anyLabel }: { items?: string[]; anyLabel: string }) {
  const values = items ?? [];

  return (
    <div className="flex min-w-0 flex-wrap gap-2">
      {values.length > 0 ? (
        values.map((item) => (
          <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={item}>
            {item}
          </span>
        ))
      ) : (
        <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5">{anyLabel}</span>
      )}
    </div>
  );
}

function RevisionHistoryTable({ revisions }: { revisions: PlatformPolicyRecord[] }) {
  const strings = useStrings();
  return (
    <DataTable wrapperProps={{ className: "min-w-0" }}>
      <caption className="sr-only">{strings.ui.policyDetail.policyRevisionHistory}</caption>
      <thead>
        <tr>
          <th>{strings.ui.common.revision}</th>
          <th>{strings.ui.common.effect}</th>
          <th>{strings.ui.common.conditions}</th>
          <th>{strings.ui.common.status}</th>
          <th>{strings.ui.policyDetail.authored}</th>
        </tr>
      </thead>
      <tbody>
        {revisions.map((revision) => (
          <tr key={revision.revision_number}>
            <td>
              <span className="font-mono text-[13px] break-words">
                {strings.ui.common.revisionVersion(revision.revision_number, revision.policy_version)}
              </span>
              {revision.revises_revision_number != null ? (
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{strings.ui.policyDetail.revisesRevision(revision.revises_revision_number)}</p>
              ) : (
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{strings.ui.policyDetail.initialRevision}</p>
              )}
            </td>
            <td>
              <span className={`status-pill ${policyEffectClass(revision.effect)}`}>
                {policyEffectLabel(revision.effect, strings)}
              </span>
            </td>
            <td>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{summarizePolicyConditions(revision.conditions)}</p>
            </td>
            <td>
              <span className={`status-pill ${policyStatusClass(revision.status)}`}>
                {policyStatusLabel(revision.status, strings)}
              </span>
              {revision.replaced_by_revision_number != null ? (
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {strings.ui.policyDetail.supersededBy(revision.replaced_by_revision_number)}
                </p>
              ) : null}
            </td>
            <td>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{revision.created_by}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{formatTimestamp(revision.created_at)}</p>
            </td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

export function PolicyDetail({ policyId }: { policyId: string }) {
  const strings = useStrings();
  const [result, setResult] = useState<DetailResult | null>(null);
  const [urlState, setUrlState] = useConsoleUrlState(policyDetailUrlSchema);
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();
  const { identity, tenantId, tenantQueriesEnabled } = useConsoleTenantScope();
  const detailPath = buildPlatformPolicyDetailPath(policyId, tenantId ?? undefined);

  useEffect(() => {
    if (!tenantQueriesEnabled || !tenantId) {
      return;
    }
    const requestedTenantId: string = tenantId;

    const controller = new AbortController();

    async function fetchPolicy() {
      try {
        const policyDetail = await fetchPlatformPolicyDetail(
          policyId,
          {
            session,
            signal: controller.signal,
          },
          requestedTenantId,
        );

        if (policyDetail === null) {
          setResult({
            tenantId: requestedTenantId,
            detail: null,
            errorRequestId: null,
            source: "missing",
          });
          return;
        }

        if (policyDetail.tenant_id !== requestedTenantId) {
          throw new Error(`Policy detail tenant does not match ${requestedTenantId}.`);
        }

        setResult({
          tenantId: requestedTenantId,
          detail: policyDetail,
          errorRequestId: null,
          source: "api",
        });
      } catch (caught) {
        if (!controller.signal.aborted) {
          setResult({
            tenantId: requestedTenantId,
            detail: null,
            errorRequestId: toAxisOperatorError(
              caught,
              strings.policyDetail.error.detailDetail,
            ).requestId,
            source: "unavailable",
          });
        }
      }
    }

    void fetchPolicy();

    return () => controller.abort();
  }, [policyId, session, refreshNonce, strings, tenantId, tenantQueriesEnabled]);

  useEffect(() => {
    const detail = result?.tenantId === tenantId ? result.detail : null;
    if (!detail || !urlState.compareRevisionNumber) {
      return;
    }

    const comparisonExists = detail.revisions.some(
      (revision) => (
        revision.revision_number !== detail.current_revision.revision_number
        && String(revision.revision_number) === urlState.compareRevisionNumber
      ),
    );
    if (!comparisonExists) {
      setUrlState({ compareRevisionNumber: "" });
    }
  }, [result, setUrlState, tenantId, urlState.compareRevisionNumber]);

  if (identity.source === "loading") {
    return <LoadingPanel layout="detail" />;
  }

  if (identity.source === "unavailable" || !tenantId) {
    return (
      <ErrorPanel
        detail={strings.ui.common.theConsoleCouldNotVerify}
        endpoint={IDENTITY_SESSION_ENDPOINT}
        reference={identity.errorRequestId ?? undefined}
        onRetry={identity.refetch}
        title={strings.states.identityUnavailable.title}
      />
    );
  }

  const detail = result?.tenantId === tenantId ? result.detail : null;
  const source: DetailSource = result?.tenantId === tenantId ? result.source : "loading";

  if (!detail) {
    if (source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    if (source !== "missing") {
      return (
        <ErrorPanel
          detail={strings.policyDetail.error.detailDetail}
          endpoint={detailPath}
          reference={result?.errorRequestId ?? undefined}
          title={strings.policyDetail.error.title}
        />
      );
    }

    return (
      <div className="grid min-w-0 gap-4">
        <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">{strings.ui.policyDetail.platformPolicy}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.policyDetail.policyNotFound}</h2>
            <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{policyId}</p>
          </div>
          <Link className={buttonVariants({ variant: "secondary" })} href="/policies">
            <ArrowLeft size={17} />
            {strings.ui.common.policies}
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
      (revision) => String(revision.revision_number) === urlState.compareRevisionNumber,
    ) ?? null;
  const compareRevisionNumber = compareRevision ? urlState.compareRevisionNumber : "";

  return (
    <div className="grid min-w-0 gap-4">
      <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">{policyScopeLabel(current.scope, strings)}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{current.display_name}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{current.description}</p>
          <Disclosure className="mt-1 text-xs text-muted" size="sm" title={strings.identifiers.inspectIdentifiers} variant="plain">
            <p className="m-0 leading-snug break-words font-mono text-[13px]">
              {detail.policy_id} / {detail.tenant_id}
            </p>
          </Disclosure>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2" aria-label={strings.ui.policyDetail.policySourceAndStatus}>
          <SourcePill
            state={deriveSourceState(
              source === "missing" ? "unavailable" : source,
              Boolean(detail),
              PROVENANCE_NOT_APPLICABLE,
            )}
            subject="policy"
          />
          <span className={`status-pill ${policyEffectClass(current.effect)}`}>
            <ShieldCheck size={15} />
            {policyEffectLabel(current.effect, strings)}
          </span>
          <Link className={buttonVariants({ variant: "secondary" })} href="/policies">
            <ArrowLeft size={17} />
            {strings.ui.common.policies}
          </Link>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 [&>*]:min-w-0" role="list">
        <StatCard
          detail={current.policy_version}
          label={strings.ui.policyDetail.currentRevision}
          value={strings.ui.common.revisionNumber(current.revision_number)}
          valueVariant="mono"
        />
        <StatCard
          detail={strings.ui.policyDetail.onlyTheActiveRevisionIs}
          label={strings.ui.common.status}
          value={policyStatusLabel(current.status, strings)}
        />
        <StatCard
          detail={formatTimestamp(current.created_at)}
          label={strings.ui.policyDetail.authoredBy}
          value={current.created_by}
          valueVariant="mono"
        />
        <StatCard
          detail={current.audit_event_type}
          label={strings.ui.policyDetail.authoringScope}
          value={current.required_authoring_scope}
          valueVariant="mono"
        />
      </div>

      <Tabs
        className="grid min-w-0 gap-3"
        onValueChange={(tab) =>
          setUrlState({ tab: tab as PolicyDetailTab }, { history: "push" })
        }
        value={urlState.tab}
      >
        <TabsList>
          <TabsTrigger value="conditions">{strings.policyDetail.tabs.conditions}</TabsTrigger>
          <TabsTrigger value="revisions">{strings.policyDetail.tabs.revisions}</TabsTrigger>
          <TabsTrigger value="evaluate">{strings.policyDetail.tabs.evaluate}</TabsTrigger>
        </TabsList>

        <TabsContent className="grid min-w-0 gap-4" value="conditions">
          <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
            <p className="eyebrow m-0">{strings.ui.policyDetail.ruleConditions}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
              {summarizePolicyConditions(current.conditions)}
            </h2>
            <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
              <div>
                <p className="eyebrow m-0">{strings.ui.common.actionDomains}</p>
                <ConditionTagList
                  anyLabel="Any domain"
                  items={current.conditions.action_domains}
                />
              </div>
              <div>
                <p className="eyebrow m-0">{strings.ui.policyDetail.riskLevels}</p>
                <ConditionTagList
                  anyLabel="Any risk level"
                  items={current.conditions.risk_levels}
                />
              </div>
              <div>
                <p className="eyebrow m-0">{strings.ui.policyDetail.autonomyLevels}</p>
                <ConditionTagList
                  anyLabel="Any autonomy level"
                  items={current.conditions.autonomy_levels}
                />
              </div>
              <div>
                <p className="eyebrow m-0">{strings.ui.common.amountThreshold}</p>
                <p className="m-0 font-mono text-[13px] font-medium text-ink break-words">
                  {current.conditions.requested_amount_at_least != null
                    ? `>= ${current.conditions.requested_amount_at_least}`
                    : strings.ui.policyDetail.noAmountGate}
                </p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {strings.ui.policyDetail.malformedAmountsFailClosed}
                </p>
              </div>
            </div>
            {current.notes && current.notes.length > 0 ? (
              <div className="grid min-w-0 gap-2.5">
                {current.notes.map((note) => (
                  <p
                    className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words"
                    key={note}
                  >
                    {note}
                  </p>
                ))}
              </div>
            ) : null}
          </section>

          <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
            <p className="eyebrow m-0">{strings.policyDetail.precedence.eyebrow}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
              {strings.policyDetail.precedence.title}
            </h2>
            <div className="grid min-w-0 gap-2.5">
              {[
                ...strings.policyDetail.precedence.steps,
                strings.policyDetail.precedence.defaultAllowTitle,
              ].map((step) => (
                <p
                  className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words"
                  key={step}
                >
                  {step}
                </p>
              ))}
            </div>
          </section>
        </TabsContent>

        <TabsContent className="grid min-w-0 gap-4" value="revisions">
          {urlState.revisedRevisionNumber ? (
            <div
              aria-label={strings.ui.policyDetail.policyRevisionResult}
              className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl border border-signal/30 bg-tint-50 px-4 py-3 dark:border-signal/40 dark:bg-signal/10"
              data-policy-revised
              role="status"
            >
              <p className="m-0 min-w-0 text-sm leading-snug break-words text-ink">
                {strings.ui.policyDetail.revisionRecorded(
                  urlState.revisedRevisionNumber,
                  current.revision_number,
                  current.policy_version,
                )}
              </p>
              <button
                className="inline-flex min-h-6 cursor-pointer items-center font-mono text-xs text-muted transition-colors hover:text-signal"
                onClick={() => setUrlState({ revisedRevisionNumber: "" })}
                type="button"
              >
                {strings.ui.common.dismiss}
              </button>
            </div>
          ) : null}
          <PolicyReviseForm
            current={current}
            key={`revise-${current.revision_number}`}
            tenantId={detail.tenant_id}
          />

          <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
              <div>
                <p className="eyebrow m-0">{strings.ui.policyDetail.revisionHistory}</p>
                <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
                  {strings.ui.policyDetail.appendOnlyRevisions(detail.revisions.length)}
                </h2>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {strings.ui.policyDetail.supersededRevisionsStayReadableBut}
                </p>
              </div>
              <ScrollText size={18} />
            </div>
          </section>
          <RevisionHistoryTable revisions={detail.revisions} />

          <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
              <div>
                <p className="eyebrow m-0">{strings.ui.policyDetail.revisionCompare}</p>
                <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
                  {strings.ui.policyDetail.diffARevisionAgainstThe}
                </h2>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {strings.ui.policyDetail.fieldLevelCompareOfName}
                </p>
              </div>
              <GitCompareArrows size={18} />
            </div>
            {compareCandidates.length > 0 ? (
              <div className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]">
                <Field label={strings.ui.policyDetail.compareRevision}>
                  <Select
                    aria-label={strings.ui.policyDetail.revisionToCompare}
                    onChange={(event) =>
                      setUrlState({ compareRevisionNumber: event.target.value })
                    }
                    value={compareRevisionNumber}
                  >
                    <option value="">{strings.ui.policyDetail.selectARevision}</option>
                    {compareCandidates.map((revision) => (
                      <option key={revision.revision_number} value={revision.revision_number}>
                        {strings.ui.common.revisionVersion(revision.revision_number, revision.policy_version)}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            ) : (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {strings.ui.policyDetail.onlyTheInitialRevisionExists}
              </p>
            )}
            {compareRevision ? (
              <PolicyRevisionCompare base={compareRevision} target={current} />
            ) : null}
          </section>
        </TabsContent>

        <TabsContent className="grid min-w-0 gap-4" value="evaluate">
          <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
              <div>
                <p className="eyebrow m-0">{strings.ui.policyDetail.dryRunEvaluation}</p>
                <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
                  {strings.ui.policyDetail.evaluateAContextAgainstTenant}
                </h2>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {strings.ui.policyDetail.dryRunOnlyEvaluationIs}
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
