"use client";

import Link from "next/link";
import { useState } from "react";

import {
  PopoverHeader,
  popoverClass,
  popoverLinkClass,
  popoverRowClass,
} from "@/components/topbar/panel-chrome";
import { axisFetchParsedJson } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
import { notificationTone } from "@/lib/identity-format";
import type {
  IdentitySessionReadModel,
  ManufacturingNotificationAcknowledgementResult,
  ManufacturingNotificationCenter,
  ManufacturingPlatformNotification,
} from "@/lib/platform-overview";
import type { useOidcConsoleSession } from "@/lib/use-oidc-session";
import {
  parseManufacturingNotificationAcknowledgementResult,
} from "@/lib/runtime-contracts/overview";

export function NotificationPanel({
  center,
  identitySession,
  onAcknowledged,
  session,
}: {
  center: ManufacturingNotificationCenter | null;
  identitySession: IdentitySessionReadModel | null;
  onAcknowledged: () => void;
  session: ReturnType<typeof useOidcConsoleSession>["session"];
}) {
  const [pendingNotificationId, setPendingNotificationId] = useState<string | null>(null);
  const [acknowledgementError, setAcknowledgementError] = useState<string | null>(null);

  if (!center) {
    return (
      <section className={popoverClass} aria-label="Notifications">
        <PopoverHeader label="Notifications">
          <span className="status-pill signal-action-required">API required</span>
        </PopoverHeader>
        <p className="m-0 text-sm leading-snug text-muted">
          Live notification data requires `/demo/manufacturing/notifications`.
        </p>
      </section>
    );
  }

  const items = center.notifications.slice(0, 5);
  const canAcknowledge = Boolean(
    identitySession?.authenticated
      && identitySession.actor_id
      && identitySession.tenant_id
      && identitySession.scopes.includes("notifications:acknowledge"),
  );
  const sessionRequiredLabel = identitySession?.authenticated
    ? "Your OIDC session needs notifications:acknowledge."
    : "Sign in with SSO to acknowledge notifications.";

  async function acknowledgeNotification(item: ManufacturingPlatformNotification) {
    if (
      !identitySession?.actor_id
      || !identitySession.tenant_id
      || !canAcknowledge
      || item.read_state === "acknowledged"
    ) {
      return;
    }

    setPendingNotificationId(item.notification_id);
    setAcknowledgementError(null);
    try {
      await axisFetchParsedJson<ManufacturingNotificationAcknowledgementResult>(
        `/demo/manufacturing/notifications/${item.notification_id}/acknowledgement`,
        parseManufacturingNotificationAcknowledgementResult,
        {
          method: "POST",
          session,
          body: {
            tenant_id: identitySession.tenant_id,
            actor_id: identitySession.actor_id,
            actor_scopes: identitySession.scopes,
            state: "acknowledged",
            reason: "Acknowledged from the Axis console notification center.",
          },
        },
      );
      onAcknowledged();
    } catch {
      setAcknowledgementError("Axis could not persist the acknowledgement.");
    } finally {
      setPendingNotificationId(null);
    }
  }

  return (
    <section className={popoverClass} aria-label="Notifications">
      <PopoverHeader label="Notifications">
        <span className="status-pill signal-ready">{center.unread_count} live</span>
      </PopoverHeader>
      <div className="grid gap-2">
        {items.length > 0 ? (
          items.map((item) => {
            const acknowledged = item.read_state === "acknowledged";
            const pending = pendingNotificationId === item.notification_id;
            return (
              <div
                aria-label={`${item.action_label}: ${item.title}`}
                className={cn(
                  "notification-row",
                  popoverRowClass,
                  acknowledged && "opacity-70",
                )}
                key={item.notification_id}
              >
                <span
                  aria-hidden="true"
                  className={`status-dot ${notificationTone(item.severity)}`}
                />
                <span className="min-w-0 [&_small]:line-clamp-2 [&_strong]:truncate">
                  <strong>{item.title}</strong>
                  <small>
                    {acknowledged
                      ? item.acknowledgement_reason ?? "Acknowledged"
                      : item.detail}
                  </small>
                </span>
                <span className="col-start-2 mt-2 inline-flex items-center gap-1.5">
                  <Link
                    className="grid h-7 w-[54px] place-items-center rounded-lg border border-line text-[11px] leading-none font-bold whitespace-nowrap text-signal dark:border-white/15"
                    href={item.route}
                    title={item.action_label}
                  >
                    Open
                  </Link>
                  <button
                    className="grid h-7 w-[52px] cursor-pointer place-items-center rounded-lg border border-positive/35 bg-positive/8 text-[11px] leading-none font-bold whitespace-nowrap text-positive disabled:cursor-not-allowed disabled:border-line/60 disabled:bg-ink/3 disabled:text-muted dark:disabled:bg-white/5"
                    disabled={!canAcknowledge || acknowledged || pending}
                    onClick={() => void acknowledgeNotification(item)}
                    type="button"
                  >
                    {acknowledged ? "Acked" : pending ? "Saving" : "Ack"}
                  </button>
                </span>
              </div>
            );
          })
        ) : (
          <div className={popoverRowClass}>
            <span aria-hidden="true" className="status-dot signal-ready" />
            <span>
              <strong>No active notifications</strong>
              <small>Axis did not derive pending alerts from persisted platform state.</small>
            </span>
          </div>
        )}
      </div>
      {items.length > 0 && !canAcknowledge ? (
        <p className="m-0 text-[11px] leading-snug text-muted">{sessionRequiredLabel}</p>
      ) : null}
      {acknowledgementError ? (
        <p className="m-0 text-[11px] leading-snug text-warning" role="status">
          {acknowledgementError}
        </p>
      ) : null}
      <Link className={popoverLinkClass} href="/audit">
        Open audit evidence
      </Link>
    </section>
  );
}
