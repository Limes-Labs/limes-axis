"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, History, ShieldCheck } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Disclosure } from "@/components/ui/disclosure";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  toAxisOperatorError,
  type AxisOperatorError,
} from "@/lib/axis-api";
import { SourcePill } from "@/components/ui/source-pill";
import { StatCard } from "@/components/ui/stat-card";
import { TenantLifecycleActions } from "@/components/tenant-lifecycle-actions";
import { TenantQuotaEditor } from "@/components/tenant-quota-editor";
import { TenantUsagePanel } from "@/components/tenant-usage-panel";
import { TenantVocabularyEditor } from "@/components/tenant-vocabulary-editor";
import {
  buildPlatformTenantDetailPath,
  fetchTenantDetail,
  tenantStatusClass,
  tenantStatusLabel,
  type TenantRecord,
} from "@/lib/platform-tenants";
import { formatTimestamp } from "@/lib/format";
import { useStrings } from "@/providers/locale-provider";
import { presentText } from "@/lib/display-names";
import { deriveSourceState, PROVENANCE_NOT_APPLICABLE } from "@/lib/source-state";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type DetailSource = "loading" | "api" | "unavailable" | "missing";

type TimelineEntry = {
  key: string;
  label: string;
  timestamp: string | null;
  actor: string | null;
  reason: string | null;
  auditEventId: string | null;
  auditEventSuperseded: boolean;
};

function buildTimeline(tenant: TenantRecord): TimelineEntry[] {
  const entries: TimelineEntry[] = [
    {
      key: "created",
      label: "Provisioned",
      timestamp: tenant.created_at,
      actor: tenant.created_by,
      reason: null,
      // The record only carries the latest audit event id; attribute it to the
      // creation entry only when no later lifecycle change has occurred.
      auditEventId:
        tenant.suspended_at || tenant.reactivated_at ? null : tenant.audit_event_id ?? null,
      auditEventSuperseded: Boolean(tenant.suspended_at || tenant.reactivated_at),
    },
  ];

  if (tenant.suspended_at) {
    entries.push({
      key: "suspended",
      label: "Suspended",
      timestamp: tenant.suspended_at,
      actor: tenant.suspended_by ?? null,
      reason: tenant.suspension_reason ?? null,
      auditEventId: tenant.status === "suspended" ? tenant.audit_event_id ?? null : null,
      auditEventSuperseded: tenant.status !== "suspended",
    });
  }

  if (tenant.reactivated_at) {
    entries.push({
      key: "reactivated",
      label: "Reactivated",
      timestamp: tenant.reactivated_at,
      actor: tenant.reactivated_by ?? null,
      reason: null,
      auditEventId: tenant.status === "active" ? tenant.audit_event_id ?? null : null,
      auditEventSuperseded: tenant.status !== "active",
    });
  }

  return entries;
}

