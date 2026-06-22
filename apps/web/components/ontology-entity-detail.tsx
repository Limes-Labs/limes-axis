"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Database, Network, RadioTower, ShieldCheck } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api-status";
import { buildAxisAuthInit } from "@/lib/oidc-session";
import {
  buildOntologyEntityDetail,
  defaultManufacturingOntology,
  formatNodeType,
  type ManufacturingOntologyEntityDetail,
} from "@/lib/ontology-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";

type EntitySource = "loading" | "api" | "fallback" | "missing";

function sourceLabel(source: EntitySource): string {
  if (source === "api") {
    return "Live entity seed";
  }

  if (source === "missing") {
    return "Entity not found";
  }

  return source === "loading" ? "Loading entity seed" : "Fallback entity seed";
}

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  return (
    <div className="tag-list">
      {items.length > 0 ? (
        items.map((item) => (
          <span className="tag" key={item}>
            {item}
          </span>
        ))
      ) : (
        <span className="tag">{emptyLabel}</span>
      )}
    </div>
  );
}

export function OntologyEntityDetail({ nodeId }: { nodeId: string }) {
  const fallbackDetail = useMemo(
    () => buildOntologyEntityDetail(defaultManufacturingOntology, nodeId),
    [nodeId],
  );
  const [detail, setDetail] = useState<ManufacturingOntologyEntityDetail | null>(
    fallbackDetail,
  );
  const [source, setSource] = useState<EntitySource>(fallbackDetail ? "loading" : "missing");
  const apiBaseUrl = getApiBaseUrl();
  const { session } = useOidcConsoleSession();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchEntity() {
      try {
        const response = await fetch(
          `${apiBaseUrl}/demo/manufacturing/ontology/entities/${encodeURIComponent(nodeId)}`,
          buildAxisAuthInit(
            {
              signal: controller.signal,
              cache: "no-store",
            },
            session,
          ),
        );

        if (!response.ok) {
          throw new Error(`Ontology entity request failed with ${response.status}`);
        }

        setDetail((await response.json()) as ManufacturingOntologyEntityDetail);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setDetail(fallbackDetail);
          setSource(fallbackDetail ? "fallback" : "missing");
        }
      }
    }

    void fetchEntity();

    return () => controller.abort();
  }, [apiBaseUrl, fallbackDetail, nodeId, session]);

  if (!detail) {
    return (
      <div className="stack">
        <section className="panel overview-context">
          <div>
            <p className="section-label">Ontology Entity</p>
            <h2 className="panel-title">Entity not found</h2>
            <p className="row-detail mono">{nodeId}</p>
          </div>
          <Link className="command-button" href="/ontology">
            <ArrowLeft size={17} />
            Ontology
          </Link>
        </section>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Ontology Entity</p>
          <h2 className="panel-title">{detail.node.label}</h2>
          <p className="row-detail">
            {detail.scenario} / {detail.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Entity source and node status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(detail.node.status)}`}>
            <Network size={15} />
            {platformStatusLabel(detail.node.status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(detail.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        <article className="metric-card compact-card">
          <p className="metric-label">Type</p>
          <p className="metric-value">{formatNodeType(detail.node.node_type)}</p>
          <p className="metric-detail">{detail.node.node_id}</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Domain</p>
          <p className="metric-value">{detail.node.domain}</p>
          <p className="metric-detail">{detail.node.source_system}</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Inbound</p>
          <p className="metric-value">{detail.inbound_count}</p>
          <p className="metric-detail">Incoming relationships</p>
        </article>
        <article className="metric-card compact-card">
          <p className="metric-label">Outbound</p>
          <p className="metric-value">{detail.outbound_count}</p>
          <p className="metric-detail">Outgoing relationships</p>
        </article>
      </div>

      <section className="panel entity-summary-panel">
        <div>
          <p className="section-label">Summary</p>
          <h2 className="panel-title">Read-only entity context</h2>
          <p className="row-detail">{detail.node.summary}</p>
        </div>
        <Link className="command-button" href="/ontology">
          <ArrowLeft size={17} />
          Ontology
        </Link>
      </section>

      <div className="entity-layout">
        <section className="panel entity-detail">
          <div className="entity-detail-header">
            <div>
              <p className="section-label">Relationships</p>
              <h2 className="panel-title">{detail.connected_relationships.length} connected</h2>
            </div>
            <ShieldCheck size={18} />
          </div>
          <div className="entity-relationship-list">
            {detail.connected_relationships.map((item) => (
              <div className="entity-relationship-item" key={item.relationship.relationship_id}>
                <div>
                  <p className="row-title">
                    {item.direction} / {item.relationship.relation_type}
                  </p>
                  <p className="row-detail">{item.relationship.summary}</p>
                  <p className="row-detail mono">{item.relationship.permission_scope}</p>
                </div>
                <Link className="tag" href={`/ontology/${item.peer_node.node_id}`}>
                  {item.peer_node.label}
                </Link>
              </div>
            ))}
          </div>
        </section>

        <section className="panel entity-detail">
          <p className="section-label">Governance</p>
          <h2 className="panel-title">Access and evidence</h2>
          <div className="entity-columns">
            <section>
              <p className="section-label">Required Permissions</p>
              <TagList items={detail.required_permissions} emptyLabel="derived read scope" />
            </section>
            <section>
              <p className="section-label">Evidence</p>
              <TagList items={detail.evidence_refs} emptyLabel="node summary only" />
            </section>
          </div>
          <div className="entity-columns">
            <section>
              <p className="section-label">Workflows</p>
              <TagList items={detail.related_workflows} emptyLabel="no workflow relation" />
            </section>
            <section>
              <p className="section-label">Approvals</p>
              <TagList items={detail.related_approvals} emptyLabel="no approval relation" />
            </section>
          </div>
          <section>
            <p className="section-label">Agents</p>
            <TagList items={detail.related_agents} emptyLabel="no agent relation" />
          </section>
        </section>
      </div>

      <div className="entity-layout">
        <section className="panel">
          <p className="section-label">Data Access</p>
          <div className="stack">
            {detail.data_access.map((item) => (
              <div className="row" key={item}>
                <div>
                  <p className="row-title">{item}</p>
                  <p className="row-detail">Public demo summary only</p>
                </div>
                <Database size={17} />
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="section-label">Detail Notes</p>
          <div className="stack">
            {detail.detail_notes.map((note) => (
              <p className="row-detail" key={note}>
                {note}
              </p>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
