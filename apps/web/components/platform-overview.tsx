"use client";

import { Suspense } from "react";

import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { ArtifactPanel } from "@/components/overview/artifact-panel";
import { EvidenceFeed } from "@/components/overview/evidence-feed";
import { NeedsAttention } from "@/components/overview/needs-attention";
import { type OverviewQuery } from "@/components/overview/overview-shared";
import { PostureCards } from "@/components/overview/posture-cards";
import { SideRail } from "@/components/overview/side-rail";
import { ErrorPanel, LoadingPanel } from "@/components/ui/states";
import type { ManufacturingAuditExplorer } from "@/lib/audit-demo";
import type { ManufacturingModelRouting } from "@/lib/model-routing-demo";
import {
  formatOverviewTimestamp,
  type IdentitySessionReadModel,
  type ManufacturingOperationsSnapshot,
  type ManufacturingOverview,
} from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { parseManufacturingAuditExplorer } from "@/lib/runtime-contracts/audit";
import { parseManufacturingModelRouting } from "@/lib/runtime-contracts/model-routing";
import {
  parseManufacturingOperationsSnapshot,
  parseManufacturingOverview,
  parseIdentitySessionReadModel,
} from "@/lib/runtime-contracts/overview";
import {
  buildTenantScopedPath,
  DEMO_TENANT_ID,
  resolveConsoleTenantScope,
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

const IDENTITY_SESSION_ENDPOINT = "/identity/session";
const OVERVIEW_ENDPOINT = "/demo/manufacturing/overview";
const SNAPSHOT_ENDPOINT = "/demo/manufacturing/operations/snapshot";
const MODEL_ROUTING_ENDPOINT = "/demo/manufacturing/model-routing";
const AUDIT_EVENTS_ENDPOINT = "/demo/manufacturing/audit/events";

function OverviewHero({
  overview,
  snapshot,
  auditEvents,
}: {
  overview: OverviewQuery<ManufacturingOverview>;
  snapshot: OverviewQuery<ManufacturingOperationsSnapshot>;
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
        title={strings.overview.hero.error.title}
      />
    );
  }

  const data = overview.data;
  const asOf = snapshot.data?.as_of ?? data.as_of;
  // One audit registry count for the whole page: the persisted audit events
  // payload that also drives the evidence feed. The seeded "Audit" overview
  // metric is never displayed, so the hero and the feed cannot disagree.
  const auditEventCount = auditEvents.data ? String(auditEvents.data.events.length) : "—";
  const facts = [
    { label: "Workflows", value: String(data.workflows.length) },
    { label: "Approvals pending", value: String(data.approvals.length) },
    { label: "Agents governed", value: String(data.agents.length) },
    { label: "Recent audit events", value: auditEventCount, testId: "hero-audit-count" },
  ];

  return (
    <section className="relative overflow-hidden rounded-3xl border border-navy bg-navy px-6 py-6 text-white sm:px-8 dark:border-white/10">
      {/* Signal glow + static dot grid, same treatment in both themes. */}
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 90% at 50% 110%, rgb(47 100 255 / 0.35) 0%, rgb(47 100 255 / 0.08) 45%, transparent 70%), radial-gradient(rgb(255 255 255 / 0.05) 1px, transparent 1px)",
          backgroundSize: "auto, 22px 22px",
        }}
      />
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-x-8 gap-y-4">
        <div className="grid gap-1">
          <h2 className="font-display m-0 text-2xl text-white">{data.scenario}</h2>
          <p className="ops-page-subtitle m-0! text-sm! text-white/70!">
            {data.plant_name} / {formatOverviewTimestamp(asOf)}
          </p>
        </div>
        <div className="flex flex-wrap gap-x-8 gap-y-3">
          {facts.map((fact) => (
            <div className="grid gap-0.5" key={fact.label}>
              <span className="font-display text-2xl text-white" data-testid={fact.testId}>
                {fact.value}
              </span>
              <span className="font-mono text-[10.5px] tracking-[0.14em] text-white/60 uppercase">
                {fact.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function PlatformOverview() {
  const { apiStatus, triggerRefresh } = useConsole();
  const demoBootstrap = useDemoBootstrap();
  const identityQuery = useAxisQuery<IdentitySessionReadModel>(IDENTITY_SESSION_ENDPOINT, {
    parse: parseIdentitySessionReadModel,
  });
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
  const auditEventsPath = buildTenantScopedPath(
    AUDIT_EVENTS_ENDPOINT,
    tenantId ?? DEMO_TENANT_ID,
    { limit: 25 },
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
  const auditEventsQuery = useAxisQuery<ManufacturingAuditExplorer>(auditEventsPath, {
    enabled: tenantQueriesEnabled,
    expectedTenantId: tenantId ?? undefined,
    parse: parseManufacturingAuditExplorer,
  });

  if (identityQuery.source === "loading") {
    return <LoadingPanel layout="detail" />;
  }

  if (identityQuery.source === "unavailable") {
    return (
      <ErrorPanel
        detail="The console could not verify the current actor and tenant. Tenant-scoped data is not loaded until identity is available."
        endpoint={IDENTITY_SESSION_ENDPOINT}
        title="Identity API unavailable"
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

  // An overview 404 on an otherwise healthy API means the tenant has never
  // been bootstrapped — that is the guided-setup story (spec §6), not an
  // error. A genuinely unreachable API (network failure, /ready probe down)
  // keeps the section-level error wall below.
  const tenantEmpty =
    !overviewQuery.data
    && overviewQuery.source === "unavailable"
    && overviewQuery.errorStatus === 404
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
      {/* Partially onboarded tenants keep a compact progress strip on top;
          it renders nothing at 0 of 5 or 5 of 5. */}
      <OnboardingChecklist tenantId={tenantId} variant="compact" />
      <OverviewHero
        auditEvents={auditEventsQuery}
        overview={overviewQuery}
        snapshot={snapshotQuery}
      />

      <NeedsAttention
        actor={
          identityQuery.data?.actor_id
            ? { actorId: identityQuery.data.actor_id, scopes: identityQuery.data.scopes }
            : undefined
        }
        overview={overviewQuery}
        tenantId={tenantId}
      />

      <PostureCards
        overview={overviewQuery}
        routing={routingQuery}
        snapshot={snapshotQuery}
        tenantId={tenantId}
      />

      <div className="ops-dashboard-grid grid grid-cols-1 gap-4 min-[1400px]:grid-cols-[minmax(0,1fr)_320px]">
        <main aria-label="Operations evidence" className="ops-dashboard-main grid min-w-0 content-start gap-4">
          <EvidenceFeed auditEvents={auditEventsQuery} />
          {/* Suspense boundary for useSearchParams inside the artifact panel. */}
          <Suspense fallback={<LoadingPanel layout="detail" />}>
            <ArtifactPanel onArtifactCommitted={triggerRefresh} snapshot={snapshotQuery} />
          </Suspense>
        </main>
        <aside
          aria-label="Operations side rail"
          className="ops-right-rail grid min-w-0 content-start gap-4"
        >
          <SideRail overview={overviewQuery} routing={routingQuery} snapshot={snapshotQuery} />
        </aside>
      </div>
    </div>
  );
}
