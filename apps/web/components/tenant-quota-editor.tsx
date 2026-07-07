"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Gauge } from "lucide-react";

import {
  buildPlatformTenantQuotasPath,
  buildTenantQuotaUpdatePayload,
  fetchTenantQuotas,
  platformTenantQuotaScope,
  quotaFormFromQuotaSet,
  tenantQuotaFields,
  updateTenantQuotas,
  validateQuotaForm,
  type TenantQuotaFieldError,
  type TenantQuotaFormState,
  type TenantQuotaSet,
} from "@/lib/platform-tenants";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type QuotaSource = "loading" | "api" | "unavailable" | "missing";

type SaveState =
  | { phase: "idle" }
  | { phase: "confirming" }
  | { phase: "saving" }
  | { phase: "done"; changeCount: number }
  | { phase: "failed"; message: string };

function sourceLabel(source: QuotaSource): string {
  if (source === "api") {
    return "API quota set";
  }

  if (source === "missing") {
    return "Tenant not found";
  }

  return source === "loading" ? "Loading quota API" : "Quota API unavailable";
}

export function TenantQuotaEditor({ tenantId }: { tenantId: string }) {
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();
  const [quotaSet, setQuotaSet] = useState<TenantQuotaSet | null>(null);
  const [source, setSource] = useState<QuotaSource>("loading");
  const [form, setForm] = useState<TenantQuotaFormState>(() => quotaFormFromQuotaSet(null));
  const [fieldErrors, setFieldErrors] = useState<TenantQuotaFieldError>({});
  const [save, setSave] = useState<SaveState>({ phase: "idle" });

  useEffect(() => {
    const controller = new AbortController();

    async function loadQuotas() {
      setSource("loading");

      try {
        const result = await fetchTenantQuotas(tenantId, {
          session,
          signal: controller.signal,
        });

        if (controller.signal.aborted) {
          return;
        }

        if (result === null) {
          setQuotaSet(null);
          setSource("missing");
          return;
        }

        setQuotaSet(result);
        setForm(quotaFormFromQuotaSet(result));
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setQuotaSet(null);
          setSource("unavailable");
        }
      }
    }

    void loadQuotas();

    return () => controller.abort();
  }, [tenantId, session, refreshNonce]);

  function updateField(field: keyof TenantQuotaFormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    if (save.phase === "confirming" || save.phase === "done") {
      setSave({ phase: "idle" });
    }
  }

  function requestConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const errors = validateQuotaForm(form);
    setFieldErrors(errors);

    if (Object.keys(errors).length > 0) {
      setSave({ phase: "failed", message: "Fix the highlighted fields; nothing was sent." });
      return;
    }

    setSave({ phase: "confirming" });
  }

  async function confirmSave() {
    setSave({ phase: "saving" });

    try {
      const result = await updateTenantQuotas(
        tenantId,
        buildTenantQuotaUpdatePayload(form),
        { session },
      );

      if (result.kind === "updated") {
        setFieldErrors({});
        setQuotaSet(result.record);
        setForm(quotaFormFromQuotaSet(result.record));
        setSave({ phase: "done", changeCount: result.record.changes?.length ?? 0 });
        return;
      }

      if (result.kind === "forbidden") {
        setSave({
          phase: "failed",
          message: result.requiredPermission
            ? `${result.message} Required permission: ${result.requiredPermission}.`
            : result.message,
        });
        return;
      }

      if (result.kind === "invalid") {
        setSave({ phase: "failed", message: result.message });
        return;
      }

      if (result.kind === "notFound") {
        setSave({ phase: "failed", message: result.message });
        return;
      }

      setSave({
        phase: "failed",
        message: result.kind === "failed" ? result.message : "Quota update failed.",
      });
    } catch {
      setSave({ phase: "failed", message: "Tenant quota API is unavailable." });
    }
  }

  const quotaNotes = quotaSet?.quota_notes ?? [];

  return (
    <section className="panel">
      <div className="row">
        <div>
          <p className="section-label">Per-Tenant Quotas</p>
          <h2 className="panel-title">Quota overrides</h2>
          <p className="row-detail">
            Reads GET and writes PUT /platform/tenants/{tenantId}/quotas. Requires the{" "}
            {platformTenantQuotaScope} scope. Leaving a field blank clears the override and falls
            back to the global configuration.
          </p>
          <p className="row-detail mono">{buildPlatformTenantQuotasPath(tenantId)}</p>
        </div>
        <Gauge size={18} />
      </div>

      {!quotaSet && source !== "api" ? (
        <p className="row-detail" role="status">
          {sourceLabel(source)}
        </p>
      ) : (
        <form
          aria-label="Tenant quota update"
          className="policy-authoring-form"
          noValidate
          onSubmit={requestConfirmation}
        >
          {tenantQuotaFields.map((descriptor) => (
            <label key={descriptor.field}>
              <span className="metric-label">{descriptor.label}</span>
              <input
                aria-label={descriptor.label}
                inputMode="numeric"
                max={descriptor.max}
                min={descriptor.min}
                onChange={(event) => updateField(descriptor.field, event.target.value)}
                placeholder="Global default"
                type="number"
                value={form[descriptor.field]}
              />
              <span className="row-detail">{descriptor.detail}</span>
              {fieldErrors[descriptor.field] ? (
                <span className="row-detail" role="alert">
                  {fieldErrors[descriptor.field]}
                </span>
              ) : null}
            </label>
          ))}

          {save.phase === "confirming" ? (
            <div className="field-wide stack">
              <p className="row-detail" role="status">
                Confirm the quota update: blank fields clear the override.
              </p>
              <div className="agent-filters">
                <button
                  className="command-button"
                  onClick={() => void confirmSave()}
                  type="button"
                >
                  <Gauge size={15} />
                  Confirm quota update
                </button>
                <button
                  className="icon-button"
                  onClick={() => setSave({ phase: "idle" })}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button className="command-button" disabled={save.phase === "saving"} type="submit">
              <Gauge size={15} />
              {save.phase === "saving" ? "Saving" : "Review quota update"}
            </button>
          )}
        </form>
      )}

      {save.phase === "failed" ? (
        <p className="row-detail" role="alert">
          Quota update failed: {save.message}
        </p>
      ) : null}
      {save.phase === "done" ? (
        <p className="row-detail" role="status">
          Quota update applied with {save.changeCount}{" "}
          {save.changeCount === 1 ? "change" : "changes"}. Unchanged keys write no audit event.
        </p>
      ) : null}

      {quotaNotes.length > 0 ? (
        <div className="stack">
          {quotaNotes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
