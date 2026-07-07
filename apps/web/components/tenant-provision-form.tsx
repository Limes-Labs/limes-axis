"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Building2 } from "lucide-react";

import {
  buildTenantProvisionPayload,
  emptyTenantProvisionForm,
  platformTenantProvisionScope,
  provisionTenant,
  tenantIdPattern,
  validateTenantProvisionForm,
  type TenantProvisionFieldErrors,
  type TenantProvisionFormState,
  type TenantRecord,
} from "@/lib/platform-tenants";
import { safeRandomUuid } from "@/lib/ids";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type SubmissionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "created"; record: TenantRecord }
  | { phase: "replayed"; record: TenantRecord }
  | { phase: "conflict"; message: string }
  | { phase: "failed"; message: string };

export function TenantProvisionForm() {
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const [form, setForm] = useState<TenantProvisionFormState>(emptyTenantProvisionForm);
  const [idempotencyKey, setIdempotencyKey] = useState<string>(() => safeRandomUuid());
  const [fieldErrors, setFieldErrors] = useState<TenantProvisionFieldErrors>({});
  const [submission, setSubmission] = useState<SubmissionState>({ phase: "idle" });

  function updateForm(patch: Partial<TenantProvisionFormState>) {
    setForm((current) => ({ ...current, ...patch }));
  }

  async function submitProvision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationErrors = validateTenantProvisionForm(form);
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
      const result = await provisionTenant(
        buildTenantProvisionPayload(form, idempotencyKey),
        { session },
      );

      if (result.kind === "created") {
        setForm(emptyTenantProvisionForm());
        setFieldErrors({});
        setIdempotencyKey(safeRandomUuid());
        setSubmission({ phase: "created", record: result.record });
        triggerRefresh();
        return;
      }

      if (result.kind === "replayed") {
        // The same idempotency key + matching request replays the prior write
        // without creating a duplicate. Keep the form; surface the replay.
        setSubmission({ phase: "replayed", record: result.record });
        triggerRefresh();
        return;
      }

      if (result.kind === "conflict") {
        // A duplicate tenant, or the key was reused with a different request.
        // A fresh key can never resolve a duplicate tenant, but it clears a
        // stale-key replay conflict for the next attempt.
        setIdempotencyKey(safeRandomUuid());
        setFieldErrors(
          result.reason === "tenant_already_exists" ? { tenantId: result.message } : {},
        );
        setSubmission({ phase: "conflict", message: result.message });
        return;
      }

      if (result.kind === "invalid") {
        setFieldErrors(result.fieldErrors as TenantProvisionFieldErrors);
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
        message: result.kind === "failed" ? result.message : "Tenant provisioning failed.",
      });
    } catch {
      setSubmission({ phase: "failed", message: "Tenant provisioning API is unavailable." });
    }
  }

  return (
    <section className="panel">
      <div className="row">
        <div>
          <p className="section-label">Provision Tenant</p>
          <h2 className="panel-title">New tenant</h2>
          <p className="row-detail">
            Creates an active tenant through POST /platform/tenants. The API enforces the{" "}
            {platformTenantProvisionScope} scope and records provisioning audit evidence.
          </p>
          <p className="row-detail mono">Idempotency key {idempotencyKey}</p>
        </div>
        <Building2 size={18} />
      </div>

      <form
        aria-label="Tenant provisioning"
        className="policy-authoring-form"
        noValidate
        onSubmit={(event) => void submitProvision(event)}
      >
        <label>
          <span className="metric-label">Tenant ID</span>
          <input
            aria-label="New tenant id"
            onChange={(event) => updateForm({ tenantId: event.target.value })}
            pattern={tenantIdPattern}
            placeholder="tenant_acme_manufacturing"
            required
            type="text"
            value={form.tenantId}
          />
        </label>
        <label>
          <span className="metric-label">Display Name</span>
          <input
            aria-label="New tenant display name"
            onChange={(event) => updateForm({ displayName: event.target.value })}
            placeholder="Acme Manufacturing"
            required
            type="text"
            value={form.displayName}
          />
        </label>
        <label className="field-wide">
          <span className="metric-label">Description</span>
          <input
            aria-label="New tenant description"
            onChange={(event) => updateForm({ description: event.target.value })}
            placeholder="What this tenant is for (optional)"
            type="text"
            value={form.description}
          />
        </label>
        {fieldErrors.tenantId ? (
          <p className="row-detail field-wide" role="alert">
            {fieldErrors.tenantId}
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

        <label className="toggle-field">
          <input
            aria-label="Bootstrap an admin actor"
            checked={form.bootstrapEnabled}
            onChange={(event) => updateForm({ bootstrapEnabled: event.target.checked })}
            type="checkbox"
          />
          <span className="metric-label">Bootstrap an admin actor for this tenant</span>
        </label>

        {form.bootstrapEnabled ? (
          <>
            <label>
              <span className="metric-label">Bootstrap Admin Actor ID</span>
              <input
                aria-label="Bootstrap admin actor id"
                onChange={(event) => updateForm({ bootstrapActorId: event.target.value })}
                placeholder="acme-admin-role"
                type="text"
                value={form.bootstrapActorId}
              />
            </label>
            <label>
              <span className="metric-label">Bootstrap Admin Display Name</span>
              <input
                aria-label="Bootstrap admin display name"
                onChange={(event) => updateForm({ bootstrapDisplayName: event.target.value })}
                placeholder="Acme Administrator"
                type="text"
                value={form.bootstrapDisplayName}
              />
            </label>
            <label className="field-wide">
              <span className="metric-label">
                Bootstrap Admin Requested Scopes (comma or newline separated)
              </span>
              <textarea
                aria-label="Bootstrap admin requested scopes"
                onChange={(event) => updateForm({ bootstrapScopesText: event.target.value })}
                placeholder="platform:tenant:read"
                rows={2}
                value={form.bootstrapScopesText}
              />
              <span className="row-detail">
                Recorded as audit evidence only. Scope grants stay IdP-owned; the API never
                grants these live.
              </span>
            </label>
            {fieldErrors.bootstrapActorId ? (
              <p className="row-detail field-wide" role="alert">
                {fieldErrors.bootstrapActorId}
              </p>
            ) : null}
            {fieldErrors.bootstrapDisplayName ? (
              <p className="row-detail field-wide" role="alert">
                {fieldErrors.bootstrapDisplayName}
              </p>
            ) : null}
          </>
        ) : null}

        <label className="field-wide">
          <span className="metric-label">Notes (one per line)</span>
          <textarea
            aria-label="New tenant notes"
            onChange={(event) => updateForm({ notesText: event.target.value })}
            placeholder="Optional provisioning notes"
            rows={2}
            value={form.notesText}
          />
        </label>
        <button className="command-button" disabled={submission.phase === "saving"} type="submit">
          <Building2 size={15} />
          {submission.phase === "saving" ? "Provisioning" : "Provision tenant"}
        </button>
      </form>

      {submission.phase === "failed" ? (
        <p className="row-detail" role="alert">
          Tenant provisioning failed: {submission.message}
        </p>
      ) : null}
      {submission.phase === "conflict" ? (
        <p className="row-detail" role="alert">
          Tenant provisioning conflict: {submission.message} A fresh idempotency key was generated
          for the next attempt.
        </p>
      ) : null}
      {submission.phase === "created" ? (
        <p className="row-detail" role="status">
          Tenant provisioned.{" "}
          <Link className="text-link" href={`/tenants/${submission.record.tenant_id}`}>
            Open {submission.record.tenant_id}
          </Link>
        </p>
      ) : null}
      {submission.phase === "replayed" ? (
        <p className="row-detail" role="status">
          Idempotent replay: the API returned the existing tenant for this key without creating a
          duplicate.{" "}
          <Link className="text-link" href={`/tenants/${submission.record.tenant_id}`}>
            Open {submission.record.tenant_id}
          </Link>
        </p>
      ) : null}
    </section>
  );
}
