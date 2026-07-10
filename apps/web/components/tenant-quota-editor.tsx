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
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

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
    <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">Per-Tenant Quotas</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Quota overrides</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            Reads GET and writes PUT /platform/tenants/{tenantId}/quotas. Requires the{" "}
            {platformTenantQuotaScope} scope. Leaving a field blank clears the override and falls
            back to the global configuration.
          </p>
          <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{buildPlatformTenantQuotasPath(tenantId)}</p>
        </div>
        <Gauge size={18} />
      </div>

      {!quotaSet && source !== "api" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          {sourceLabel(source)}
        </p>
      ) : (
        <form
          aria-label="Tenant quota update"
          className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
          noValidate
          onSubmit={requestConfirmation}
        >
          {tenantQuotaFields.map((descriptor) => (
            <Field key={descriptor.field} label={descriptor.label}>
              <Input
                aria-label={descriptor.label}
                inputMode="numeric"
                max={descriptor.max}
                min={descriptor.min}
                onChange={(event) => updateField(descriptor.field, event.target.value)}
                placeholder="Global default"
                type="number"
                value={form[descriptor.field]}
              />
              <span className="m-0 text-xs leading-snug text-muted break-words">{descriptor.detail}</span>
              {fieldErrors[descriptor.field] ? (
                <span className="m-0 text-sm leading-snug text-danger break-words" role="alert">
                  {fieldErrors[descriptor.field]}
                </span>
              ) : null}
            </Field>
          ))}

          {save.phase === "confirming" ? (
            <div className="col-span-full grid min-w-0 gap-2.5">
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
                Confirm the quota update: blank fields clear the override.
              </p>
              <div className="grid w-full min-w-0 gap-2.5 sm:flex sm:w-auto sm:flex-wrap sm:items-end sm:justify-end">
                <button
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-mist bg-surface px-4 py-2 text-sm font-medium text-ink transition-all duration-300 select-none hover:border-signal/50 hover:text-signal disabled:cursor-not-allowed disabled:opacity-55 dark:border-white/20 dark:hover:border-signal/60"
                  onClick={() => void confirmSave()}
                  type="button"
                >
                  <Gauge size={15} />
                  Confirm quota update
                </button>
                <button
                  className="inline-flex items-center justify-center rounded-full px-3 py-2 text-sm font-medium text-ink transition-all duration-300 select-none hover:text-signal"
                  onClick={() => setSave({ phase: "idle" })}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-4 py-2 text-sm font-medium text-white transition-all duration-300 select-none hover:bg-signal hover:shadow-[0_8px_24px_rgb(47_100_255/0.35)] disabled:cursor-not-allowed disabled:opacity-55 dark:bg-signal dark:hover:bg-white dark:hover:text-navy dark:hover:shadow-none" disabled={save.phase === "saving"} type="submit">
              <Gauge size={15} />
              {save.phase === "saving" ? "Saving" : "Review quota update"}
            </button>
          )}
        </form>
      )}

      {save.phase === "failed" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-danger break-words" role="alert">
          Quota update failed: {save.message}
        </p>
      ) : null}
      {save.phase === "done" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          Quota update applied with {save.changeCount}{" "}
          {save.changeCount === 1 ? "change" : "changes"}. Unchanged keys write no audit event.
        </p>
      ) : null}

      {quotaNotes.length > 0 ? (
        <div className="grid min-w-0 gap-2.5">
          {quotaNotes.map((note) => (
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={note}>
              {note}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
