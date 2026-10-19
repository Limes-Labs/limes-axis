"use client";

import { Suspense, useState } from "react";

import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { ArtifactPanel } from "@/components/overview/artifact-panel";
import {
  EvidenceFeed,
  OVERVIEW_AUDIT_WINDOW,
} from "@/components/overview/evidence-feed";
import { APPROVALS_ENDPOINT, NeedsAttention } from "@/components/overview/needs-attention";
import { type OverviewQuery } from "@/components/overview/overview-shared";
import { PostureCards } from "@/components/overview/posture-cards";
import { SideRail } from "@/components/overview/side-rail";
import { SourcePill } from "@/components/ui/source-pill";
import { StatCard } from "@/components/ui/stat-card";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  countAwaitingDecision,
  type ManufacturingApprovalInbox,
} from "@/lib/approval-demo";
import {
  partitionReadAuditEvents,
  type ManufacturingAuditExplorer,
} from "@/lib/audit-demo";
import type { ManufacturingModelRouting } from "@/lib/model-routing-demo";
import {
  formatNumber,
  formatTimestamp,
  NO_VALUE,
} from "@/lib/format";
import {
  OPEN_WORKFLOWS_METRIC,
  type ManufacturingOperationsSnapshot,
  type ManufacturingOverview,
} from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { parseManufacturingApprovalInbox } from "@/lib/runtime-contracts/approvals";
import { parseManufacturingAuditExplorer } from "@/lib/runtime-contracts/audit";
import { parseManufacturingModelRouting } from "@/lib/runtime-contracts/model-routing";
import {
  parseManufacturingOperationsSnapshot,
  parseManufacturingOverview,
} from "@/lib/runtime-contracts/overview";
import {
  IDENTITY_SESSION_ENDPOINT,
  useIdentitySession,
} from "@/lib/use-identity-session";
import { deriveSourceState } from "@/lib/source-state";
import {
  buildTenantScopedPath,
  DEMO_TENANT_ID,
  resolveConsoleTenantScope,
  OPERATIONS_API_PREFIX,
} from "@/lib/tenant-scope";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useDemoBootstrap } from "@/lib/use-demo-bootstrap";
import { useConsole } from "@/providers/console-provider";

/*
 * Overview control room (spec §5.1): slim hero, needs-attention strip,
 * posture cards, one evidence feed, governed-artifact panel, side rail.
 * Four independent queries — there is deliberately no page-level gate, so a
 * failing endpoint degrades only the sections that read from it.
 */

const OVERVIEW_ENDPOINT = `${OPERATIONS_API_PREFIX}/overview`;
const SNAPSHOT_ENDPOINT = `${OPERATIONS_API_PREFIX}/operations/snapshot`;
const MODEL_ROUTING_ENDPOINT = `${OPERATIONS_API_PREFIX}/model-routing`;
const AUDIT_EVENTS_ENDPOINT = `${OPERATIONS_API_PREFIX}/audit/events`;

