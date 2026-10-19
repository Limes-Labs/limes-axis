"use client";

import { SourcePill, sourceStateLabel } from "@/components/ui/source-pill";
import { StatCard } from "@/components/ui/stat-card";
import { isReadAuditEvent } from "@/lib/audit-demo";
import { formatNumber } from "@/lib/format";
import { countBlockedModelRoutes, type ManufacturingModelRouting } from "@/lib/model-routing-demo";
import {
  OPEN_WORKFLOWS_METRIC,
  type ManufacturingOperationsSnapshot,
  type ManufacturingOverview,
  type OverviewMetric,
  type PlatformStatus,
} from "@/lib/platform-overview";
import type { PlatformPolicyRegistry } from "@/lib/platform-policies";
import type { ConsoleStrings } from "@/lib/i18n";
import { useStrings } from "@/providers/locale-provider";
import { buildTenantScopedPath, DEMO_TENANT_ID } from "@/lib/tenant-scope";
import { parsePlatformPolicyRegistry } from "@/lib/runtime-contracts/policies";
import {
  deriveSourceState,
  PROVENANCE_NOT_APPLICABLE,
  type SourceProvenance,
  type SourceState,
} from "@/lib/source-state";
import { useAxisQuery } from "@/lib/use-axis-query";

import { PanelLink, StatusDot, type OverviewQuery } from "./overview-shared";

/*
 * The five posture cards from spec §5.1: agents, workflows, connectors,
 * policies, models — one status, one number, one link each. Every card is
 * driven by its own endpoint, so a failing endpoint only degrades the cards
 * that depend on it.
 */

export const POLICIES_ENDPOINT = "/platform/policies";

type PostureCard = {
  key: string;
  label: string;
  href: string;
  linkLabel: string;
  /** null while loading; the card renders a skeleton value. */
  value: string | null;
  detail: string;
  status: PlatformStatus;
  sourceState: SourceState;
};

function metricByLabel(
  source: Pick<ManufacturingOverview | ManufacturingOperationsSnapshot, "metrics">,
  label: string,
): OverviewMetric | null {
  return source.metrics.find((metric) => metric.label === label) ?? null;
}

function connectorEventCount(snapshot: ManufacturingOperationsSnapshot): number {
  // Reads are excluded: every /connectors visit writes workspace/policy read
  // evidence, which made merely looking at connectors read as "activity".
  return snapshot.recent_audit_events.filter(
    (event) => event.event_type.startsWith("connector.") && !isReadAuditEvent(event),
  ).length;
}

function cardState<T>(
  query: OverviewQuery<T>,
  build: (data: T) => Pick<PostureCard, "value" | "detail" | "status">,
  provenanceOf: (data: T) => SourceProvenance, strings: ConsoleStrings,
): Pick<PostureCard, "value" | "detail" | "status" | "sourceState"> {
  if (query.data) {
    return {
      ...build(query.data),
      sourceState: deriveSourceState(query.source, true, provenanceOf(query.data)),
    };
  }

  if (query.source === "loading") {
    return {
      value: null,
      detail: "",
      status: "watch",
      sourceState: deriveSourceState(query.source, false),
    };
  }

  return {
    value: strings.overview.posture.unavailable,
    detail: "This endpoint did not respond.",
    status: "watch",
    sourceState: deriveSourceState(query.source, false),
  };
}

export function PostureCards({
  overview,
  snapshot,
  routing,
  tenantId = DEMO_TENANT_ID,
}: {
  overview: OverviewQuery<ManufacturingOverview>;
  snapshot: OverviewQuery<ManufacturingOperationsSnapshot>;
  routing: OverviewQuery<ManufacturingModelRouting>;
  tenantId?: string;
}) {
  const strings = useStrings();
  const policiesQuery = useAxisQuery<PlatformPolicyRegistry>(
    buildTenantScopedPath(POLICIES_ENDPOINT, tenantId),
    { expectedTenantId: tenantId, parse: parsePlatformPolicyRegistry },
  );
  const copy = strings.overview.posture;

  const cards: PostureCard[] = [
    {
      key: "agents",
      label: copy.agents.label,
      href: "/agents",
      linkLabel: copy.agents.link,
      ...cardState(overview, (data) => ({
        value: String(data.agents.length),
        detail: metricByLabel(data, "Agents")?.detail ?? "Governed autonomy records",
        status: metricByLabel(data, "Agents")?.status ?? "ready",
      }), (data) => data.provenance, strings),
    },
    {
      key: "workflows",
      label: copy.workflows.label,
      href: "/workflows",
      linkLabel: copy.workflows.link,
      /*
       * The persisted open-workflow metric, the same number the overview hero
       * shows. It used to count the reference scenario's workflow array, so a
       * live tenant read "Open workflows 0" in the hero next to "3" here.
       */
      ...cardState(snapshot, (data) => {
        const metric = metricByLabel(data, OPEN_WORKFLOWS_METRIC);
        return {
          value: metric?.value ?? strings.overview.posture.unavailable,
          detail: metric?.detail ?? copy.workflows.detail,
          status: metric?.status ?? "watch",
        };
      }, (data) => data.provenance, strings),
    },
    {
      key: "connectors",
      label: copy.connectors.label,
      href: "/connectors",
      linkLabel: copy.connectors.link,
      /*
       * This counts connector evidence events in the latest audit window — it
       * is deliberately labelled as activity rather than as a connector count,
       * which is what it used to claim: five healthy idle connectors read "0 ·
       * watch" while one connector failing twelve times read "12 · ready".
       * A true health card needs the connector configurations endpoint on this
       * page; until then the card states exactly what it measures.
       */
      ...cardState(snapshot, (data) => {
        const count = connectorEventCount(data);
        return {
          value: formatNumber(count),
          detail: copy.connectors.detail,
          // Quiet connectors are not a problem, so zero activity is neutral.
          status: "ready",
        };
      }, (data) => data.provenance, strings),
    },
    {
      key: "policies",
      label: copy.policies.label,
      href: "/policies",
      linkLabel: copy.policies.link,
      ...cardState(policiesQuery, (data) => ({
        value: String(data.active_policy_count),
        detail: `${data.policy_count} authored, ${data.active_policy_count} active`,
        status: data.active_policy_count > 0 ? "ready" : "watch",
      }), () => PROVENANCE_NOT_APPLICABLE, strings),
    },
    {
      key: "models",
      label: copy.models.label,
      href: "/model-routing",
      linkLabel: copy.models.link,
      ...cardState(routing, (data) => ({
        value: formatNumber(data.routes.length),
        detail: strings.ui.overviewPostureCards.blockedRoutes(countBlockedModelRoutes(data)),
        status: data.routing_status,
      }), (data) => data.provenance, strings),
    },
  ];

  return (
    <div
      aria-label={strings.ui.overviewPostureCards.platformPosture}
      className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5"
      role="list"
    >
      {cards.map((card) => (
        <StatCard
          aside={card.value === null ? null : <StatusDot status={card.status} />}
          data-kpi-card
          detail={card.detail}
          data-source-state={card.sourceState}
          key={card.key}
          label={card.label}
          title={sourceStateLabel(card.sourceState, card.label.toLowerCase())}
          value={card.value}
        >
          {/* Provenance is in the tooltip and the page banner; stale numbers
              keep a visible warning because they are no longer current. */}
          {card.sourceState === "stale" ? (
            <SourcePill
              className="w-fit max-w-full"
              state={card.sourceState}
              subject={card.label.toLowerCase()}
            />
          ) : null}
          <PanelLink href={card.href}>{card.linkLabel}</PanelLink>
        </StatCard>
      ))}
    </div>
  );
}
