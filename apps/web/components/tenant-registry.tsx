"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Building2, RotateCcw, ShieldCheck } from "lucide-react";

import { useStrings } from "@/providers/locale-provider";
import { dataTableClassName } from "@/components/ui/data-table";
import { cn } from "@/lib/cn";
import { Disclosure } from "@/components/ui/disclosure";
import { TenantProvisionForm } from "@/components/tenant-provision-form";
import {
  toAxisOperatorError,
  type AxisOperatorError,
} from "@/lib/axis-api";
import { enumUrlField, useConsoleUrlState } from "@/lib/console-url-state";
import {
  allTenantFilter,
  fetchTenantRegistry,
  mergeTenantRegistryPage,
  platformTenantsPath,
  tenantLifecycleStatuses,
  tenantStatusClass,
  tenantStatusLabel,
  type TenantLifecycleStatus,
  type TenantRegistry as TenantRegistryData,
  type TenantRegistryFilters,
} from "@/lib/platform-tenants";
import { formatNumber, formatTimestamp } from "@/lib/format";
import {
  deriveSourceState,
  PROVENANCE_NOT_APPLICABLE,
  type AxisSource,
} from "@/lib/source-state";
import { useConsole } from "@/providers/console-provider";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { SourcePill } from "@/components/ui/source-pill";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";

const defaultFilters: TenantRegistryFilters = {
  status: allTenantFilter,
};
const tenantUrlSchema = {
  status: enumUrlField(
    "status",
    [allTenantFilter, ...tenantLifecycleStatuses],
    allTenantFilter,
  ),
};

function isTenantLifecycleStatus(value: string): value is TenantLifecycleStatus {
  return tenantLifecycleStatuses.some((status) => status === value);
}

/**
 * Cursor-paginated tenant registry read. The first page loads on mount and on
 * filter / console-refresh change; loadMore follows next_cursor and appends the
 * next page, so the console can page past the per-request server maximum.
 */
function useTenantRegistryPages(filters: TenantRegistryFilters) {
  const { refreshNonce } = useConsole();
  const { session } = useOidcConsoleSession();
  const [registry, setRegistry] = useState<TenantRegistryData | null>(null);
  const [source, setSource] = useState<AxisSource>("loading");
  const [loadError, setLoadError] = useState<AxisOperatorError | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<AxisOperatorError | null>(null);
  // Generation guard: bumped every time the base page reloads (filter,
  // session or console-refresh change). A "load more" page fetch started
  // under an earlier generation is discarded on arrival instead of merging a
  // stale filter's tenants into the current list and corrupting the counts
  // and next_cursor.
  const generationRef = useRef(0);
  const loadMoreControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    generationRef.current += 1;
    // A new base load supersedes any in-flight "load more" page fetch.
    loadMoreControllerRef.current?.abort();
    loadMoreControllerRef.current = null;
    const generation = generationRef.current;

    const controller = new AbortController();

    async function load() {
      // Stale-while-revalidate: keep the previously loaded registry mounted
      // during a reload (filter change or console refresh) so sibling surfaces
      // — notably the provision form and its success confirmation — are not
      // torn down by the `!registry` guard. The registry is only null on the
      // very first load, or when a load genuinely fails with nothing cached.
      setSource("loading");

      try {
        const page = await fetchTenantRegistry(filters, {
          session,
          signal: controller.signal,
        });

        if (!controller.signal.aborted && generationRef.current === generation) {
          setRegistry(page);
          setLoadError(null);
          setSource("api");
        }
      } catch (caught) {
        if (!controller.signal.aborted && generationRef.current === generation) {
          // Preserve any already-loaded registry on a refetch failure; only a
          // first load (registry still null) falls through to the unavailable
          // state. Surface the unavailable source either way.
          setLoadError(toAxisOperatorError(
            caught,
            "Axis could not load platform tenant records.",
          ));
          setSource("unavailable");
        }
      }
    }

    void load();

    return () => controller.abort();
    // filters is recreated each render; reload only when its status changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.status, session, refreshNonce]);

  const loadMore = useCallback(async () => {
    if (!registry?.has_more || !registry.next_cursor || loadingMore) {
      return;
    }

    const generation = generationRef.current;
    const controller = new AbortController();
    loadMoreControllerRef.current = controller;
    setLoadingMore(true);
    setLoadMoreError(null);

    try {
      const page = await fetchTenantRegistry(
        filters,
        { session, signal: controller.signal },
        registry.next_cursor,
      );

      // A filter change (or console refresh) mid-flight bumps the
      // generation; discard this page rather than merging it into the new
      // base query's list.
      if (!controller.signal.aborted && generationRef.current === generation) {
        setRegistry((current) => mergeTenantRegistryPage(current, page));
      }
    } catch (caught) {
      if (!controller.signal.aborted && generationRef.current === generation) {
        setLoadMoreError(toAxisOperatorError(
          caught,
          "Axis could not load the next page of tenants.",
        ));
      }
    } finally {
      if (loadMoreControllerRef.current === controller) {
        loadMoreControllerRef.current = null;
      }
      if (!controller.signal.aborted && generationRef.current === generation) {
        setLoadingMore(false);
      }
    }
  }, [registry, filters, session, loadingMore]);

  return { registry, source, loadError, loadMore, loadingMore, loadMoreError };
}