function OverviewHero({
  overview,
  snapshot,
  approvals,
  auditEvents,
}: {
  overview: OverviewQuery<ManufacturingOverview>;
  snapshot: OverviewQuery<ManufacturingOperationsSnapshot>;
  approvals: OverviewQuery<ManufacturingApprovalInbox>;
  auditEvents: OverviewQuery<ManufacturingAuditExplorer>;
}) {
  if (!overview.data) {
    if (overview.source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    return (
      <ErrorPanel
        detail={strings.overview.hero.error.detail}
        endpoint={OVERVIEW_ENDPOINT}
        onRetry={overview.refetch}
        reference={overview.errorRequestId ?? undefined}
        title={strings.overview.hero.error.title}
      />
    );
  }

  const data = overview.data;
  const asOf = snapshot.data?.as_of ?? data.as_of;
  /*
   * Every headline number is read from the persisted operations snapshot, not
   * from the reference scenario. The scenario's own arrays and metrics describe
   * a fictional plant — on a live tenant they read "3 workflows / 3 approvals
   * pending" while the persisted truth is zero, which is exactly the kind of
   * confident-but-wrong number this console must never show. When the snapshot
   * has not resolved, the fact reads "—" rather than falling back to seed data.
   *
   * One source per number: "Open workflows" is the snapshot metric the
   * workflows posture card also shows, and "Pending approvals" is counted from
   * the approvals queue that feeds the needs-attention cards and the sidebar
   * badge, so the hero can never contradict the panels around it.
   */
  const persistedFact = (metricLabel: string): string => {
    const metric = snapshot.data?.metrics.find((entry) => entry.label === metricLabel);
    return metric ? metric.value : NO_VALUE;
  };
  // The audit endpoint is fetched with a fixed limit and exposes no total, so
  // this is explicitly the size of the latest window, never "all events".
  const auditEventCount = auditEvents.data
    ? formatNumber(auditEvents.data.events.length)
    : NO_VALUE;
  const pendingApprovals = approvals.data
    ? formatNumber(countAwaitingDecision(approvals.data))
    : NO_VALUE;
  const facts = [
    {
      label: strings.overview.hero.facts.openWorkflows,
      value: persistedFact(OPEN_WORKFLOWS_METRIC),
      testId: "hero-open-workflows",
    },
    {
      label: strings.overview.hero.facts.pendingApprovals,
      value: pendingApprovals,
      testId: "hero-pending-approvals",
    },
    { label: strings.overview.hero.facts.operationRecords, value: persistedFact("Operation Records") },
    {
      label: strings.overview.hero.facts.recentAudit,
      value: auditEventCount,
      testId: "hero-audit-count",
    },
  ];

  return (
    <section aria-label={strings.clarity.recordedActivity} className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 text-sm font-medium text-ink">{strings.clarity.recordedActivity}</h2>
        <span className="text-xs text-muted">{data.plant_name} · {formatTimestamp(asOf)}</span>
      </div>
      <div className="grid min-w-0 grid-cols-2 gap-3 lg:grid-cols-4" role="list">
        {facts.map((fact) => (
          <StatCard key={fact.label} label={fact.label} value={fact.value} valueTestId={fact.testId} />
        ))}
      </div>
      <div aria-label="Overview data sources" className="flex min-w-0 flex-wrap gap-1.5">
        <SourcePill compact state={deriveSourceState(overview.source, true, data.provenance)} subject="Context" />
        <SourcePill compact state={deriveSourceState(snapshot.source, Boolean(snapshot.data), snapshot.data?.provenance)} subject="Operations" />
        <SourcePill compact state={deriveSourceState(approvals.source, Boolean(approvals.data), approvals.data?.provenance)} subject="Approvals" />
        <SourcePill compact state={deriveSourceState(auditEvents.source, Boolean(auditEvents.data), auditEvents.data?.provenance)} subject="Audit" />
      </div>
    </section>
  );
}

export function PlatformOverview() {
  const { apiStatus, triggerRefresh } = useConsole();
  const demoBootstrap = useDemoBootstrap();
  const identityQuery = useIdentitySession();
  const tenantScope = resolveConsoleTenantScope(identityQuery.data);
  const tenantId = tenantScope.tenantId;
  const tenantQueriesEnabled = identityQuery.source === "api" && tenantId !== null;
  const overviewPath = buildTenantScopedPath(
    OVERVIEW_ENDPOINT,
    tenantId ?? DEMO_TENANT_ID,
  );
  const snapshotPath = buildTenantScopedPath(
    SNAPSHOT_ENDPOINT,
    tenantId ?? DEMO_TENANT_ID,
  );
  const routingPath = buildTenantScopedPath(
    MODEL_ROUTING_ENDPOINT,
    tenantId ?? DEMO_TENANT_ID,
  );
  const approvalsPath = buildTenantScopedPath(
    APPROVALS_ENDPOINT,
    tenantId ?? DEMO_TENANT_ID,
  );
  const auditEventsPath = buildTenantScopedPath(
    AUDIT_EVENTS_ENDPOINT,
    tenantId ?? DEMO_TENANT_ID,
    { limit: OVERVIEW_AUDIT_WINDOW },
  );
  const overviewQuery = useAxisQuery<ManufacturingOverview>(overviewPath, {
    enabled: tenantQueriesEnabled,
    expectedTenantId: tenantId ?? undefined,
    parse: parseManufacturingOverview,
  });
  const snapshotQuery = useAxisQuery<ManufacturingOperationsSnapshot>(snapshotPath, {
    enabled: tenantQueriesEnabled,
    expectedTenantId: tenantId ?? undefined,
    parse: parseManufacturingOperationsSnapshot,
  });
  const routingQuery = useAxisQuery<ManufacturingModelRouting>(routingPath, {
    enabled: tenantQueriesEnabled,
    expectedTenantId: tenantId ?? undefined,
    parse: parseManufacturingModelRouting,
  });
  // One approvals query for the page: the hero count and the needs-attention
  // cards both read it (the sidebar badge counts the same endpoint the same way).
  const approvalsQuery = useAxisQuery<ManufacturingApprovalInbox>(approvalsPath, {
    enabled: tenantQueriesEnabled,
    expectedTenantId: tenantId ?? undefined,
    parse: parseManufacturingApprovalInbox,
  });
  const auditEventsQuery = useAxisQuery<ManufacturingAuditExplorer>(auditEventsPath, {
    enabled: tenantQueriesEnabled,
    expectedTenantId: tenantId ?? undefined,
    parse: parseManufacturingAuditExplorer,
  });
  // The hero count, the evidence feed and the activity chart all show the same
  // display window: state-changing events by default, reads on request. This
  // is a view filter only; the ledger and the request are unchanged.
  const [showReads, setShowReads] = useState(false);
  const auditPartition = auditEventsQuery.data
    ? partitionReadAuditEvents(auditEventsQuery.data.events)
    : null;
  const hiddenReadCount = !showReads && auditPartition ? auditPartition.reads.length : 0;
  const activityQuery: typeof auditEventsQuery =
    auditEventsQuery.data && auditPartition && !showReads
      ? {
          ...auditEventsQuery,
          data: { ...auditEventsQuery.data, events: auditPartition.stateChanging },
        }
      : auditEventsQuery;

  if (identityQuery.source === "loading") {
    return <LoadingPanel layout="detail" />;
  }

  if (identityQuery.source === "unavailable") {
    return (
      <ErrorPanel
        detail="The console could not verify the current actor and tenant. Tenant-scoped data is not loaded until identity is available."
        endpoint={IDENTITY_SESSION_ENDPOINT}
        reference={identityQuery.errorRequestId ?? undefined}
        onRetry={identityQuery.refetch}
        title={strings.states.identityUnavailable.title}
      />
    );
  }

  if (!tenantId) {
    return (
      <ErrorPanel
        detail="The authenticated identity response does not contain a tenant. Axis will not fall back to demo data for an authenticated actor."
        endpoint={IDENTITY_SESSION_ENDPOINT}
        title="Authenticated tenant missing"
      />
    );
  }

  // `TENANT_NOT_FOUND` on an otherwise healthy API means the tenant has never
  // been bootstrapped — that is the guided-setup story (spec §6), not an
  // error. useAxisQuery classifies that response as `tenant_not_found`, never
  // as `unavailable`. A genuinely unreachable API (network failure, /ready
  // probe down) keeps the section-level error wall below.
  const tenantEmpty =
    !overviewQuery.data
    && overviewQuery.source === "tenant_not_found"
    && apiStatus.state !== "unavailable";

  if (tenantEmpty) {
    return (
      <div className="grid gap-4">
        <OnboardingChecklist
          demoAvailable={tenantScope.mode === "demo"}
          demoError={demoBootstrap.error}
          demoPending={demoBootstrap.pending}
          onExploreDemo={demoBootstrap.bootstrapDemo}
          tenantId={tenantId}
          variant="full"
        />
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <OverviewHero
        approvals={approvalsQuery}
        auditEvents={activityQuery}
        overview={overviewQuery}
        snapshot={snapshotQuery}
      />

      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
      <NeedsAttention
        actor={
          identityQuery.data?.actor_id
            ? { actorId: identityQuery.data.actor_id, scopes: identityQuery.data.scopes }
            : undefined
        }
        approvals={approvalsQuery}
        identitySession={identityQuery.data ?? null}
        overview={overviewQuery}
        tenantId={tenantId}
      />
        <SideRail auditEvents={activityQuery} hiddenReadCount={hiddenReadCount} />
      </div>

      <OnboardingChecklist tenantId={tenantId} variant="compact" />

      <PostureCards
        overview={overviewQuery}
        routing={routingQuery}
        snapshot={snapshotQuery}
        tenantId={tenantId}
      />

      <div className="ops-dashboard-grid grid grid-cols-1 gap-4">
        <section aria-label="Operations evidence" className="ops-dashboard-main grid min-w-0 content-start gap-4">
          <EvidenceFeed
            auditEvents={activityQuery}
            reads={{
              showReads,
              hiddenCount: hiddenReadCount,
              onShowReadsChange: setShowReads,
            }}
          />
          {/* Suspense boundary for useSearchParams inside the artifact panel. */}
          <Suspense fallback={<LoadingPanel layout="detail" />}>
            <ArtifactPanel onArtifactCommitted={triggerRefresh} snapshot={snapshotQuery} />
          </Suspense>
        </section>

      </div>
    </div>
  );
}