export function TenantDetail({ tenantId }: { tenantId: string }) {
  const strings = useStrings();
  const [tenant, setTenant] = useState<TenantRecord | null>(null);
  const [source, setSource] = useState<DetailSource>("loading");
  const [loadError, setLoadError] = useState<AxisOperatorError | null>(null);
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();

  useEffect(() => {
    const controller = new AbortController();

    async function loadTenant() {
      try {
        const result = await fetchTenantDetail(tenantId, {
          session,
          signal: controller.signal,
        });

        if (controller.signal.aborted) {
          return;
        }

        if (result.kind === "notFound") {
          setTenant(null);
          setLoadError(null);
          setSource("missing");
          return;
        }

        setTenant(result.record);
        setLoadError(null);
        setSource("api");
      } catch (caught) {
        if (!controller.signal.aborted) {
          setTenant(null);
          setLoadError(toAxisOperatorError(
            caught,
            "Axis could not load this platform tenant.",
          ));
          setSource("unavailable");
        }
      }
    }

    void loadTenant();

    return () => controller.abort();
  }, [tenantId, session, refreshNonce]);

  if (!tenant) {
    if (source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    if (source !== "missing") {
      return (
        <ErrorPanel
          detail={strings.ui.tenantDetail.axisDidNotReceiveAn}
          endpoint={buildPlatformTenantDetailPath(tenantId)}
          reference={loadError?.requestId ?? undefined}
          title={strings.ui.common.tenantApiUnavailable}
        />
      );
    }

    return (
      <div className="grid min-w-0 gap-4">
        <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">{strings.ui.tenantDetail.platformTenant}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.tenantDetail.tenantNotFound}</h2>
            <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{tenantId}</p>
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
              {strings.ui.tenantDetail.theTenantReadRouteReturned}
            </p>
          </div>
          <Link className={buttonVariants({ variant: "secondary" })} href="/tenants">
            <ArrowLeft size={17} />
            {strings.ui.common.tenants}
          </Link>
        </section>
      </div>
    );
  }

  const timeline = buildTimeline(tenant);
  const notes = tenant.notes ?? [];

  return (
    <div className="grid min-w-0 gap-4">
      <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">{strings.ui.tenantDetail.platformTenant}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{tenant.display_name}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{tenant.description || strings.ui.tenantDetail.noDescriptionRecorded}</p>
          <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]" title={tenant.tenant_id}>{tenant.tenant_id}</p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2" aria-label={strings.ui.tenantDetail.tenantSourceAndStatus}>
          <SourcePill
            state={deriveSourceState(
              source === "missing" ? "unavailable" : source,
              Boolean(tenant),
              PROVENANCE_NOT_APPLICABLE,
            )}
            subject={strings.sources.subjects.tenant}
          />
          <span className={`status-pill ${tenantStatusClass(tenant.status)}`}>
            <ShieldCheck size={15} />
            {tenantStatusLabel(tenant.status, strings)}
          </span>
          <Link className={buttonVariants({ variant: "secondary" })} href="/tenants">
            <ArrowLeft size={17} />
            {strings.ui.common.tenants}
          </Link>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 [&>*]:min-w-0" role="list">
        <StatCard
          detail={strings.ui.tenantDetail.onlyActiveTenantsCanEstablish}
          label={strings.ui.common.status}
          value={tenantStatusLabel(tenant.status, strings)}
        />
        <StatCard
          detail={formatTimestamp(tenant.created_at)}
          label={strings.ui.tenantDetail.createdBy}
          value={tenant.created_by}
          valueVariant="mono"
        />
        <StatCard
          detail={strings.ui.tenantDetail.optionalActorCreatedAtProvisioning}
          label={strings.ui.tenantDetail.bootstrapAdmin}
          value={presentText(tenant.bootstrap_admin_actor_id) ?? (
            // A missing actor is prose, not an identifier, so it is not set in mono.
            <span className="font-sans" data-bootstrap-admin-missing>{strings.identifiers.notRecorded}</span>
          )}
          valueVariant="mono"
        />
        <StatCard
          detail={<span className="font-mono">{tenant.audit_event_id ?? strings.ui.tenantDetail.noAuditId}</span>}
          label={strings.ui.tenantDetail.lastAuditEvent}
          value={tenant.audit_event_type}
          valueVariant="mono"
        />
      </div>

      <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
          <div>
            <p className="eyebrow m-0">{strings.ui.tenantDetail.lifecycleTimeline}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.tenantDetail.provisioningAndLifecycleTransitions}</h2>
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
              {strings.ui.tenantDetail.everyTransitionRecordsTheOperator}
            </p>
          </div>
          <History size={18} />
        </div>
        <div className="grid min-w-0 gap-2.5">
          {timeline.map((entry) => (
            <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0" key={entry.key}>
              <div>
                <p className="eyebrow m-0">{strings.ui.common.event}</p>
                <p className="m-0 font-medium text-ink break-words">{entry.label}</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                  {formatTimestamp(entry.timestamp)}
                </p>
              </div>
              <div>
                <p className="eyebrow m-0">{strings.ui.common.actor}</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{presentText(entry.actor) ?? strings.ui.tenantDetail.unknownActor}</p>
              </div>
              <div>
                <p className="eyebrow m-0">{strings.ui.tenantDetail.reason}</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{presentText(entry.reason) ?? strings.ui.tenantDetail.noReasonRecorded}</p>
              </div>
              <div>
                <p className="eyebrow m-0">{strings.ui.tenantDetail.auditEventId}</p>
                <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{entry.auditEventId ?? (entry.auditEventSuperseded ? strings.ui.tenantDetail.supersededByLaterEvent : strings.clarity.auditEventIdUnavailable)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <TenantLifecycleActions tenant={tenant} />

      <TenantUsagePanel tenantId={tenant.tenant_id} />

      <TenantQuotaEditor tenantId={tenant.tenant_id} />

      <TenantVocabularyEditor tenantId={tenant.tenant_id} />

      {notes.length > 0 ? (
        <Disclosure title={strings.ui.tenantDetail.tenantNotes}>
          <div className="grid min-w-0 gap-2.5">
            {notes.map((note) => (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={note}>
                {note}
              </p>
            ))}
          </div>
        </Disclosure>
      ) : null}
    </div>
  );
}
