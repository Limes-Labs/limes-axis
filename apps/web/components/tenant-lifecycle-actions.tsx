"use client";

import { useState, type FormEvent } from "react";
import { PauseCircle, PlayCircle } from "lucide-react";

import {
  buildTenantReactivatePayload,
  buildTenantSuspendPayload,
  platformTenantSuspendScope,
  reactivateTenant,
  suspendTenant,
  tenantStatusLabel,
  type TenantRecord,
} from "@/lib/platform-tenants";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type ActionState =
  | { phase: "idle" }
  | { phase: "saving" }
  | { phase: "done"; message: string }
  | { phase: "failed"; message: string };

function forbiddenMessage(message: string, requiredPermission?: string): string {
  return requiredPermission
    ? `${message} Required permission: ${requiredPermission}.`
    : message;
}

export function TenantLifecycleActions({ tenant }: { tenant: TenantRecord }) {
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
      setAction({ phase: "failed", message: "A suspension reason is required." });
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
          message: forbiddenMessage(result.message, result.requiredPermission),
        });
        return;
      }

      if (result.kind === "conflict") {
        setAction({ phase: "failed", message: `${result.message} (${result.reason})` });
        return;
      }

      if (result.kind === "notFound") {
        setAction({ phase: "failed", message: result.message });
        return;
      }

      setAction({
        phase: "failed",
        message: result.kind === "failed" ? result.message : "Suspend failed.",
      });
    } catch {
      setAction({ phase: "failed", message: "Tenant lifecycle API is unavailable." });
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
          message: forbiddenMessage(result.message, result.requiredPermission),
        });
        return;
      }

      if (result.kind === "conflict") {
        setAction({ phase: "failed", message: `${result.message} (${result.reason})` });
        return;
      }

      if (result.kind === "notFound") {
        setAction({ phase: "failed", message: result.message });
        return;
      }

      setAction({
        phase: "failed",
        message: result.kind === "failed" ? result.message : "Reactivate failed.",
      });
    } catch {
      setAction({ phase: "failed", message: "Tenant lifecycle API is unavailable." });
    }
  }

  return (
    <section className="panel">
      <div className="row">
        <div>
          <p className="section-label">Lifecycle Actions</p>
          <h2 className="panel-title">
            {isActive ? "Suspend tenant" : isSuspended ? "Reactivate tenant" : "No actions available"}
          </h2>
          <p className="row-detail">
            Lifecycle transitions require the {platformTenantSuspendScope} scope and append audit
            evidence. Operators without the scope receive an inline 403.
          </p>
        </div>
        {isActive ? <PauseCircle size={18} /> : <PlayCircle size={18} />}
      </div>

      {isActive ? (
        <form
          aria-label="Suspend tenant"
          className="policy-authoring-form"
          noValidate
          onSubmit={(event) => void submitSuspend(event)}
        >
          <label className="field-wide">
            <span className="metric-label">Suspension Reason</span>
            <input
              aria-label="Suspension reason"
              onChange={(event) => setReason(event.target.value)}
              placeholder="Why this tenant is being suspended"
              required
              type="text"
              value={reason}
            />
          </label>
          <button
            className="command-button"
            disabled={action.phase === "saving"}
            type="submit"
          >
            <PauseCircle size={15} />
            {action.phase === "saving" ? "Suspending" : "Suspend tenant"}
          </button>
        </form>
      ) : isSuspended ? (
        <form
          aria-label="Reactivate tenant"
          className="policy-authoring-form"
          noValidate
          onSubmit={(event) => void submitReactivate(event)}
        >
          <label className="field-wide">
            <span className="metric-label">Reactivation Reason (optional)</span>
            <input
              aria-label="Reactivation reason"
              onChange={(event) => setReactivateReason(event.target.value)}
              placeholder="Optional reason for reactivating"
              type="text"
              value={reactivateReason}
            />
          </label>
          <button
            className="command-button"
            disabled={action.phase === "saving"}
            type="submit"
          >
            <PlayCircle size={15} />
            {action.phase === "saving" ? "Reactivating" : "Reactivate tenant"}
          </button>
        </form>
      ) : (
        <p className="row-detail">
          This tenant is {tenantStatusLabel(tenant.status)}. Lifecycle actions are unavailable
          {isTerminal ? "; pending-deletion tenants have no reactivation path in this slice." : "."}
        </p>
      )}

      {action.phase === "failed" ? (
        <p className="row-detail" role="alert">
          Lifecycle action failed: {action.message}
        </p>
      ) : null}
      {action.phase === "done" ? (
        <p className="row-detail" role="status">
          {action.message}
        </p>
      ) : null}
    </section>
  );
}
