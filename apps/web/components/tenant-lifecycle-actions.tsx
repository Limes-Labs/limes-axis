"use client";

import { useId, useState, type FormEvent } from "react";
import { PauseCircle, PlayCircle } from "lucide-react";

import {
  buildTenantReactivatePayload,
  buildTenantSuspendPayload,
  platformTenantSuspendScope,
  reactivateTenant,
  suspendTenant,
  tenantStatusLabel,
  tenantWriteOperatorError,
  type TenantRecord,
} from "@/lib/platform-tenants";
import { toAxisOperatorError, type AxisOperatorError } from "@/lib/axis-api";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useStrings } from "@/providers/locale-provider";
import { useConsole } from "@/providers/console-provider";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InlineOperatorError } from "@/components/ui/inline-operator-error";

type ActionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "done"; message: string }
  | { phase: "failed"; error: AxisOperatorError };

function forbiddenMessage(message: string, requiredPermission?: string): string {
  return requiredPermission
    ? `${message} Required permission: ${requiredPermission}.`
    : message;
}

export function TenantLifecycleActions({ tenant }: { tenant: TenantRecord }) {
  const strings = useStrings();
  const suspendCopy = useStrings().tenantLifecycle.suspend;
  const suspendImpactId = useId();
  const { session } = useOidcConsoleSession();
  const { triggerRefresh } = useConsole();
  const [reason, setReason] = useState("");
  const [reactivateReason, setReactivateReason] = useState("");
  const [action, setAction] = useState<ActionState>({ phase: "idle" });

  const isActive = tenant.status === "active";
  const isSuspended = tenant.status === "suspended";
  const isTerminal = tenant.status === "pending_deletion";

  async function submitSuspend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedReason = reason.trim();
    if (trimmedReason.length === 0) {
      setAction({
        phase: "failed",
        error: toAxisOperatorError(null, "A suspension reason is required."),
      });
      return;
    }

    setAction({ phase: "saving" });

    try {
      const result = await suspendTenant(
        tenant.tenant_id,
        buildTenantSuspendPayload(trimmedReason),
        { session },
      );

      if (result.kind === "updated") {
        setReason("");
        setAction({
          phase: "done",
          message: `Tenant suspended. It is now rejected fail-closed at the OIDC principal boundary.`,
        });
        triggerRefresh();
        return;
      }

      if (result.kind === "forbidden") {
        setAction({
          phase: "failed",
          error: tenantWriteOperatorError(
            result,
            forbiddenMessage(result.message, result.requiredPermission),
          ),
        });
        return;
      }

      if (result.kind === "conflict") {
        setAction({
          phase: "failed",
          error: tenantWriteOperatorError(result, `${result.message} (${result.reason})`),
        });
        return;
      }

      if (result.kind === "notFound") {
        setAction({ phase: "failed", error: tenantWriteOperatorError(result) });
        return;
      }

      setAction({
        phase: "failed",
        error: tenantWriteOperatorError(
          result,
          result.kind === "failed" ? result.message : "Suspend failed.",
        ),
      });
    } catch (caught) {
      setAction({
        phase: "failed",
        error: toAxisOperatorError(caught, "Tenant lifecycle API is unavailable."),
      });
    }
  }

  async function submitReactivate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setAction({ phase: "saving" });

    try {
      const result = await reactivateTenant(
        tenant.tenant_id,
        buildTenantReactivatePayload(reactivateReason),
        { session },
      );

      if (result.kind === "updated") {
        setReactivateReason("");
        setAction({ phase: "done", message: "Tenant reactivated. Sessions can be established again." });
        triggerRefresh();
        return;
      }

      if (result.kind === "forbidden") {
        setAction({
          phase: "failed",
          error: tenantWriteOperatorError(
            result,
            forbiddenMessage(result.message, result.requiredPermission),
          ),
        });
        return;
      }

      if (result.kind === "conflict") {
        setAction({
          phase: "failed",
          error: tenantWriteOperatorError(result, `${result.message} (${result.reason})`),
        });
        return;
      }

      if (result.kind === "notFound") {
        setAction({ phase: "failed", error: tenantWriteOperatorError(result) });
        return;
      }

      setAction({
        phase: "failed",
        error: tenantWriteOperatorError(
          result,
          result.kind === "failed" ? result.message : "Reactivate failed.",
        ),
      });
    } catch (caught) {
      setAction({
        phase: "failed",
        error: toAxisOperatorError(caught, "Tenant lifecycle API is unavailable."),
      });
    }
  }

  return (
    <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
        <div>
          <p className="eyebrow m-0">{strings.ui.tenantLifecycleActions.lifecycleActions}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">
            {isActive ? suspendCopy.title : isSuspended ? strings.ui.tenantLifecycleActions.reactivateTenant : strings.ui.tenantLifecycleActions.noActionsAvailable}
          </h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            Lifecycle transitions require the {platformTenantSuspendScope} scope and append audit
            evidence. Operators without the scope receive an inline 403.
          </p>
        </div>
        {isActive ? <PauseCircle size={18} /> : <PlayCircle size={18} />}
      </div>

      {isActive ? (
        <form
          aria-label={strings.ui.tenantLifecycleActions.suspendTenant}
          className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
          noValidate
          onSubmit={(event) => void submitSuspend(event)}
        >
          <Field className="col-span-full" label={strings.ui.tenantLifecycleActions.suspensionReason}>
            <Input
              aria-label={strings.ui.tenantLifecycleActions.suspensionReason2}
              onChange={(event) => setReason(event.target.value)}
              placeholder={strings.ui.tenantLifecycleActions.whyThisTenantIsBeing}
              required
              type="text"
              value={reason}
            />
          </Field>
          <div
            className="col-span-full grid gap-1 rounded-xl border border-danger/30 bg-danger/6 p-3 text-sm leading-snug dark:border-danger/40 dark:bg-danger/10"
            id={suspendImpactId}
          >
            <p className="m-0 font-medium text-danger">{suspendCopy.impactTitle}</p>
            <p className="m-0 text-ink break-words">{suspendCopy.impact}</p>
          </div>
          {/* Destructive, not primary: this locks the tenant's users out. */}
          <Button
            aria-describedby={suspendImpactId}
            className="w-fit"
            loading={action.phase === "saving"}
            type="submit"
            variant="destructive"
          >
            {action.phase === "saving" ? null : <PauseCircle aria-hidden="true" size={15} />}
            {action.phase === "saving" ? suspendCopy.saving : suspendCopy.action}
          </Button>
        </form>
      ) : isSuspended ? (
        <form
          aria-label={strings.ui.tenantLifecycleActions.reactivateTenant}
          className="grid grid-cols-1 items-end gap-3 border-t border-line/60 pt-4 dark:border-white/10 sm:grid-cols-[repeat(auto-fit,minmax(150px,1fr))]"
          noValidate
          onSubmit={(event) => void submitReactivate(event)}
        >
          <Field className="col-span-full" label={strings.ui.tenantLifecycleActions.reactivationReasonOptional}>
            <Input
              aria-label={strings.ui.tenantLifecycleActions.reactivationReason}
              onChange={(event) => setReactivateReason(event.target.value)}
              placeholder={strings.ui.tenantLifecycleActions.optionalReasonForReactivating}
              type="text"
              value={reactivateReason}
            />
          </Field>
          <Button
            disabled={action.phase === "saving"}
            type="submit"
          >
            <PlayCircle size={15} />
            {action.phase === "saving" ? strings.ui.tenantLifecycleActions.reactivating : strings.ui.tenantLifecycleActions.reactivateTenant}
          </Button>
        </form>
      ) : (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
          This tenant is {tenantStatusLabel(tenant.status)}. Lifecycle actions are unavailable
          {isTerminal ? "; pending-deletion tenants have no reactivation path in this slice." : "."}
        </p>
      )}

      {action.phase === "failed" ? (
        <InlineOperatorError error={action.error} prefix="Lifecycle action failed" />
      ) : null}
      {action.phase === "done" ? (
        <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" role="status">
          {action.message}
        </p>
      ) : null}
    </section>
  );
}