export function TenantRegistry() {
  const strings = useStrings();
  const [filters, setFilters] = useConsoleUrlState(tenantUrlSchema);
  const { registry, source, loadError, loadMore, loadingMore, loadMoreError } =
    useTenantRegistryPages(filters);

  function updateStatus(value: string) {
    if (
      value === allTenantFilter
      || isTenantLifecycleStatus(value)
    ) {
      setFilters({ status: value });
    }
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  if (!registry) {
    if (source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    return (
      <ErrorPanel
        detail={strings.ui.tenantRegistry.axisDidNotReceiveApi}
        endpoint={platformTenantsPath}
        reference={loadError?.requestId ?? undefined}
        title={strings.ui.common.tenantApiUnavailable}
      />
    );
  }

  const tenants = registry.tenants ?? [];
  const tenantNotes = registry.tenant_notes ?? [];
  const hasMore = registry.has_more ?? false;
  const suspendedCount = tenants.filter((tenant) => tenant.status === "suspended").length;
  const pendingDeletionCount = tenants.filter(
    (tenant) => tenant.status === "pending_deletion",
  ).length;

  return (
    <div className="grid min-w-0 gap-4">
      <div
        aria-label={strings.ui.tenantRegistry.tenantSourceAndRegistryStatus}
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm leading-snug break-words text-muted">
          {strings.ui.tenantRegistry.crossTenantOperatorSurfaceEvery}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <SourcePill
            state={deriveSourceState(source, Boolean(registry), PROVENANCE_NOT_APPLICABLE)}
            subject="tenant registry"
          />
          <span className="status-pill signal-watch">
            <ShieldCheck size={15} />
            {formatNumber(registry.active_tenant_count)} active
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3.5 xl:grid-cols-4 [&>*]:min-w-0">
        <article className="min-w-0 rounded-2xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">{strings.ui.common.tenants}</p>
          <p className="font-display mx-0 mt-3 mb-1.5 text-2xl tabular-nums break-words text-ink">{formatNumber(registry.tenant_count)}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">{strings.ui.tenantRegistry.tenantsMatchingTheCurrentStatus}</p>
        </article>
        <article className="min-w-0 rounded-2xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">{strings.ui.tenantRegistry.active}</p>
          <p className="font-display mx-0 mt-3 mb-1.5 text-2xl tabular-nums break-words text-ink">{formatNumber(registry.active_tenant_count)}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">{strings.ui.tenantRegistry.tenantsAbleToEstablishSessions}</p>
        </article>
        <article className="min-w-0 rounded-2xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">{strings.ui.tenantRegistry.suspended}</p>
          <p className="font-display mx-0 mt-3 mb-1.5 text-2xl tabular-nums break-words text-ink">{formatNumber(suspendedCount)}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">{strings.ui.tenantRegistry.rejectedFailClosedAtThe}</p>
        </article>
        <article className="min-w-0 rounded-2xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]">
          <p className="eyebrow m-0">{strings.ui.tenantRegistry.pendingDeletion}</p>
          <p className="font-display mx-0 mt-3 mb-1.5 text-2xl tabular-nums break-words text-ink">{formatNumber(pendingDeletionCount)}</p>
          <p className="m-0 text-xs leading-relaxed text-muted break-words">{strings.ui.tenantRegistry.modeledAndBlockedNoDeletion}</p>
        </article>
      </div>

      <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow m-0">{strings.ui.common.filters}</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.tenantRegistry.tenantRegistry}</h2>
        </div>
        <div className="grid w-full min-w-0 gap-2.5 sm:flex sm:w-auto sm:flex-wrap sm:items-end sm:justify-end">
          <Field label={strings.ui.common.status}>
            <Select value={filters.status} onChange={(event) => updateStatus(event.target.value)}>
              <option value={allTenantFilter}>{strings.ui.common.allStatuses}</option>
              {tenantLifecycleStatuses.map((status: TenantLifecycleStatus) => (
                <option key={status} value={status}>
                  {tenantStatusLabel(status)}
                </option>
              ))}
            </Select>
          </Field>
          <button className="icon-button" onClick={resetFilters} title={strings.ui.common.resetFilters} type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      {tenants.length > 0 ? (
        <section className="min-w-0 overflow-x-auto rounded-2xl border border-line bg-surface dark:border-white/10 dark:bg-white/5">
          <table className={cn(dataTableClassName, "min-w-[640px]")}>
            <thead>
              <tr>
                <th>{strings.ui.common.tenant}</th>
                <th>{strings.ui.common.status}</th>
                <th>{strings.ui.tenantRegistry.createdBy}</th>
                <th>{strings.ui.tenantRegistry.lifecycle}</th>
                <th>{strings.ui.common.updated}</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((tenant) => (
                <tr key={tenant.tenant_id}>
                  <td>
                    <Link className="inline-flex min-h-6 items-center font-medium text-signal underline decoration-1 underline-offset-2" href={`/tenants/${tenant.tenant_id}`}>
                      {tenant.display_name}
                    </Link>
                    <p className="mx-0 mt-1 mb-0 leading-snug text-muted break-words font-mono text-[13px]">{tenant.tenant_id}</p>
                  </td>
                  <td>
                    <span className={`status-pill ${tenantStatusClass(tenant.status)}`}>
                      {tenantStatusLabel(tenant.status)}
                    </span>
                  </td>
                  <td>
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{tenant.created_by}</p>
                  </td>
                  <td>
                    {tenant.status === "suspended" ? (
                      <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                        Suspended by {tenant.suspended_by ?? "unknown"}
                        {tenant.suspension_reason ? ` — ${tenant.suspension_reason}` : ""}
                      </p>
                    ) : tenant.reactivated_at ? (
                      <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                        Reactivated by {tenant.reactivated_by ?? "unknown"}
                      </p>
                    ) : (
                      <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{strings.ui.tenantRegistry.noLifecycleChanges}</p>
                    )}
                  </td>
                  <td>
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{formatTimestamp(tenant.updated_at)}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {hasMore ? (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line/60 px-4 py-3.5 dark:border-white/10">
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {strings.ui.tenantRegistry.showingTenants(formatNumber(tenants.length))}
              </p>
              <button
                className="inline-flex items-center justify-center gap-2 rounded-full border border-mist bg-surface px-4 py-2 text-sm font-medium text-ink transition-all duration-300 select-none hover:border-signal/50 hover:text-signal disabled:cursor-not-allowed disabled:opacity-55 dark:border-white/20 dark:hover:border-signal/60"
                disabled={loadingMore}
                onClick={() => void loadMore()}
                type="button"
              >
                <Building2 size={16} />
                {loadingMore ? strings.ui.tenantRegistry.loading : strings.ui.tenantRegistry.loadMoreTenants}
              </button>
            </div>
          ) : null}
          {loadMoreError ? (
            <div className="border-t border-line/60 p-4 dark:border-white/10" role="alert">
              <ErrorPanel
                detail={strings.ui.tenantRegistry.axisCouldNotLoadThe}
                reference={loadMoreError.requestId ?? undefined}
                title={strings.ui.tenantRegistry.tenantPageUnavailable}
              />
            </div>
          ) : null}
        </section>
      ) : (
        <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">{strings.ui.common.registry}</p>
            <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{strings.ui.tenantRegistry.noTenantsMatchTheCurrent}</h2>
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
              {strings.ui.tenantRegistry.theTenantApiRespondedWithout}
            </p>
          </div>
          <span className="status-pill status-checking">
            <Building2 size={15} />
            {strings.ui.common.emptyRegistry}
          </span>
        </section>
      )}

      <Disclosure title={strings.clarity.createOrganization}>
        <TenantProvisionForm />
      </Disclosure>

      {tenantNotes.length > 0 ? (
        <section className="min-w-0 rounded-2xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <p className="eyebrow m-0">{strings.ui.common.registryNotes}</p>
          <div className="grid min-w-0 gap-2.5">
            {tenantNotes.map((note) => (
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={note}>
                {note}
              </p>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
