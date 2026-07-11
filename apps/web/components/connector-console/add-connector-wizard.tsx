"use client";

import { useMemo, useState, type ChangeEvent } from "react";
import { Database, FileText, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DetailGrid, KeyValueRow } from "@/components/ui/detail-grid";
import { Field, FieldError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { axisFetch } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
import {
  buildExternalDbPreviewRequest,
  buildManifestCreateRequest,
  CONNECTOR_CONSOLE_ACTOR,
  CONNECTOR_TENANT_ID,
  deriveConnectorId,
  parseCsvText,
  type ParsedCsv,
} from "@/lib/connectors-console";
import type {
  ConnectorCsvPreviewResult,
  ConnectorExternalDbPreviewResult,
  ConnectorRegistryItem,
} from "@/lib/connectors-demo";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

/*
 * Add Connector wizard. The Axis preview endpoints validate real content
 * against an existing registry connector's field mapping, so the CSV step
 * pairs the uploaded file with a mapping template from the registry; the
 * manifest that gets registered is the template with the new identity and the
 * file-derived preview sample. Registration never starts a live sync.
 */

type WizardStep = "type" | "source" | "review";
type ConnectorChoice = "file_csv" | "external_db";
type SubmitErrorKind = "conflict" | "forbidden" | "validation" | "generic";

const CSV_PREVIEW_ENDPOINT = "/demo/manufacturing/connectors/file-csv/preview";
const DB_PREVIEW_ENDPOINT = "/demo/manufacturing/connectors/external-db/preview";
const MANIFESTS_ENDPOINT = "/demo/manufacturing/connectors/manifests";

type SubmitError = {
  kind: SubmitErrorKind;
  /** Raw API reason/permission string, rendered as secondary mono text. */
  technicalDetail?: string;
};

type DbForm = {
  connectionProfileId: string;
  schemaName: string;
  tableName: string;
  credentialHandleId: string;
};

const DEFAULT_DB_FORM: DbForm = {
  connectionProfileId: "profile_postgres_ops_readonly",
  schemaName: "operations",
  tableName: "production_orders",
  credentialHandleId: "cred_external_db_readonly",
};

async function readErrorDetail(response: Response): Promise<string | undefined> {
  try {
    const payload = (await response.json()) as {
      detail?: { reason?: string; message?: string; required_permission?: string };
    };
    return (
      payload.detail?.required_permission
      ?? payload.detail?.reason
      ?? payload.detail?.message
    );
  } catch {
    return undefined;
  }
}

function IssueList({ title, issues }: { title: string; issues: string[] }) {
  return (
    <div className="grid gap-1.5 rounded-2xl border border-warning/40 bg-warning/8 p-4">
      <p className="m-0 text-sm font-medium text-ink">{title}</p>
      <ul className="m-0 grid list-none gap-1 p-0">
        {issues.map((issue) => (
          <li className="text-sm text-muted" key={issue}>
            {issue}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AddConnectorWizard({
  connectors,
  open,
  onOpenChange,
  onCreated,
}: {
  connectors: ConnectorRegistryItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const copy = strings.connectors.wizard;
  const { push } = useToast();
  const { session } = useOidcConsoleSession();
  const { data: identitySession } = useAxisQuery<IdentitySessionReadModel>(
    "/identity/session",
  );

  const [step, setStep] = useState<WizardStep>("type");
  const [choice, setChoice] = useState<ConnectorChoice>("file_csv");

  // CSV source state
  const [csvTemplateId, setCsvTemplateId] = useState("");
  const [csvFileName, setCsvFileName] = useState("");
  const [csvText, setCsvText] = useState("");
  const [parsedCsv, setParsedCsv] = useState<ParsedCsv | null>(null);
  const [csvPreview, setCsvPreview] = useState<ConnectorCsvPreviewResult | null>(null);
  const [fileReadError, setFileReadError] = useState(false);

  // External DB source state
  const [dbTemplateId, setDbTemplateId] = useState("");
  const [dbForm, setDbForm] = useState<DbForm>(DEFAULT_DB_FORM);
  const [dbPreview, setDbPreview] = useState<ConnectorExternalDbPreviewResult | null>(null);

  // Shared preview/submit lifecycle
  const [previewing, setPreviewing] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);

  // Review state
  const [connectorId, setConnectorId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<SubmitError | null>(null);

  const csvTemplates = useMemo(
    () => connectors.filter((connector) => connector.manifest.connector_type === "file_csv"),
    [connectors],
  );
  const dbTemplates = useMemo(
    () => connectors.filter((connector) => connector.manifest.connector_type === "external_db"),
    [connectors],
  );

  const templates = choice === "file_csv" ? csvTemplates : dbTemplates;
  const selectedTemplateId = choice === "file_csv" ? csvTemplateId : dbTemplateId;
  const template =
    templates.find((item) => item.manifest.connector_id === selectedTemplateId)
    ?? templates[0]
    ?? null;

  // Submission is gated only when the API confirms it enforces OIDC and the
  // browser session is unauthenticated; in public-evaluation deployments
  // (api_auth_required=false) unauthenticated demo writes are accepted.
  const ssoBlocked = identitySession != null
    && identitySession.api_auth_required
    && !identitySession.authenticated;

  const sourceReady =
    choice === "file_csv"
      ? csvPreview?.preview_status === "ready" && parsedCsv !== null
      : dbPreview?.preview_status === "ready";

  function resetAll() {
    setStep("type");
    setChoice("file_csv");
    setCsvTemplateId("");
    setCsvFileName("");
    setCsvText("");
    setParsedCsv(null);
    setCsvPreview(null);
    setFileReadError(false);
    setDbTemplateId("");
    setDbForm(DEFAULT_DB_FORM);
    setDbPreview(null);
    setPreviewing(false);
    setPreviewFailed(false);
    setConnectorId("");
    setDisplayName("");
    setSubmitting(false);
    setSubmitError(null);
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetAll();
    }
    onOpenChange(nextOpen);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setCsvPreview(null);
    setPreviewFailed(false);
    setFileReadError(false);
    if (!file) {
      setCsvFileName("");
      setCsvText("");
      setParsedCsv(null);
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setCsvFileName(file.name);
      setCsvText(text);
      setParsedCsv(parseCsvText(text));
    };
    reader.onerror = () => {
      setFileReadError(true);
    };
    reader.readAsText(file);
  }

  async function previewCsv() {
    if (!template || !csvText) {
      return;
    }
    setPreviewing(true);
    setPreviewFailed(false);
    try {
      const response = await axisFetch(CSV_PREVIEW_ENDPOINT, {
        method: "POST",
        session,
        body: {
          tenant_id: CONNECTOR_TENANT_ID,
          connector_id: template.manifest.connector_id,
          file_name: csvFileName,
          csv_content: csvText,
        },
      });
      if (!response.ok) {
        setPreviewFailed(true);
        return;
      }
      setCsvPreview((await response.json()) as ConnectorCsvPreviewResult);
    } catch {
      setPreviewFailed(true);
    } finally {
      setPreviewing(false);
    }
  }

  async function previewDb() {
    if (!template) {
      return;
    }
    setPreviewing(true);
    setPreviewFailed(false);
    try {
      const response = await axisFetch(DB_PREVIEW_ENDPOINT, {
        method: "POST",
        session,
        body: buildExternalDbPreviewRequest({
          tenantId: CONNECTOR_TENANT_ID,
          connectorId: template.manifest.connector_id,
          connectionProfileId: dbForm.connectionProfileId,
          schemaName: dbForm.schemaName,
          tableName: dbForm.tableName,
          credentialHandleId: dbForm.credentialHandleId,
          template,
        }),
      });
      if (!response.ok) {
        setPreviewFailed(true);
        return;
      }
      setDbPreview((await response.json()) as ConnectorExternalDbPreviewResult);
    } catch {
      setPreviewFailed(true);
    } finally {
      setPreviewing(false);
    }
  }

  function advanceToReview() {
    if (choice === "file_csv") {
      setConnectorId(deriveConnectorId(csvFileName, "file_csv"));
      setDisplayName(csvFileName.replace(/\.[^.]+$/, "") || "New CSV connector");
    } else {
      setConnectorId(
        deriveConnectorId(`${dbForm.schemaName}_${dbForm.tableName}`, "external_db"),
      );
      setDisplayName(`${dbForm.schemaName}.${dbForm.tableName} mirror`);
    }
    setSubmitError(null);
    setStep("review");
  }

  async function submitManifest() {
    if (!template) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);

    const previewSample =
      choice === "file_csv" && parsedCsv
        ? {
            file_name: csvFileName,
            record_count: parsedCsv.rows.length,
            headers: parsedCsv.headers,
            sample_rows: parsedCsv.rows.slice(0, 5),
          }
        : {
            ...template.preview_sample,
            file_name: `${dbForm.schemaName}.${dbForm.tableName}`,
          };

    try {
      const response = await axisFetch(MANIFESTS_ENDPOINT, {
        method: "POST",
        session,
        body: buildManifestCreateRequest({
          tenantId: CONNECTOR_TENANT_ID,
          registeredBy: identitySession?.actor_id ?? CONNECTOR_CONSOLE_ACTOR,
          template,
          connectorId: connectorId.trim(),
          displayName: displayName.trim(),
          previewSample: previewSample,
        }),
      });

      if (response.status === 201) {
        push({
          title: copy.reviewStep.toastTitle,
          detail: copy.reviewStep.toastDetail,
          tone: "positive",
        });
        handleOpenChange(false);
        onCreated();
        return;
      }
      if (response.status === 409) {
        setSubmitError({ kind: "conflict" });
        return;
      }
      if (response.status === 403) {
        setSubmitError({
          kind: "forbidden",
          technicalDetail: await readErrorDetail(response),
        });
        return;
      }
      if (response.status === 422) {
        setSubmitError({
          kind: "validation",
          technicalDetail: await readErrorDetail(response),
        });
        return;
      }
      setSubmitError({ kind: "generic" });
    } catch {
      setSubmitError({ kind: "generic" });
    } finally {
      setSubmitting(false);
    }
  }

  const submitErrorLabel: Record<SubmitErrorKind, string> = {
    conflict: copy.reviewStep.conflict,
    forbidden: copy.reviewStep.forbidden,
    validation: copy.reviewStep.validationFailed,
    generic: copy.reviewStep.genericError,
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent aria-describedby={undefined} className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>

        {step === "type" ? (
          <div className="grid gap-3">
            <p className="m-0 text-sm font-medium text-ink">{copy.typeStep.title}</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {(
                [
                  {
                    value: "file_csv" as const,
                    icon: FileText,
                    title: copy.typeStep.csvTitle,
                    detail: copy.typeStep.csvDetail,
                  },
                  {
                    value: "external_db" as const,
                    icon: Database,
                    title: copy.typeStep.dbTitle,
                    detail: copy.typeStep.dbDetail,
                  },
                ]
              ).map((option) => (
                <button
                  aria-pressed={choice === option.value}
                  className={cn(
                    "grid cursor-pointer content-start gap-1.5 rounded-2xl border bg-surface p-4 text-left transition-colors dark:bg-transparent",
                    choice === option.value
                      ? "border-signal/60 bg-tint-50 dark:bg-signal/10"
                      : "border-line hover:border-signal/40 dark:border-white/15",
                  )}
                  key={option.value}
                  onClick={() => setChoice(option.value)}
                  type="button"
                >
                  <span className="flex items-center gap-2 text-sm font-medium text-ink">
                    <option.icon aria-hidden="true" size={16} />
                    {option.title}
                  </span>
                  <span className="text-xs leading-snug text-muted">{option.detail}</span>
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === "source" && choice === "file_csv" ? (
          <div className="grid gap-3.5">
            {csvTemplates.length === 0 ? (
              <FieldError>{copy.csvStep.noTemplates}</FieldError>
            ) : (
              <>
                <Field label={copy.csvStep.template}>
                  <Select
                    onChange={(event) => {
                      setCsvTemplateId(event.target.value);
                      setCsvPreview(null);
                    }}
                    value={template?.manifest.connector_id ?? ""}
                  >
                    {csvTemplates.map((item) => (
                      <option
                        key={item.manifest.connector_id}
                        value={item.manifest.connector_id}
                      >
                        {item.manifest.display_name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <p className="m-0 text-xs text-muted">{copy.csvStep.templateDetail}</p>
                <Field label={copy.csvStep.file}>
                  <Input accept=".csv,text/csv" onChange={handleFileChange} type="file" />
                </Field>
                {fileReadError ? <FieldError>{copy.csvStep.fileReadError}</FieldError> : null}
                <div>
                  <Button
                    className="px-4 py-2 text-sm"
                    disabled={!csvText || previewing}
                    variant="secondary"
                    onClick={() => void previewCsv()}
                  >
                    {previewing ? copy.csvStep.previewing : copy.csvStep.preview}
                  </Button>
                </div>
                {previewFailed ? <FieldError>{copy.csvStep.previewError}</FieldError> : null}
                {csvPreview ? (
                  <div className="grid gap-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          "status-pill",
                          csvPreview.preview_status === "ready"
                            ? "signal-ready"
                            : "signal-action-required",
                        )}
                      >
                        {csvPreview.preview_status === "ready"
                          ? copy.csvStep.readyTitle
                          : copy.csvStep.blockedTitle}
                      </span>
                      <span className="text-sm text-muted">
                        {csvPreview.record_count} {copy.csvStep.rows} /{" "}
                        {csvPreview.accepted_record_count} {copy.csvStep.accepted} /{" "}
                        {csvPreview.rejected_record_count} {copy.csvStep.rejected}
                      </span>
                    </div>
                    {csvPreview.validation_issues.length > 0 ? (
                      <IssueList
                        issues={csvPreview.validation_issues}
                        title={copy.csvStep.issuesTitle}
                      />
                    ) : null}
                    {csvPreview.proposed_entities.length > 0 ? (
                      <DataTable
                        aria-label={copy.csvStep.entitiesTitle}
                        minWidth={360}
                      >
                        <thead>
                          <tr>
                            <th>Node</th>
                            <th>Type</th>
                            <th>Ontology target</th>
                          </tr>
                        </thead>
                        <tbody>
                          {csvPreview.proposed_entities.slice(0, 5).map((entity) => (
                            <tr key={entity.node_id}>
                              <td className="font-mono text-xs">{entity.node_id}</td>
                              <td className="text-xs text-muted">{entity.node_type}</td>
                              <td className="font-mono text-xs">{entity.ontology_type}</td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    ) : null}
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : null}

        {step === "source" && choice === "external_db" ? (
          <div className="grid gap-3.5">
            {dbTemplates.length === 0 ? (
              <FieldError>{copy.dbStep.noTemplates}</FieldError>
            ) : (
              <>
                <Field label={copy.dbStep.template}>
                  <Select
                    onChange={(event) => {
                      setDbTemplateId(event.target.value);
                      setDbPreview(null);
                    }}
                    value={template?.manifest.connector_id ?? ""}
                  >
                    {dbTemplates.map((item) => (
                      <option
                        key={item.manifest.connector_id}
                        value={item.manifest.connector_id}
                      >
                        {item.manifest.display_name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label={copy.dbStep.profile}>
                    <Input
                      onChange={(event) =>
                        setDbForm((current) => ({
                          ...current,
                          connectionProfileId: event.target.value,
                        }))
                      }
                      value={dbForm.connectionProfileId}
                    />
                  </Field>
                  <Field label={copy.dbStep.credentialHandle}>
                    <Input
                      onChange={(event) =>
                        setDbForm((current) => ({
                          ...current,
                          credentialHandleId: event.target.value,
                        }))
                      }
                      value={dbForm.credentialHandleId}
                    />
                  </Field>
                  <Field label={copy.dbStep.schema}>
                    <Input
                      onChange={(event) =>
                        setDbForm((current) => ({ ...current, schemaName: event.target.value }))
                      }
                      value={dbForm.schemaName}
                    />
                  </Field>
                  <Field label={copy.dbStep.table}>
                    <Input
                      onChange={(event) =>
                        setDbForm((current) => ({ ...current, tableName: event.target.value }))
                      }
                      value={dbForm.tableName}
                    />
                  </Field>
                </div>
                <p className="m-0 text-xs text-muted">{copy.dbStep.profileDetail}</p>
                <div>
                  <Button
                    className="px-4 py-2 text-sm"
                    disabled={previewing}
                    variant="secondary"
                    onClick={() => void previewDb()}
                  >
                    {previewing ? copy.dbStep.previewing : copy.dbStep.preview}
                  </Button>
                </div>
                {previewFailed ? <FieldError>{copy.dbStep.previewError}</FieldError> : null}
                {dbPreview ? (
                  <div className="grid gap-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          "status-pill",
                          dbPreview.preview_status === "ready"
                            ? "signal-ready"
                            : "signal-action-required",
                        )}
                      >
                        {dbPreview.preview_status === "ready"
                          ? copy.dbStep.readyTitle
                          : copy.dbStep.blockedTitle}
                      </span>
                      <span className="font-mono text-xs text-muted">
                        {dbPreview.inspected_table.table_ref}
                      </span>
                    </div>
                    {dbPreview.validation_issues.length > 0 ? (
                      <IssueList
                        issues={dbPreview.validation_issues}
                        title={copy.csvStep.issuesTitle}
                      />
                    ) : null}
                    {dbPreview.inspected_table.columns.length > 0 ? (
                      <DataTable aria-label={copy.dbStep.columnsTitle} minWidth={360}>
                        <thead>
                          <tr>
                            <th>Column</th>
                            <th>Target</th>
                            <th>Ontology target</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dbPreview.inspected_table.columns.map((column) => (
                            <tr key={column.source_column}>
                              <td className="font-mono text-xs">{column.source_column}</td>
                              <td className="font-mono text-xs">{column.target_field}</td>
                              <td className="font-mono text-xs">{column.ontology_target}</td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    ) : null}
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : null}

        {step === "review" && template ? (
          <div className="grid gap-3.5">
            <p className="m-0 text-sm font-medium text-ink">{copy.reviewStep.title}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={copy.reviewStep.connectorId}>
                <Input
                  className="font-mono text-xs"
                  onChange={(event) => setConnectorId(event.target.value)}
                  value={connectorId}
                />
              </Field>
              <Field label={copy.reviewStep.displayName}>
                <Input
                  onChange={(event) => setDisplayName(event.target.value)}
                  value={displayName}
                />
              </Field>
            </div>
            <DetailGrid>
              <KeyValueRow label={copy.reviewStep.type}>
                {choice === "file_csv"
                  ? copy.typeStep.csvTitle
                  : copy.typeStep.dbTitle}
              </KeyValueRow>
              <KeyValueRow label={copy.reviewStep.records}>
                {choice === "file_csv"
                  ? `${parsedCsv?.rows.length ?? 0} rows from ${csvFileName}`
                  : `${dbForm.schemaName}.${dbForm.tableName} metadata`}
              </KeyValueRow>
            </DetailGrid>

            {ssoBlocked ? (
              <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
                <ShieldCheck aria-hidden="true" className="shrink-0 text-signal" size={15} />
                {copy.ssoGate}
              </p>
            ) : null}
            {submitError ? (
              <div className="grid gap-1">
                <FieldError>{submitErrorLabel[submitError.kind]}</FieldError>
                {submitError.technicalDetail ? (
                  <p className="m-0 font-mono text-xs break-words text-muted">
                    {submitError.technicalDetail}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        <DialogFooter>
          {step !== "type" ? (
            <Button
              className="px-4 py-2 text-sm"
              variant="ghost"
              onClick={() => setStep(step === "review" ? "source" : "type")}
            >
              {copy.back}
            </Button>
          ) : null}
          <Button
            className="px-4 py-2 text-sm"
            variant="secondary"
            onClick={() => handleOpenChange(false)}
          >
            {copy.cancel}
          </Button>
          {step === "type" ? (
            <Button className="px-4 py-2 text-sm" onClick={() => setStep("source")}>
              {copy.next}
            </Button>
          ) : null}
          {step === "source" ? (
            <Button
              className="px-4 py-2 text-sm"
              disabled={!sourceReady}
              onClick={advanceToReview}
            >
              {copy.next}
            </Button>
          ) : null}
          {step === "review" ? (
            <Button
              className="px-4 py-2 text-sm"
              disabled={
                submitting || ssoBlocked || connectorId.trim() === "" || displayName.trim() === ""
              }
              onClick={() => void submitManifest()}
            >
              {submitting ? copy.submitting : copy.submit}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
