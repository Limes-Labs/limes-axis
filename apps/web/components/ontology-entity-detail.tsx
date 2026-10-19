"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { EntityDetailContent } from "@/components/ontology/entity-detail-content";
import { useOntologyEntity } from "@/components/ontology/use-ontology-entity";
import { PlatformStatusPill } from "@/components/status-pill";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
import { SourcePill } from "@/components/ui/source-pill";
import { EmptyPanel, ErrorPanel } from "@/components/ui/states";
import { formatContextPath, formatTimestamp } from "@/lib/format";
import { deriveSourceState } from "@/lib/source-state";
import { useStrings } from "@/providers/locale-provider";
import { DEMO_TENANT_ID } from "@/lib/tenant-scope";
import {
  IDENTITY_SESSION_ENDPOINT,
  useConsoleTenantScope,
} from "@/lib/use-console-tenant-scope";

export function OntologyEntityDetail({ nodeId }: { nodeId: string }) {
  const strings = useStrings();
  const { identity, tenantId, tenantQueriesEnabled } = useConsoleTenantScope();
  const { detail, endpoint, errorRequestId, source } = useOntologyEntity(
    nodeId,
    tenantId ?? DEMO_TENANT_ID,
    tenantQueriesEnabled,
  );

  if (identity.source === "unavailable") {
    return (
      <ErrorPanel
        detail={strings.ui.ontologyEntityDetail.theEntityIsNotLoaded}
        endpoint={IDENTITY_SESSION_ENDPOINT}
        reference={identity.errorRequestId ?? undefined}
        onRetry={identity.refetch}
        title={strings.states.identityUnavailable.title}
      />
    );
  }

  if (identity.source === "api" && !tenantId) {
    return (
      <ErrorPanel
        detail={strings.ui.ontologyEntityDetail.theAuthenticatedIdentityResponseDoes}
        endpoint={IDENTITY_SESSION_ENDPOINT}
        title={strings.ui.common.authenticatedTenantMissing}
      />
    );
  }

  if (!detail) {
    if (source === "loading") {
      return (
        <div className="grid gap-5" aria-busy="true" aria-label={strings.ui.ontologyEntityDetail.loadingEntityApi}>
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
          detail={strings.ui.ontologyEntityDetail.axisDidNotReceiveAn}
          endpoint={endpoint ?? undefined}
          reference={errorRequestId ?? undefined}
          title={strings.ui.ontologyEntityDetail.entityApiUnavailable}
        />
      );
    }

    return (
      <EmptyPanel
        action={{ label: strings.ui.ontologyEntityDetail.backToOntology, href: "/ontology" }}
        detail={strings.ui.ontologyEntityDetail.notFoundDetail(nodeId)}
        title={strings.ui.ontologyEntityDetail.entityNotFound}
      />
    );
  }

  return (
    <div className="grid gap-5">
      <Card className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <Eyebrow>{strings.ui.ontologyEntityDetail.ontologyEntity}</Eyebrow>
          <h2 className="font-display m-0 text-2xl text-ink">{detail.node.label}</h2>
          <p className="m-0 text-sm text-muted">
            {formatContextPath(detail.scenario, detail.tenant_id)}
          </p>
        </div>
        <div
          className="flex flex-wrap items-center gap-2"
          aria-label={strings.ui.ontologyEntityDetail.entitySourceAndNodeStatus}
        >
          <SourcePill
            state={deriveSourceState(
              source === "missing" ? "unavailable" : source,
              Boolean(detail),
              detail.provenance,
            )}
            subject="ontology entity"
          />
          <PlatformStatusPill status={detail.node.status} />
          <span className="font-mono text-xs text-muted">
            {formatTimestamp(detail.as_of)}
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
            {strings.ui.ontologyEntityDetail.ontology}
          </Link>
        }
      />
    </div>
  );
}
