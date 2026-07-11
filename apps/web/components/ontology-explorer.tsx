"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Database, List, Network, Share2, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { OntologyGraph } from "@/components/ontology-graph";
import { Reveal } from "@/components/reveal";
import { PlatformStatusPill } from "@/components/status-pill";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
import {
  countNodesByType,
  formatNodeType,
  nodeLabelById,
  type ManufacturingOntology,
  type OntologyNodeType,
} from "@/lib/ontology-demo";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";

type OntologyView = "graph" | "list";

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API ontology graph";
  }

  return source === "loading" ? "Loading ontology API" : "Ontology API unavailable";
}

function OntologyExplorerSkeleton() {
  return (
    <div className="grid gap-5" aria-busy="true" aria-label="Loading ontology API">
      <Skeleton className="h-28" />
      <Skeleton className="h-[420px]" />
    </div>
  );
}

export function OntologyExplorer() {
  const { data: ontology, source } = useAxisQuery<ManufacturingOntology>(
    "/demo/manufacturing/ontology",
  );
  const [view, setView] = useState<OntologyView>("graph");

  const nodeLabels = useMemo(
    () => (ontology ? nodeLabelById(ontology) : new Map<string, string>()),
    [ontology],
  );
  const nodeTypeCounts = useMemo(
    () => (ontology ? countNodesByType(ontology) : new Map<OntologyNodeType, number>()),
    [ontology],
  );

  if (!ontology) {
    if (source === "loading") {
      return <OntologyExplorerSkeleton />;
    }

    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed ontology records. Local fallback ontology records are disabled."
        endpoint="/demo/manufacturing/ontology"
        title="Ontology API unavailable"
      />
    );
  }

  return (
    <div className="grid gap-5">
      <div
        aria-label="Ontology source"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm break-words text-muted">
          {ontology.plant_name} / {ontology.scenario} / {ontology.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="status-pill signal-ready">
            <Network size={15} />
            {sourceLabel(source)}
          </span>
          <span className="font-mono text-xs text-muted">{ontology.nodes.length} nodes</span>
          <span className="font-mono text-xs text-muted">
            {ontology.relationships.length} relationships
          </span>
        </div>
      </div>

      <Card className="grid gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="grid gap-1">
            <Eyebrow>Knowledge Graph</Eyebrow>
            <h2 className="font-display m-0 text-xl text-ink">Typed entities and relationships</h2>
          </div>
          <div className="flex gap-2" role="group" aria-label="Ontology view">
            <Button
              aria-pressed={view === "graph"}
              className="px-4 py-2 text-sm"
              onClick={() => setView("graph")}
              variant={view === "graph" ? "primary" : "secondary"}
            >
              <Share2 size={15} />
              Graph
            </Button>
            <Button
              aria-pressed={view === "list"}
              className="px-4 py-2 text-sm"
              onClick={() => setView("list")}
              variant={view === "list" ? "primary" : "secondary"}
            >
              <List size={15} />
              List
            </Button>
          </div>
        </div>
        <div aria-hidden="true" className="rule-dotted" />

        {view === "graph" ? (
          <div className="grid gap-3">
            <OntologyGraph nodes={ontology.nodes} relationships={ontology.relationships} />
            <div
              className="flex flex-wrap items-center gap-x-4 gap-y-2 font-mono text-[11px] tracking-[0.14em] text-muted uppercase"
              aria-label={strings.ontology.legend.label}
            >
              <span className="inline-flex items-center gap-2">
                <span aria-hidden="true" className="inline-block size-2 rotate-45 bg-ink" />
                {strings.ontology.legend.entity}
              </span>
              <span className="inline-flex items-center gap-2">
                <span aria-hidden="true" className="inline-block size-2 rotate-45 bg-signal" />
                {strings.ontology.legend.selected}
              </span>
              <span className="inline-flex items-center gap-2">
                <span aria-hidden="true" className="inline-block h-px w-5 bg-signal/60" />
                {strings.ontology.legend.relation}
              </span>
              {Array.from(nodeTypeCounts.entries()).map(([type, count]) => (
                <span key={type}>{`${formatNodeType(type)} ×${count}`}</span>
              ))}
              <span className="normal-case">{strings.ontology.legend.hint}</span>
            </div>
          </div>
        ) : (
          <div className="grid gap-4">
            <DataTable aria-label="Ontology nodes">
              <thead>
                <tr>
                  <th>Node</th>
                  <th>Type</th>
                  <th>Domain</th>
                  <th>Source</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {ontology.nodes.map((node) => (
                  <tr key={node.node_id}>
                    <td>
                      <Link
                        className="font-medium text-signal hover:underline"
                        href={`/ontology/${node.node_id}`}
                      >
                        {node.label}
                      </Link>
                      <p className="m-0 mt-1 text-xs text-muted">{node.summary}</p>
                    </td>
                    <td>{formatNodeType(node.node_type)}</td>
                    <td>{node.domain}</td>
                    <td>{node.source_system}</td>
                    <td>
                      <PlatformStatusPill status={node.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>

            <DataTable aria-label="Ontology relationships">
              <thead>
                <tr>
                  <th>Relationship</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Permission</th>
                  <th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {ontology.relationships.map((relationship) => (
                  <tr key={relationship.relationship_id}>
                    <td>
                      <strong>{relationship.relation_type}</strong>
                      <p className="m-0 mt-1 text-xs text-muted">{relationship.summary}</p>
                    </td>
                    <td>{nodeLabels.get(relationship.source_id)}</td>
                    <td>{nodeLabels.get(relationship.target_id)}</td>
                    <td>
                      <span className="font-mono text-xs">{relationship.permission_scope}</span>
                      <p className="m-0 mt-1 text-xs text-muted">
                        {Math.round(relationship.metadata.confidence * 100)}% confidence
                      </p>
                    </td>
                    <td>
                      {relationship.metadata.owner_role}
                      <p className="m-0 mt-1 font-mono text-xs text-muted">
                        {relationship.metadata.verification_status} /{" "}
                        {relationship.metadata.last_verified_at}
                      </p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
        )}
      </Card>

      <Reveal>
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="grid content-start gap-3">
            <Eyebrow>Source Systems</Eyebrow>
            <h2 className="font-display m-0 text-xl text-ink">Connected context</h2>
            <div className="flex flex-wrap gap-2">
              {ontology.source_systems.map((system) => (
                <span
                  className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 font-mono text-xs text-muted dark:border-white/15"
                  key={system}
                >
                  <Database size={13} />
                  {system}
                </span>
              ))}
            </div>
          </Card>

          <Card className="grid content-start gap-3">
            <Eyebrow>Graph Query</Eyebrow>
            <h2 className="font-display m-0 text-xl text-ink">{ontology.graph_query.adapter}</h2>
            <div className="flex flex-wrap gap-2" aria-label="Ontology graph query metadata">
              <span className="status-pill signal-ready">
                <ShieldCheck size={15} />
                {ontology.graph_query.query_mode}
              </span>
              <span className="font-mono text-xs text-muted">{ontology.graph_query.source}</span>
              <span className="font-mono text-xs text-muted">
                {ontology.graph_query.denied_relationship_count} denied relationships
              </span>
            </div>
            <div aria-hidden="true" className="rule-dotted" />
            <p className="m-0 text-sm text-muted">
              {ontology.graph_query.returned_node_count} nodes /{" "}
              {ontology.graph_query.returned_relationship_count} relationships returned for{" "}
              {ontology.graph_query.actor_id}
            </p>
            <p className="m-0 text-sm text-muted">
              Permission decision: {ontology.graph_query.permission_decision.reason}
            </p>
          </Card>

          <Card className="grid content-start gap-3">
            <Eyebrow>Permission Notes</Eyebrow>
            <h2 className="font-display m-0 text-xl text-ink">Read boundaries</h2>
            <div className="grid gap-2">
              {ontology.permission_notes.map((note) => (
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
