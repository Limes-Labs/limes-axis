"use client";

import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
import { countBlockedModelRoutes, type ManufacturingModelRouting } from "@/lib/model-routing-demo";
import type {
  ManufacturingOperationsSnapshot,
  ManufacturingOverview,
  OverviewMetric,
  PlatformStatus,
} from "@/lib/platform-overview";
import type { PlatformPolicyRegistry } from "@/lib/platform-policies";
import { strings } from "@/lib/strings";
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
  unavailable: boolean;
};

function metricByLabel(overview: ManufacturingOverview, label: string): OverviewMetric | null {
  return overview.metrics.find((metric) => metric.label === label) ?? null;
}

function connectorEventCount(snapshot: ManufacturingOperationsSnapshot): number {
  return snapshot.recent_audit_events.filter((event) => event.event_type.startsWith("connector."))
    .length;
}

function cardState<T>(
  query: OverviewQuery<T>,
  build: (data: T) => Pick<PostureCard, "value" | "detail" | "status">,
): Pick<PostureCard, "value" | "detail" | "status" | "unavailable"> {
  if (query.data) {
    return { ...build(query.data), unavailable: false };
  }

  if (query.source === "loading") {
    return { value: null, detail: "", status: "watch", unavailable: false };
  }

  return {
    value: strings.overview.posture.unavailable,
    detail: "This endpoint did not respond.",
    status: "watch",
    unavailable: true,
  };
}

export function PostureCards({
  overview,
  snapshot,
  routing,
}: {
  overview: OverviewQuery<ManufacturingOverview>;
  snapshot: OverviewQuery<ManufacturingOperationsSnapshot>;
  routing: OverviewQuery<ManufacturingModelRouting>;
}) {
  const policiesQuery = useAxisQuery<PlatformPolicyRegistry>(POLICIES_ENDPOINT);
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
      })),
    },
    {
      key: "workflows",
      label: copy.workflows.label,
      href: "/workflows",
      linkLabel: copy.workflows.link,
      ...cardState(overview, (data) => ({
        value: String(data.workflows.length),
        detail: metricByLabel(data, "Workflow Load")?.detail ?? "Workflow records from the API",
        status: metricByLabel(data, "Workflow Load")?.status ?? "watch",
      })),
    },
    {
      key: "connectors",
      label: copy.connectors.label,
      href: "/connectors",
      linkLabel: copy.connectors.link,
      ...cardState(snapshot, (data) => {
        const count = connectorEventCount(data);
        return {
          value: String(count),
          detail: "Recent connector evidence events",
          status: count > 0 ? "ready" : "watch",
        };
      }),
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
      })),
    },
    {
      key: "models",
      label: copy.models.label,
      href: "/model-routing",
      linkLabel: copy.models.link,
      ...cardState(routing, (data) => ({
        value: String(data.routes.length),
        detail: `${countBlockedModelRoutes(data)} blocked route`,
        status: data.routing_status,
      })),
    },
  ];

  return (
    <div
      aria-label="Platform posture"
      className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5"
      role="list"
    >
      {cards.map((card) => (
        <article
          className="grid content-start gap-2 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5"
          data-kpi-card
          key={card.key}
          role="listitem"
        >
          <div className="flex items-start justify-between gap-2">
            <Eyebrow>{card.label}</Eyebrow>
            {card.value === null ? null : <StatusDot status={card.status} />}
          </div>
          {card.value === null ? (
            <Skeleton className="h-7 w-2/5" />
          ) : (
            <p className="font-display m-0 text-xl break-words text-ink">{card.value}</p>
          )}
          <div aria-hidden="true" className="rule-dotted" />
          <p className="m-0 text-xs text-muted">{card.detail}</p>
          <PanelLink href={card.href}>{card.linkLabel}</PanelLink>
        </article>
      ))}
    </div>
  );
}
