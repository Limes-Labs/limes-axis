"use client";

import Link from "next/link";
import { ArrowLeft, RadioTower } from "lucide-react";

import { EntityDetailContent } from "@/components/ontology/entity-detail-content";
import {
  useOntologyEntity,
  type OntologyEntitySource,
} from "@/components/ontology/use-ontology-entity";
import { PlatformStatusPill } from "@/components/status-pill";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyPanel, ErrorPanel } from "@/components/ui/states";
import { formatOverviewTimestamp } from "@/lib/platform-overview";

function sourceLabel(source: OntologyEntitySource): string {
  if (source === "api") {
    return "API entity detail";
  }

  if (source === "missing") {
    return "Entity not found";
  }

  return source === "loading" ? "Loading entity API" : "Entity API unavailable";
}

export function OntologyEntityDetail({ nodeId }: { nodeId: string }) {
  const { detail, source } = useOntologyEntity(nodeId);

  if (!detail) {
    if (source === "loading") {
      return (
        <div className="grid gap-5" aria-busy="true" aria-label="Loading entity API">
          <Skeleton className="h-28" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
          <Skeleton className="h-72" />
        </div>
      );
    }

    if (source !== "missing") {
      return (
        <ErrorPanel
          detail="Axis did not receive an API-backed ontology entity. Local fallback entity records are disabled."
          endpoint={`/demo/manufacturing/ontology/entities/${nodeId}`}
          title="Entity API unavailable"
        />
      );
    }

    return (
      <EmptyPanel
        action={{ label: "Back to ontology", href: "/ontology" }}
        detail={`No ontology entity exists with the id ${nodeId}. It may have been renamed or removed from the graph.`}
        title="Entity not found"
      />
    );
  }

  return (
    <div className="grid gap-5">
      <Card className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <Eyebrow>Ontology Entity</Eyebrow>
          <h2 className="font-display m-0 text-2xl text-ink">{detail.node.label}</h2>
          <p className="m-0 text-sm text-muted">
            {detail.scenario} / {detail.tenant_id}
          </p>
        </div>
        <div
          className="flex flex-wrap items-center gap-2"
          aria-label="Entity source and node status"
        >
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <PlatformStatusPill status={detail.node.status} />
          <span className="font-mono text-xs text-muted">
            {formatOverviewTimestamp(detail.as_of)}
          </span>
        </div>
      </Card>

      <EntityDetailContent
        detail={detail}
        summaryAction={
          <Link
            className="inline-flex items-center gap-2 rounded-full border border-mist bg-surface px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:border-signal/50 hover:text-signal dark:border-white/20"
            href="/ontology"
          >
            <ArrowLeft size={16} />
            Ontology
          </Link>
        }
      />
    </div>
  );
}
