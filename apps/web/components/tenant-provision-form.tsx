"use client";

import { displayName } from "@/lib/display-names";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Building2 } from "lucide-react";

import {
  buildTenantProvisionPayload,
  emptyTenantProvisionForm,
  platformTenantProvisionScope,
  provisionTenant,
  tenantIdPattern,
  tenantWriteOperatorError,
  validateTenantProvisionForm,
  type TenantProvisionFieldErrors,
  type TenantProvisionFormState,
  type TenantRecord,
} from "@/lib/platform-tenants";
import { toAxisOperatorError, type AxisOperatorError } from "@/lib/axis-api";
import { deriveGovernedActor } from "@/lib/governed-action";
import { safeRandomUuid } from "@/lib/ids";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useIdentitySession } from "@/lib/use-identity-session";
import { useConsole } from "@/providers/console-provider";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { InlineOperatorError } from "@/components/ui/inline-operator-error";
import { useStrings } from "@/providers/locale-provider";

type SubmissionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "created"; record: TenantRecord }
  | { phase: "replayed"; record: TenantRecord }
  | { phase: "conflict"; error: AxisOperatorError }
  | { phase: "failed"; error: AxisOperatorError };

export function TenantProvisionForm() {
  const strings = useStrings();
  const { session } = useOidcConsoleSession();
  const identity = useIdentitySession();
  const { ssoBlocked } = deriveGovernedActor(identity.data ?? null, "platform-tenant-operator");
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

    if (ssoBlocked) {
      return;
    }

    const validationErrors = validateTenantProvisionForm(form);
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
        setSubmission({
          phase: "conflict",
          error: tenantWriteOperatorError(
            result,
            `${result.message} A fresh idempotency key was generated for the next attempt.`,
          ),
        });
        return;
      }

      if (result.kind === "invalid") {
        setFieldErrors(result.fieldErrors as TenantProvisionFieldErrors);
        setSubmission({
          phase: "failed",
          error: tenantWriteOperatorError(result),
        });
        return;
      }

      if (result.kind === "forbidden") {
        setSubmission({
          phase: "failed",
          error: tenantWriteOperatorError(
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
        error: tenantWriteOperatorError(
          result,
          result.kind === "failed" ? result.message : "Tenant provisioning failed.",
        ),
      });
    } catch (caught) {
      setSubmission({
        phase: "failed",
        error: toAxisOperatorError(caught, "Tenant provisioning API is unavailable."),
      });
    }
  }

  return (
    <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">{strings.ui.tenantProvisionForm.provisionTenant}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.tenantProvisionForm.newTenant}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {strings.ui.tenantProvisionForm.createsActiveTenant(platformTenantProvisionScope)}
          </p>
          <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{strings.ui.common.idempotencyKey(idempotencyKey)}</p>
        </div>
        <Building2 size={18} />
      </div>

      <form
        aria-label={strings.ui.tenantProvisionForm.tenantProvisioning}
        className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
        noValidate
        onSubmit={(event) => void submitProvision(event)}
      >
        <Field label={strings.ui.tenantProvisionForm.tenantId}>
          <Input
            aria-label={strings.ui.tenantProvisionForm.newTenantId}
            onChange={(event) => updateForm({ tenantId: event.target.value })}
            pattern={tenantIdPattern}
            placeholder="tenant_acme_manufacturing"
            required
            type="text"
            value={form.tenantId}
          />
        </Field>
        <Field label={strings.ui.common.displayName}>
          <Input
            aria-label={strings.ui.tenantProvisionForm.newTenantDisplayName}
            onChange={(event) => updateForm({ displayName: event.target.value })}
            placeholder={strings.ui.tenantProvisionForm.acmeManufacturing}
            required
            type="text"
            value={form.displayName}
          />
        </Field>
        <Field className="col-span-full" label={strings.ui.common.description}>
          <Input
            aria-label={strings.ui.tenantProvisionForm.newTenantDescription}
            onChange={(event) => updateForm({ description: event.target.value })}
            placeholder={strings.ui.tenantProvisionForm.whatThisTenantIsFor}
            type="text"
            value={form.description}
          />
        </Field>
        {fieldErrors.tenantId ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
            {fieldErrors.tenantId}
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

        <label className="col-span-full flex items-center gap-2.5">
          <Input
            aria-label={strings.ui.tenantProvisionForm.bootstrapAnAdminActor}
            checked={form.bootstrapEnabled}
            onChange={(event) => updateForm({ bootstrapEnabled: event.target.checked })}
            type="checkbox"
          />
          <span className="eyebrow m-0">{strings.ui.tenantProvisionForm.bootstrapAnAdminActorFor}</span>
        </label>

        {form.bootstrapEnabled ? (
          <>
            <Field label={strings.ui.tenantProvisionForm.bootstrapAdminActorId}>
              <Input
                aria-label={strings.ui.tenantProvisionForm.bootstrapAdminActorId2}
                onChange={(event) => updateForm({ bootstrapActorId: event.target.value })}
                placeholder="acme-admin-role"
                type="text"
                value={form.bootstrapActorId}
              />
            </Field>
            <Field label={strings.ui.tenantProvisionForm.bootstrapAdminDisplayName}>
              <Input
                aria-label={strings.ui.tenantProvisionForm.bootstrapAdminDisplayName2}
                onChange={(event) => updateForm({ bootstrapDisplayName: event.target.value })}
                placeholder={strings.ui.tenantProvisionForm.acmeAdministrator}
                type="text"
                value={form.bootstrapDisplayName}
              />
            </Field>
            <Field className="col-span-full" label={strings.ui.tenantProvisionForm.bootstrapAdminRequestedScopesComma}>
              <Textarea
                aria-label={strings.ui.tenantProvisionForm.bootstrapAdminRequestedScopes}
                onChange={(event) => updateForm({ bootstrapScopesText: event.target.value })}
                placeholder="platform:tenant:read"
                rows={2}
                value={form.bootstrapScopesText}
              />
              <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {strings.ui.tenantProvisionForm.recordedAsAuditEvidenceOnly}
              </span>
            </Field>
            {fieldErrors.bootstrapActorId ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
                {fieldErrors.bootstrapActorId}
              </p>
            ) : null}
            {fieldErrors.bootstrapDisplayName ? (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words col-span-full" role="alert">
                {fieldErrors.bootstrapDisplayName}
              </p>
            ) : null}
          </>
        ) : null}

        <Field className="col-span-full" label={strings.ui.common.notesOnePerLine}>
          <Textarea
            aria-label={strings.ui.tenantProvisionForm.newTenantNotes}
            onChange={(event) => updateForm({ notesText: event.target.value })}
            placeholder={strings.ui.tenantProvisionForm.optionalProvisioningNotes}
            rows={2}
            value={form.notesText}
          />
        </Field>
        {ssoBlocked ? (
          <p className="m-0 flex items-center gap-2 text-sm text-muted" role="status">
            <Building2 aria-hidden="true" className="shrink-0 text-signal" size={15} />
            {strings.ui.tenantProvisionForm.signInWithSsoTo}
          </p>
        ) : (
          <Button disabled={submission.phase === "saving"} type="submit">
            <Building2 size={15} />
            {submission.phase === "saving" ? strings.ui.tenantProvisionForm.provisioning : strings.ui.tenantProvisionForm.provisionTenant2}
          </Button>
        )}
      </form>

      {submission.phase === "failed" ? (
        <InlineOperatorError error={submission.error} prefix={strings.ui.tenantProvisionForm.tenantProvisioningFailed} />
      ) : null}
      {submission.phase === "conflict" ? (
        <InlineOperatorError error={submission.error} prefix={strings.ui.tenantProvisionForm.tenantProvisioningConflict} />
      ) : null}
      {submission.phase === "created" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          {strings.ui.tenantProvisionForm.tenantProvisioned}{" "}
          <Link className="inline-flex min-h-6 items-center font-medium text-signal underline decoration-1 underline-offset-2" href={`/tenants/${submission.record.tenant_id}`}>
            {strings.ui.common.openRecord(displayName(submission.record.display_name, submission.record.tenant_id, submission.record.tenant_id))}
          </Link>
        </p>
      ) : null}
      {submission.phase === "replayed" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          {strings.ui.tenantProvisionForm.idempotentReplay}{" "}
          <Link className="inline-flex min-h-6 items-center font-medium text-signal underline decoration-1 underline-offset-2" href={`/tenants/${submission.record.tenant_id}`}>
            {strings.ui.common.openRecord(displayName(submission.record.display_name, submission.record.tenant_id, submission.record.tenant_id))}
          </Link>
        </p>
      ) : null}
    </section>
  );
}
