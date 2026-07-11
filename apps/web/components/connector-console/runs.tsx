"use client";

import { Fragment, useState } from "react";
import Link from "next/link";
import { CheckCircle2, CircleDashed, CircleX, Loader2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Eyebrow } from "@/components/ui/eyebrow";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import { axisFetch } from "@/lib/axis-api";
import { buildAuditEventHref } from "@/lib/audit-demo";
import { cn } from "@/lib/cn";
import {
  buildCsvFromPreviewSample,
  buildExternalDbPreviewRequest,
  buildPreviewSyncPlan,
  CONNECTOR_CONSOLE_ACTOR,
  CONNECTOR_TENANT_ID,
  findActiveLeaseForConnector,
  manifestAllowsRuns,
  manifestRecordForConnector,
} from "@/lib/connectors-console";
import {
  formatConnectorLabel,
  type ConnectorCsvPreviewResult,
  type ConnectorExternalDbPreviewResult,
  type ConnectorRegistryItem,
  type ConnectorRunRecord,
} from "@/lib/connectors-demo";
import { safeRandomUuid } from "@/lib/ids";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";
import type { ConnectorRegistries } from "@/lib/use-connector-registries";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

/*
 * Runs tab: recorded governed runs plus two real actions against the live
 * API — Validate (re-runs the preview endpoint for the connector's recorded
 * sample) and Run sync (preview), a three-stage flow of POST /connectors/runs
 * -> dispatch -> execute-sync. Every stage surfaces the API's own status and
 * links to the audit evidence it wrote.
 */

const CSV_PREVIEW_ENDPOINT = "/demo/manufacturing/connectors/file-csv/preview";
const DB_PREVIEW_ENDPOINT = "/demo/manufacturing/connectors/external-db/preview";
const RUNS_ENDPOINT = "/demo/manufacturing/connectors/runs";

type StageKey = "create" | "dispatch" | "execute";
type StageStatus = "idle" | "pending" | "success" | "failure";

type StageState = {
  status: StageStatus;
  /** Status string reported by the API response for this stage. */
  resultStatus?: string;
  auditEventId?: string | null;
  errorDetail?: string;
};

type StepperState = Record<StageKey, StageState>;

const IDLE_STEPPER: StepperState = {
  create: { status: "idle" },
  dispatch: { status: "idle" },
  execute: { status: "idle" },
};

type ValidateOutcome =
  | { kind: "csv"; result: ConnectorCsvPreviewResult }
  | { kind: "db"; result: ConnectorExternalDbPreviewResult }
  | { kind: "error" };

async function readApiErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: { message?: string; reason?: string; required_permission?: string };
    };
    return (
      payload.detail?.message
      ?? payload.detail?.reason
      ?? payload.detail?.required_permission
      ?? `Request failed with ${response.status}`
    );
  } catch {
    return `Request failed with ${response.status}`;
  }
}

function formatRunTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function StageIcon({ status }: { status: StageStatus }) {
  if (status === "success") {
    return <CheckCircle2 aria-hidden="true" className="text-positive" size={17} />;
  }
  if (status === "failure") {
    return <CircleX aria-hidden="true" className="text-danger" size={17} />;
  }
  if (status === "pending") {
    return <Loader2 aria-hidden="true" className="animate-spin text-signal" size={17} />;
  }
  return <CircleDashed aria-hidden="true" className="text-muted" size={17} />;
}

