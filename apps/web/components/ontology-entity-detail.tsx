"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowLeftRight, Database, Network, RadioTower } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { Reveal } from "@/components/reveal";
import { PlatformStatusPill } from "@/components/status-pill";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
import { axisFetch } from "@/lib/axis-api";
import {
  formatNodeType,
  type ManufacturingOntologyEntityDetail,
} from "@/lib/ontology-demo";
import { formatOverviewTimestamp } from "@/lib/platform-overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type EntitySource = "loading" | "api" | "unavailable" | "missing";

function sourceLabel(source: EntitySource): string {
  if (source === "api") {
    return "API entity detail";
  }

  if (source === "missing") {
    return "Entity not found";
  }

  return source === "loading" ? "Loading entity API" : "Entity API unavailable";
}

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  const rendered = items.length > 0 ? items : [emptyLabel];

  return (
    <div className="flex flex-wrap gap-2">
      {rendered.map((item) => (
        <span
          className="inline-flex items-center rounded-full border border-line px-3 py-1 font-mono text-xs text-muted dark:border-white/15"
          key={item}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function EntityMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card className="grid content-start gap-2 p-5">
      <Eyebrow>{label}</Eyebrow>
      <p className="font-display m-0 text-2xl break-words text-ink">{value}</p>
      <div aria-hidden="true" className="rule-dotted" />
      <p className="m-0 font-mono text-xs break-words text-muted">{detail}</p>
    </Card>
  );
}

export function OntologyEntityDetail({ nodeId }: { nodeId: string }) {
  const [detail, setDetail] = useState<ManufacturingOntologyEntityDetail | null>(null);
  const [source, setSource] = useState<EntitySource>("loading");
  const { session } = useOidcConsoleSession();
  const { refreshNonce } = useConsole();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchEntity() {
      try {
        const response = await axisFetch(
          `/demo/manufacturing/ontology/entities/${encodeURIComponent(nodeId)}`,
          {
            session,
            signal: controller.signal,
          },
        );

        if (response.status === 404) {
          setDetail(null);
          setSource("missing");
          return;
        }

        if (!response.ok) {
          throw new Error(`Ontology entity request failed with ${response.status}`);
        }

        setDetail((await response.json()) as ManufacturingOntologyEntityDetail);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setDetail(null);
          setSource("unavailable");
        }
      }
    }

    void fetchEntity();

    return () => controller.abort();
  }, [nodeId, session, refreshNonce]);

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
        <ApiRequiredState
          detail="Axis did not receive an API-backed ontology entity. Local fallback entity records are disabled."
          endpoint={`/demo/manufacturing/ontology/entities/${nodeId}`}
          title="Entity API unavailable"
        />
      );
    }

    return (
      <Card className="flex flex-wrap items-center justify-between gap-4">
        <div className="grid gap-1">
          <Eyebrow>Ontology Entity</Eyebrow>
          <h2 className="font-display m-0 text-2xl text-ink">Entity not found</h2>
          <p className="m-0 font-mono text-sm text-muted">{nodeId}</p>
        </div>
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-mist bg-surface px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:border-signal/50 hover:text-signal dark:border-white/20"
          href="/ontology"
        >
          <ArrowLeft size={16} />
          Ontology
        </Link>
      </Card>
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

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <EntityMetric
          detail={detail.node.node_id}
          label="Type"
          value={formatNodeType(detail.node.node_type)}
        />
        <EntityMetric detail={detail.node.source_system} label="Domain" value={detail.node.domain} />
        <EntityMetric
          detail="Incoming relationships"
          label="Inbound"
          value={String(detail.inbound_count)}
        />
        <EntityMetric
          detail="Outgoing relationships"
          label="Outbound"
          value={String(detail.outbound_count)}
        />
      </div>

      <Card className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid max-w-2xl gap-1">
          <Eyebrow>Summary</Eyebrow>
          <h2 className="font-display m-0 text-xl text-ink">Read-only entity context</h2>
          <p className="m-0 text-sm text-muted">{detail.node.summary}</p>
        </div>
        <Link
          className="inline-flex items-center gap-2 rounded-full border border-mist bg-surface px-5 py-2.5 text-sm font-medium text-ink transition-colors hover:border-signal/50 hover:text-signal dark:border-white/20"
          href="/ontology"
        >
          <ArrowLeft size={16} />
          Ontology
        </Link>
      </Card>

      <Reveal>
        <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
          <Card className="grid content-start gap-4">
            <div className="flex items-start justify-between gap-3">
              <div className="grid gap-1">
                <Eyebrow>Relationships</Eyebrow>
                <h2 className="font-display m-0 text-xl text-ink">
                  {detail.connected_relationships.length} connected
                </h2>
              </div>
              <Network className="text-signal" size={18} />
            </div>
            <div className="grid gap-0">
              {detail.connected_relationships.map((item, index) => (
                <div
                  className="grid gap-3 py-4 first:pt-0 last:pb-0"
                  key={item.relationship.relationship_id}
                >
                  {index > 0 ? <div aria-hidden="true" className="rule-dotted -mt-4 mb-1" /> : null}
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="grid min-w-0 gap-1">
                      <p className="m-0 inline-flex items-center gap-2 text-sm font-medium text-ink">
                        <ArrowLeftRight className="shrink-0 text-signal" size={14} />
                        {item.direction} / {item.relationship.relation_type}
                      </p>
                      <p className="m-0 text-sm text-muted">{item.relationship.summary}</p>
                      <p className="m-0 font-mono text-xs text-muted">
                        {item.relationship.permission_scope}
                      </p>
                      <p className="m-0 text-xs text-muted">
                        {item.relationship.metadata.owner_role} /{" "}
                        {item.relationship.metadata.verification_status}
                      </p>
                      <p className="m-0 font-mono text-xs break-words text-muted">
                        {item.relationship.metadata.evidence_refs.join(", ")}
                      </p>
                    </div>
                    <Link
                      className="inline-flex items-center rounded-full border border-line px-3 py-1 font-mono text-xs text-ink transition-colors hover:border-signal/60 hover:text-signal dark:border-white/15"
                      href={`/ontology/${item.peer_node.node_id}`}
                    >
                      {item.peer_node.label}
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="grid content-start gap-4">
            <div className="grid gap-1">
              <Eyebrow>Governance</Eyebrow>
              <h2 className="font-display m-0 text-xl text-ink">Access and evidence</h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <section className="grid content-start gap-2">
                <Eyebrow>Required Permissions</Eyebrow>
                <TagList items={detail.required_permissions} emptyLabel="derived read scope" />
              </section>
              <section className="grid content-start gap-2">
                <Eyebrow>Evidence</Eyebrow>
                <TagList items={detail.evidence_refs} emptyLabel="node summary only" />
              </section>
            </div>
            <div aria-hidden="true" className="rule-dotted" />
            <div className="grid gap-4 sm:grid-cols-2">
              <section className="grid content-start gap-2">
                <Eyebrow>Workflows</Eyebrow>
                <TagList items={detail.related_workflows} emptyLabel="no workflow relation" />
              </section>
              <section className="grid content-start gap-2">
                <Eyebrow>Approvals</Eyebrow>
                <TagList items={detail.related_approvals} emptyLabel="no approval relation" />
              </section>
            </div>
            <div aria-hidden="true" className="rule-dotted" />
            <section className="grid content-start gap-2">
              <Eyebrow>Agents</Eyebrow>
              <TagList items={detail.related_agents} emptyLabel="no agent relation" />
            </section>
          </Card>
        </div>
      </Reveal>

      <Reveal>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="grid content-start gap-3">
            <Eyebrow>Data Access</Eyebrow>
            <div className="grid gap-3">
              {detail.data_access.map((item) => (
                <div className="flex items-start justify-between gap-3" key={item}>
                  <div className="grid gap-0.5">
                    <p className="m-0 text-sm font-medium text-ink">{item}</p>
                    <p className="m-0 text-xs text-muted">Public demo summary only</p>
                  </div>
                  <Database className="shrink-0 text-signal" size={16} />
                </div>
              ))}
            </div>
          </Card>

          <Card className="grid content-start gap-3">
            <Eyebrow>Detail Notes</Eyebrow>
            <div className="grid gap-2">
              {detail.detail_notes.map((note) => (
                <p className="m-0 text-sm text-muted" key={note}>
                  {note}
                </p>
              ))}
            </div>
          </Card>
        </div>
      </Reveal>
    </div>
  );
}
