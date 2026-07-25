"use client";

import { useState, type ChangeEvent } from "react";
import { FileJson, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { ErrorPanel } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { axisFetch, decodeAxisJson } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
import {
  CONNECTOR_CONSOLE_ACTOR,
  CONNECTOR_MANIFEST_BATCH_LIMIT,
  type ConnectorManifestBatchValidationResponse,
  type ConnectorManifestValidationOutcome,
  type ConnectorRegistrationDocument,
} from "@/lib/connectors-console";
import { safeRandomUuid } from "@/lib/ids";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";
import {
  parseConnectorManifestBatchValidationResponse,
  parseConnectorManifestDetail,
} from "@/lib/runtime-contracts/connectors";
import { strings } from "@/lib/strings";
import { buildTenantScopedPath, OPERATIONS_API_PREFIX } from "@/lib/tenant-scope";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

export const MANIFESTS_ENDPOINT = `${OPERATIONS_API_PREFIX}/connectors/manifests`;
export const MANIFEST_VALIDATION_ENDPOINT = `${MANIFESTS_ENDPOINT}/validation`;

type LocalError = "malformed" | "shape" | "file" | null;
type ApplyResult = "landed" | "failed" | "conflict" | "notAttempted" | "pending";

type ApplyState =
  | { phase: "idle" }
  | { phase: "confirming" }
  | { phase: "applying"; results: ApplyResult[] }
  | { phase: "done"; results: ApplyResult[]; landed: number };

function parseDocuments(text: string):
  | { documents: ConnectorRegistrationDocument[] }
  | { error: Exclude<LocalError, "file" | null> } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { error: "malformed" };
  }

  const documents = Array.isArray(parsed) ? parsed : [parsed];
  if (
    documents.length === 0
    || documents.some((document) => (
      typeof document !== "object" || document === null || Array.isArray(document)
    ))
  ) {
    return { error: "shape" };
  }
  return { documents: documents as ConnectorRegistrationDocument[] };
}

function outcomeClass(outcome: ConnectorManifestValidationOutcome): string {
  if (outcome === "would_register") {
    return "signal-ready";
  }
  return outcome === "would_replace" ? "signal-watch" : "signal-action-required";
}

function applyResultClass(result: ApplyResult): string {
  if (result === "landed") {
    return "signal-ready";
  }
  if (result === "failed" || result === "conflict") {
    return "signal-action-required";
  }
  return "status-checking";
}

export function buildManifestDetailPath(connectorId: string, tenantId: string): string {
  return buildTenantScopedPath(
    `${MANIFESTS_ENDPOINT}/${encodeURIComponent(connectorId)}`,
    tenantId,
  );
}

async function isConcurrentChangeResponse(response: Response): Promise<boolean> {
  if (response.status !== 409) {
    return false;
  }
  try {
    const body = await response.json() as { detail?: { reason?: unknown } };
    return body.detail?.reason === "expected_revision_mismatch"
      || body.detail?.reason === "revision_idempotency_conflict";
  } catch {
    return false;
  }
}

