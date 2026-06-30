"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Database, Network, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import {
  countNodesByType,
  formatNodeType,
  nodeLabelById,
  type ManufacturingOntology,
  type OntologyNodeType,
} from "@/lib/ontology-demo";
import { platformStatusClass, platformStatusLabel } from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API ontology graph";
  }

  return source === "loading" ? "Loading ontology API" : "Ontology API unavailable";
}

export function OntologyExplorer() {
  const { data: ontology, source } = useAxisQuery<ManufacturingOntology>(
    "/demo/manufacturing/ontology",
  );

  const nodeLabels = useMemo(
    () => (ontology ? nodeLabelById(ontology) : new Map<string, string>()),
    [ontology],
  );
  const nodeTypeCounts = useMemo(
    () => (ontology ? countNodesByType(ontology) : new Map<OntologyNodeType, number>()),
    [ontology],
  );

  if (!ontology) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed ontology records. Local fallback ontology records are disabled."
        endpoint="/demo/manufacturing/ontology"
        title={source === "loading" ? "Loading ontology API" : "Ontology API unavailable"}
      />
    );
  }

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Ontology</p>
          <h2 className="panel-title">{ontology.plant_name}</h2>
          <p className="row-detail">
            {ontology.scenario} / {ontology.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Ontology source">
          <span className="status-pill signal-ready">
            <Network size={15} />
            {sourceLabel(source)}
          </span>
          <span className="mono">{ontology.nodes.length} nodes</span>
          <span className="mono">{ontology.relationships.length} relationships</span>
        </div>
      </section>

      <div className="metric-grid">
        {Array.from(nodeTypeCounts.entries()).map(([type, count]) => (
          <article className="metric-card compact-card" key={type}>
            <p className="metric-label">{formatNodeType(type)}</p>
            <p className="metric-value">{count}</p>
            <p className="metric-detail">Mapped demo ontology nodes</p>
          </article>
        ))}
      </div>

      <div className="two-column">
        <section className="panel">
          <p className="section-label">Source Systems</p>
          <h2 className="panel-title">Connected context</h2>
          <div className="tag-list">
            {ontology.source_systems.map((system) => (
              <span className="tag" key={system}>
                <Database size={14} />
                {system}
              </span>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="section-label">Graph Query</p>
          <h2 className="panel-title">{ontology.graph_query.adapter}</h2>
          <div className="overview-meta" aria-label="Ontology graph query metadata">
            <span className="status-pill signal-ready">
              <ShieldCheck size={15} />
              {ontology.graph_query.query_mode}
            </span>
            <span className="mono">{ontology.graph_query.source}</span>
            <span className="mono">
              {ontology.graph_query.denied_relationship_count} denied relationships
            </span>
          </div>
          <p className="row-detail">
            {ontology.graph_query.returned_node_count} nodes /{" "}
            {ontology.graph_query.returned_relationship_count} relationships returned for{" "}
            {ontology.graph_query.actor_id}
          </p>
          <p className="row-detail">
            Permission decision: {ontology.graph_query.permission_decision.reason}
          </p>
        </section>

        <section className="panel">
          <p className="section-label">Permission Notes</p>
          <h2 className="panel-title">Read boundaries</h2>
          <div className="stack">
            {ontology.permission_notes.map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
            ))}
          </div>
        </section>
      </div>

      <section className="table-panel">
        <table className="data-table">
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
                  <Link className="text-link" href={`/ontology/${node.node_id}`}>
                    {node.label}
                  </Link>
                  <p className="row-detail">{node.summary}</p>
                </td>
                <td>{formatNodeType(node.node_type)}</td>
                <td>{node.domain}</td>
                <td>{node.source_system}</td>
                <td>
                  <span className={`status-pill ${platformStatusClass(node.status)}`}>
                    {platformStatusLabel(node.status)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="table-panel">
        <table className="data-table">
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
                  <p className="row-detail">{relationship.summary}</p>
                </td>
                <td>{nodeLabels.get(relationship.source_id)}</td>
                <td>{nodeLabels.get(relationship.target_id)}</td>
                <td>
                  <span className="mono">{relationship.permission_scope}</span>
                  <p className="row-detail">
                    {Math.round(relationship.metadata.confidence * 100)}% confidence
                  </p>
                </td>
                <td>
                  {relationship.metadata.owner_role}
                  <p className="row-detail mono">
                    {relationship.metadata.verification_status} /{" "}
                    {relationship.metadata.last_verified_at}
                  </p>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