export function ConnectorRuns({
  connector,
  registries,
}: {
  connector: ConnectorRegistryItem;
  registries: ConnectorRegistries;
}) {
  const copy = strings.connectors.runs;
  const connectorId = connector.manifest.connector_id;
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const { data: identitySession } = useAxisQuery<IdentitySessionReadModel>(
    "/identity/session",
  );

  const [validating, setValidating] = useState(false);
  const [validateOutcome, setValidateOutcome] = useState<ValidateOutcome | null>(null);
  const [stepper, setStepper] = useState<StepperState>(IDLE_STEPPER);
  const [syncRunning, setSyncRunning] = useState(false);

  const runsQuery = registries.runs;
  const connectorRuns = (runsQuery.data?.runs ?? [])
    .filter((run) => run.connector_id === connectorId)
    .slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at));

  const lease = findActiveLeaseForConnector(
    registries.credentialLeases.data?.leases ?? [],
    connectorId,
    new Date(),
  );
  const manifestRecord = registries.manifests.data
    ? manifestRecordForConnector(registries.manifests.data.manifests, connectorId)
    : null;
  const runsAllowed = manifestAllowsRuns(manifestRecord);
  const ssoBlocked = identitySession != null && !identitySession.authenticated;
  const actorId = identitySession?.actor_id ?? CONNECTOR_CONSOLE_ACTOR;
  const syncBlockedReason = ssoBlocked
    ? copy.sync.ssoGate
    : !runsAllowed
      ? copy.sync.manifestMissing
      : !lease
        ? copy.sync.leaseMissing
        : null;

  async function validate() {
    setValidating(true);
    setValidateOutcome(null);
    try {
      if (connector.manifest.connector_type === "external_db") {
        const response = await axisFetch(DB_PREVIEW_ENDPOINT, {
          method: "POST",
          session,
          body: buildExternalDbPreviewRequest({
            tenantId: CONNECTOR_TENANT_ID,
            connectorId,
            connectionProfileId: "profile_postgres_ops_readonly",
            schemaName: "operations",
            tableName: "production_orders",
            credentialHandleId: "cred_external_db_readonly",
            template: connector,
          }),
        });
        if (!response.ok) {
          setValidateOutcome({ kind: "error" });
          return;
        }
        setValidateOutcome({
          kind: "db",
          result: (await response.json()) as ConnectorExternalDbPreviewResult,
        });
        return;
      }

      const response = await axisFetch(CSV_PREVIEW_ENDPOINT, {
        method: "POST",
        session,
        body: {
          tenant_id: CONNECTOR_TENANT_ID,
          connector_id: connectorId,
          file_name: connector.preview_sample.file_name,
          csv_content: buildCsvFromPreviewSample(connector.preview_sample),
        },
      });
      if (!response.ok) {
        setValidateOutcome({ kind: "error" });
        return;
      }
      setValidateOutcome({
        kind: "csv",
        result: (await response.json()) as ConnectorCsvPreviewResult,
      });
    } catch {
      setValidateOutcome({ kind: "error" });
    } finally {
      setValidating(false);
    }
  }

  async function runStage(
    key: StageKey,
    path: string,
    body: unknown,
  ): Promise<ConnectorRunRecord | null> {
    setStepper((current) => ({ ...current, [key]: { status: "pending" } }));
    try {
      const response = await axisFetch(path, { method: "POST", session, body });
      if (!response.ok) {
        const errorDetail = await readApiErrorMessage(response);
        setStepper((current) => ({
          ...current,
          [key]: { status: "failure", errorDetail },
        }));
        return null;
      }
      const record = (await response.json()) as ConnectorRunRecord;
      const resultStatus =
        key === "create"
          ? (record.schedule_result?.status ?? record.status)
          : key === "dispatch"
            ? (record.dispatch_result?.status ?? record.status)
            : (record.sync_execution_result?.status ?? record.status);
      setStepper((current) => ({
        ...current,
        [key]: {
          status: "success",
          resultStatus,
          auditEventId: record.audit_event_id,
        },
      }));
      return record;
    } catch {
      setStepper((current) => ({
        ...current,
        [key]: { status: "failure", errorDetail: "The Axis API request failed." },
      }));
      return null;
    }
  }

  async function runPreviewSync() {
    if (!lease || syncRunning) {
      return;
    }
    setSyncRunning(true);
    setStepper(IDLE_STEPPER);

    const plan = buildPreviewSyncPlan({
      tenantId: CONNECTOR_TENANT_ID,
      connectorId,
      actorId,
      lease,
      now: new Date(),
      token: safeRandomUuid(),
    });

    try {
      const created = await runStage("create", RUNS_ENDPOINT, plan.create);
      if (!created) {
        return;
      }
      const dispatched = await runStage(
        "dispatch",
        `${RUNS_ENDPOINT}/${encodeURIComponent(plan.runId)}/dispatch`,
        plan.dispatch,
      );
      if (!dispatched) {
        return;
      }
      await runStage(
        "execute",
        `${RUNS_ENDPOINT}/${encodeURIComponent(plan.runId)}/execute-sync`,
        plan.execute,
      );
    } finally {
      setSyncRunning(false);
      triggerRefresh();
    }
  }

  const stages: { key: StageKey; title: string; detail: string }[] = [
    { key: "create", ...copy.sync.stages.create },
    { key: "dispatch", ...copy.sync.stages.dispatch },
    { key: "execute", ...copy.sync.stages.execute },
  ];
  const stepperStarted = stages.some((stage) => stepper[stage.key].status !== "idle");

  return (
    <div className="grid content-start gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <Eyebrow>{copy.title}</Eyebrow>
          <p className="m-0 text-sm text-muted">{copy.detail}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            className="px-4 py-2 text-sm"
            disabled={validating}
            variant="secondary"
            onClick={() => void validate()}
          >
            {validating ? copy.validate.running : copy.validate.action}
          </Button>
          <Button
            className="px-4 py-2 text-sm"
            disabled={syncRunning || syncBlockedReason !== null}
            onClick={() => void runPreviewSync()}
          >
            {syncRunning ? copy.sync.running : copy.sync.action}
          </Button>
        </div>
      </div>

      {syncBlockedReason ? (
        <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
          <ShieldCheck aria-hidden="true" className="shrink-0 text-signal" size={15} />
          {syncBlockedReason}
        </p>
      ) : null}

      {validateOutcome?.kind === "error" ? (
        <ErrorPanel title={copy.validate.error} />
      ) : null}
      {validateOutcome && validateOutcome.kind !== "error" ? (
        <div
          className={cn(
            "grid gap-2 rounded-2xl border p-4",
            validateOutcome.result.preview_status === "ready"
              ? "border-positive/35 bg-positive/8"
              : "border-warning/40 bg-warning/8",
          )}
          role="status"
        >
          <p className="m-0 text-sm font-medium text-ink">
            {validateOutcome.result.preview_status === "ready"
              ? copy.validate.readyTitle
              : copy.validate.blockedTitle}
          </p>
          <p className="m-0 text-sm text-muted">
            {validateOutcome.kind === "csv"
              ? `${validateOutcome.result.record_count} ${copy.validate.rows} / ` +
                `${validateOutcome.result.accepted_record_count} ${copy.validate.accepted} / ` +
                `${validateOutcome.result.rejected_record_count} ${copy.validate.rejected}`
              : `${validateOutcome.result.inspected_table.columns.length} ${copy.validate.columnsChecked} / ` +
                validateOutcome.result.inspected_table.table_ref}
          </p>
          {validateOutcome.result.validation_issues.length > 0 ? (
            <ul className="m-0 grid list-none gap-1 p-0">
              {validateOutcome.result.validation_issues.map((issue) => (
                <li className="text-sm text-muted" key={issue}>
                  {issue}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {stepperStarted ? (
        <ol className="m-0 grid list-none gap-2.5 p-0" aria-label={copy.sync.action}>
          {stages.map((stage) => {
            const state = stepper[stage.key];

            return (
              <Fragment key={stage.key}>
                <li className="flex items-start gap-3 rounded-2xl border border-line p-4 dark:border-white/10">
                  <span className="mt-0.5 shrink-0">
                    <StageIcon status={state.status} />
                  </span>
                  <span className="grid min-w-0 flex-1 gap-0.5">
                    <span className="text-sm font-medium text-ink">{stage.title}</span>
                    <span className="text-xs text-muted">{stage.detail}</span>
                    {state.resultStatus ? (
                      <span className="font-mono text-xs text-muted">
                        {state.resultStatus}
                      </span>
                    ) : null}
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    {state.status === "success" && state.auditEventId ? (
                      <Link
                        className="text-xs font-medium text-signal hover:underline"
                        href={buildAuditEventHref(state.auditEventId)}
                      >
                        {copy.openAudit}
                      </Link>
                    ) : null}
                    <span className="text-xs text-muted">
                      {state.status === "success"
                        ? copy.sync.success
                        : state.status === "failure"
                          ? copy.sync.failure
                          : state.status === "pending"
                            ? copy.sync.running
                            : copy.sync.pending}
                    </span>
                  </span>
                </li>
                {state.status === "failure" && state.errorDetail ? (
                  <li aria-label={`${stage.title} error`} className="list-none">
                    <ErrorPanel detail={state.errorDetail} title={`${stage.title} failed`} />
                  </li>
                ) : null}
              </Fragment>
            );
          })}
        </ol>
      ) : null}

      {runsQuery.source === "loading" ? (
        <LoadingPanel rows={3} />
      ) : runsQuery.source === "unavailable" ? (
        <ErrorPanel title={copy.error} />
      ) : connectorRuns.length === 0 ? (
        <p className="m-0 text-sm text-muted">{copy.empty}</p>
      ) : (
        <DataTable aria-label={copy.title} minWidth={560}>
          <thead>
            <tr>
              <th>{copy.columns.run}</th>
              <th>{copy.columns.status}</th>
              <th>{copy.columns.mode}</th>
              <th>{copy.columns.when}</th>
              <th>{copy.columns.evidence}</th>
            </tr>
          </thead>
          <tbody>
            {connectorRuns.map((run) => (
              <tr key={run.run_id}>
                <td className="font-mono text-xs break-all">{run.run_id}</td>
                <td className="text-xs text-muted">{formatConnectorLabel(run.status)}</td>
                <td className="text-xs text-muted">
                  {formatConnectorLabel(run.execution_mode)}
                </td>
                <td className="font-mono text-xs whitespace-nowrap text-muted">
                  {formatRunTime(run.created_at)}
                </td>
                <td>
                  {run.audit_event_id ? (
                    <Link
                      className="text-xs font-medium text-signal hover:underline"
                      href={buildAuditEventHref(run.audit_event_id)}
                    >
                      {copy.openAudit}
                    </Link>
                  ) : (
                    <span className="text-xs text-muted">{copy.auditPending}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      )}
    </div>
  );
}