export function ManifestImportPanel({
  identitySession,
  onApplied,
  tenantId,
}: {
  identitySession: IdentitySessionReadModel | null;
  onApplied: () => void;
  tenantId: string;
}) {
  const copy = strings.connectors.manifestImport;
  const { push } = useToast();
  const { session } = useOidcConsoleSession();
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [localError, setLocalError] = useState<LocalError>(null);
  const [limitErrorCount, setLimitErrorCount] = useState<number | null>(null);
  const [checking, setChecking] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<ConnectorRegistrationDocument[]>([]);
  const [validation, setValidation] = useState<ConnectorManifestBatchValidationResponse | null>(null);
  const [replacementRevisions, setReplacementRevisions] = useState<Array<number | null>>([]);
  const [applyState, setApplyState] = useState<ApplyState>({ phase: "idle" });

  const ssoBlocked = identitySession != null
    && identitySession.api_auth_required
    && !identitySession.authenticated;
  const invalidCount = validation?.summary.invalid ?? 0;
  const applying = applyState.phase === "applying";
  const canApply = validation !== null
    && invalidCount === 0
    && validation.results.every((result, index) => (
      result.outcome !== "would_replace" || typeof replacementRevisions[index] === "number"
    ))
    && !ssoBlocked
    && applyState.phase === "idle";

  function resetReview(nextText: string) {
    setText(nextText);
    setLocalError(null);
    setLimitErrorCount(null);
    setRequestError(null);
    setDocuments([]);
    setValidation(null);
    setReplacementRevisions([]);
    setApplyState({ phase: "idle" });
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setFileName(file?.name ?? "");
    setLocalError(null);
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resetReview(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => setLocalError("file");
    reader.readAsText(file);
  }

  async function checkDocuments() {
    const parsed = parseDocuments(text);
    if ("error" in parsed) {
      setLocalError(parsed.error);
      setValidation(null);
      return;
    }
    if (parsed.documents.length > CONNECTOR_MANIFEST_BATCH_LIMIT) {
      setLimitErrorCount(parsed.documents.length);
      setValidation(null);
      return;
    }

    setChecking(true);
    setLocalError(null);
    setLimitErrorCount(null);
    setRequestError(null);
    setDocuments([]);
    setValidation(null);
    setReplacementRevisions([]);
    setApplyState({ phase: "idle" });
    let loadingReplacementRevisions = false;
    try {
      const response = await axisFetch(MANIFEST_VALIDATION_ENDPOINT, {
        method: "POST",
        session,
        body: {
          tenant_id: tenantId,
          registered_by: identitySession?.actor_id ?? CONNECTOR_CONSOLE_ACTOR,
          manifests: parsed.documents,
        },
      });
      if (!response.ok) {
        setRequestError(copy.errors.validationRequest);
        return;
      }
      const result = decodeAxisJson(
        MANIFEST_VALIDATION_ENDPOINT,
        await response.json(),
        parseConnectorManifestBatchValidationResponse,
        response.headers.get("x-request-id") ?? response.headers.get("x-correlation-id"),
      );
      if (result.tenant_id !== tenantId) {
        setRequestError(copy.errors.tenantMismatch);
        return;
      }
      if (result.results.length !== parsed.documents.length) {
        setRequestError(copy.errors.resultCountMismatch);
        return;
      }
      loadingReplacementRevisions = true;
      const revisions = await Promise.all(result.results.map(async (validationResult) => {
        if (validationResult.outcome !== "would_replace") {
          return null;
        }
        if (!validationResult.connector_id) {
          throw new Error(copy.errors.replacementRevisionRequest);
        }
        const detailPath = buildManifestDetailPath(validationResult.connector_id, tenantId);
        const detailResponse = await axisFetch(detailPath, { session });
        if (!detailResponse.ok) {
          throw new Error(copy.errors.replacementRevisionRequest);
        }
        const detail = decodeAxisJson(
          detailPath,
          await detailResponse.json(),
          parseConnectorManifestDetail,
          detailResponse.headers.get("x-request-id")
            ?? detailResponse.headers.get("x-correlation-id"),
        );
        if (detail.tenant_id !== tenantId || detail.connector_id !== validationResult.connector_id) {
          throw new Error(copy.errors.replacementRevisionRequest);
        }
        return detail.current_revision.revision_number;
      }));
      setDocuments(parsed.documents);
      setReplacementRevisions(revisions);
      setValidation(result);
    } catch {
      setRequestError(
        loadingReplacementRevisions
          ? copy.errors.replacementRevisionRequest
          : copy.errors.validationRequest,
      );
    } finally {
      setChecking(false);
    }
  }

  async function applyDocuments() {
    if (!validation || invalidCount > 0) {
      return;
    }
    const results: ApplyResult[] = documents.map(() => "pending");
    const applyAttemptId = safeRandomUuid();
    const idempotencyKeys = documents.map((_, index) => (
      `connector-manifest-replace:${applyAttemptId}:${index + 1}`
    ));
    setApplyState({ phase: "applying", results });
    let landed = 0;
    for (let index = 0; index < documents.length; index += 1) {
      try {
        const validationResult = validation.results[index];
        const replacing = validationResult.outcome === "would_replace";
        const connectorId = validationResult.connector_id;
        const path = replacing && connectorId
          ? `${MANIFESTS_ENDPOINT}/${encodeURIComponent(connectorId)}`
          : MANIFESTS_ENDPOINT;
        const response = await axisFetch(path, {
          method: replacing ? "PUT" : "POST",
          session,
          body: {
            ...documents[index],
            tenant_id: tenantId,
            registered_by: identitySession?.actor_id ?? CONNECTOR_CONSOLE_ACTOR,
            ...(replacing ? {
              idempotency_key: idempotencyKeys[index],
              expected_revision_number: replacementRevisions[index],
            } : {}),
          },
        });
        const expectedStatus = replacing ? 200 : 201;
        if (response.status !== expectedStatus) {
          const conflict = await isConcurrentChangeResponse(response);
          results[index] = conflict ? "conflict" : "failed";
          for (let pendingIndex = index + 1; pendingIndex < results.length; pendingIndex += 1) {
            results[pendingIndex] = "notAttempted";
          }
          setApplyState({ phase: "done", results: [...results], landed });
          const detail = conflict && connectorId
            ? copy.concurrentConflict(connectorId)
            : copy.applyFailure(landed, documents.length);
          push({
            title: copy.toast.partial,
            detail,
            tone: "danger",
          });
          if (landed > 0) {
            onApplied();
          }
          return;
        }
      } catch {
        results[index] = "failed";
        for (let pendingIndex = index + 1; pendingIndex < results.length; pendingIndex += 1) {
          results[pendingIndex] = "notAttempted";
        }
        setApplyState({ phase: "done", results: [...results], landed });
        push({
          title: copy.toast.partial,
          detail: copy.applyFailure(landed, documents.length),
          tone: "danger",
        });
        if (landed > 0) {
          onApplied();
        }
        return;
      }
      results[index] = "landed";
      landed += 1;
      setApplyState({ phase: "applying", results: [...results] });
    }
    setApplyState({ phase: "done", results: [...results], landed });
    push({
      title: copy.toast.success,
      detail: copy.applySuccess(landed),
      tone: "positive",
    });
    onApplied();
  }

  const applyResults = applyState.phase === "applying" || applyState.phase === "done"
    ? applyState.results
    : null;
  const applyMessage = applyState.phase === "done"
    ? applyState.results.includes("conflict")
      ? copy.concurrentConflict(
          validation?.results[applyState.results.indexOf("conflict")].connector_id
            ?? copy.table.unknownConnector,
        )
      : applyState.landed === documents.length
      ? copy.applySuccess(applyState.landed)
      : copy.applyFailure(applyState.landed, documents.length)
    : null;

  return (
    <Card className="grid min-w-0 gap-4">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <Eyebrow>{copy.eyebrow}</Eyebrow>
          <h2 className="font-display mx-0 mt-1 mb-1 text-xl text-ink">{copy.title}</h2>
          <p className="m-0 text-sm leading-snug text-muted">{copy.description}</p>
          <p className="mx-0 mt-2 mb-0 text-sm leading-snug text-muted">{copy.access}</p>
          <p className="mx-0 mt-1 mb-0 font-mono text-xs break-words text-muted">
            {copy.validationEndpoint}: {MANIFEST_VALIDATION_ENDPOINT}
          </p>
          <p className="mx-0 mt-1 mb-0 font-mono text-xs break-words text-muted">
            {copy.applyEndpoint}: {copy.applyEndpointPaths(MANIFESTS_ENDPOINT)}
          </p>
        </div>
        <FileJson aria-hidden="true" className="text-muted" size={20} />
      </div>

      <p className="m-0 rounded-xl border border-warning/35 bg-warning/8 p-3 text-sm text-muted">
        {copy.requiredPreview}
      </p>

      <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(220px,0.35fr)]">
        <Field label={copy.inputLabel}>
          <Textarea
            aria-invalid={Boolean(localError || limitErrorCount)}
            className="min-h-40 font-mono text-xs"
            disabled={applying}
            onChange={(event) => resetReview(event.target.value)}
            placeholder={copy.inputPlaceholder}
            value={text}
          />
        </Field>
        <Field label={copy.fileLabel}>
          <Input
            accept=".json,application/json"
            disabled={applying}
            onChange={handleFileChange}
            type="file"
          />
          {fileName ? <span className="font-mono text-xs text-muted">{fileName}</span> : null}
        </Field>
      </div>

      {localError ? (
        <p className="m-0 text-sm text-danger" role="alert">
          {localError === "file" ? copy.fileReadError : copy.errors[localError]}
        </p>
      ) : null}
      {limitErrorCount !== null ? (
        <p className="m-0 text-sm text-danger" role="alert">
          {copy.errors.tooMany(limitErrorCount, CONNECTOR_MANIFEST_BATCH_LIMIT)}
        </p>
      ) : null}
      {ssoBlocked ? (
        <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
          <ShieldCheck aria-hidden="true" className="shrink-0 text-signal" size={15} />
          {copy.ssoGate}
        </p>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        <Button
          disabled={!text.trim() || ssoBlocked || applying}
          loading={checking}
          onClick={() => void checkDocuments()}
          variant="secondary"
        >
          {checking ? copy.checking : copy.check}
        </Button>
        <Button
          disabled={!canApply}
          onClick={() => setApplyState({ phase: "confirming" })}
        >
          {copy.reviewApply}
        </Button>
      </div>

      {requestError ? (
        <ErrorPanel
          detail={requestError}
          endpoint={MANIFEST_VALIDATION_ENDPOINT}
          title={copy.errors.validationRequest}
        />
      ) : null}

      {validation ? (
        <div className="grid gap-4">
          <div aria-label={copy.summary.title} className="grid gap-2 sm:grid-cols-3">
            {([
              ["would_register", copy.summary.wouldRegister],
              ["would_replace", copy.summary.wouldReplace],
              ["invalid", copy.summary.invalid],
            ] as const).map(([outcome, label]) => (
              <div className="rounded-xl border border-line p-3 dark:border-white/10" key={outcome}>
                <p className="m-0 text-xs text-muted">{label}</p>
                <p className="m-0 text-xl font-medium text-ink">{validation.summary[outcome]}</p>
              </div>
            ))}
          </div>

          <DataTable aria-label={copy.title} minWidth={680}>
            <thead>
              <tr>
                <th>{copy.table.document}</th>
                <th>{copy.table.connector}</th>
                <th>{copy.table.outcome}</th>
                {applyResults ? <th>{copy.table.applyResult}</th> : null}
              </tr>
            </thead>
            <tbody>
              {validation.results.map((result, index) => (
                <tr key={index}>
                  <td className="font-mono text-xs">{index + 1}</td>
                  <td className="font-mono text-xs">
                    {result.connector_id ?? copy.table.unknownConnector}
                    {result.errors.length > 0 ? (
                      <ul className="mt-2 mb-0 grid gap-1 pl-4">
                        {result.errors.map((error, errorIndex) => (
                          <li className="text-xs text-danger" key={`${error.field_path}-${errorIndex}`}>
                            <span className="font-mono">{error.field_path}</span>: {error.message}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </td>
                  <td>
                    <span className={cn("status-pill", outcomeClass(result.outcome))}>
                      {copy.outcomes[result.outcome]}
                    </span>
                    {result.outcome === "would_replace" && replacementRevisions[index] ? (
                      <p className="mx-0 mt-1 mb-0 text-xs text-muted">
                        {copy.table.replacesRevision(replacementRevisions[index])}
                      </p>
                    ) : null}
                  </td>
                  {applyResults ? (
                    <td>
                      <span className={cn("status-pill", applyResultClass(applyResults[index]))}>
                        {copy.applyResults[applyResults[index]]}
                      </span>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </DataTable>

          <p
            className={cn("m-0 text-sm", invalidCount > 0 ? "text-danger" : "text-muted")}
            role="status"
          >
            {copy.applyability(invalidCount, documents.length)}
          </p>
          {applyState.phase === "confirming" ? (
            <div className="grid gap-3 rounded-xl border border-warning/40 bg-warning/8 p-4">
              <p className="m-0 text-sm text-muted" role="status">
                {copy.confirmation(documents.length)}
              </p>
              <div className="flex flex-wrap justify-end gap-2">
                <Button onClick={() => setApplyState({ phase: "idle" })} variant="ghost">
                  {copy.cancel}
                </Button>
                <Button onClick={() => void applyDocuments()}>{copy.apply}</Button>
              </div>
            </div>
          ) : null}
          {applyState.phase === "applying" ? (
            <p className="m-0 text-sm text-muted" role="status">{copy.applying}</p>
          ) : null}
          {applyMessage ? (
            <p
              className={cn(
                "m-0 text-sm",
                applyState.phase === "done" && applyState.landed === documents.length
                  ? "text-muted"
                  : "text-danger",
              )}
              role="status"
            >
              {applyMessage}
            </p>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
