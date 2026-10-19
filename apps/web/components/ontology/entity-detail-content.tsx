"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeftRight, Database, Network, TriangleAlert } from "lucide-react";

import { Reveal } from "@/components/reveal";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { humanizeIdentifier, humanizeScope } from "@/lib/display-names";
import {
  entityAttention,
  formatNodeType,
  resolveRelatedNodes,
  type ManufacturingOntologyEntityDetail,
} from "@/lib/ontology-demo";
import { useStrings } from "@/providers/locale-provider";
import { buildOntologyEntityRoute } from "@/lib/ontology-routes";

/*
 * Presentational core of the ontology entity detail, shared by the full
 * entity page and the explorer slide-over. Page chrome (headers, source
 * pills, back links) stays with the callers.
 */

type EntityDetailLayout = "page" | "sheet";

type EntityDetailContentProps = {
  detail: ManufacturingOntologyEntityDetail;
  /** "page" spreads sections into columns; "sheet" stacks them. */
  layout?: EntityDetailLayout;
  /**
   * When set, peer entity chips become buttons handled in place (the
   * slide-over swaps entities without navigating). Defaults to links to
   * the full entity pages.
   */
  onNavigateToNode?: (nodeId: string) => void;
  /** Optional action rendered next to the summary (e.g. a back link). */
  summaryAction?: ReactNode;
};

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

function RelatedNodeList({
  detail,
  ids,
  emptyLabel,
  onNavigateToNode,
}: {
  detail: ManufacturingOntologyEntityDetail;
  ids: string[];
  emptyLabel: string;
  onNavigateToNode?: (nodeId: string) => void;
}) {
  if (ids.length === 0) {
    return <TagList emptyLabel={emptyLabel} items={[]} />;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {resolveRelatedNodes(detail, ids).map(({ id, node }) =>
        node && node.node_id !== detail.node.node_id ? (
          <PeerNodeChip
            key={id}
            label={node.label}
            nodeId={node.node_id}
            onNavigateToNode={onNavigateToNode}
          />
        ) : (
          <span
            className="inline-flex items-center rounded-full border border-line px-3 py-1 text-xs text-muted dark:border-white/15"
            key={id}
            title={id}
          >
            {node?.label ?? humanizeIdentifier(id) ?? id}
          </span>
        ),
      )}
    </div>
  );
}

/** Type/Domain/Source at metadata size, with the raw node id kept secondary. */
function EntityFacts({ detail }: { detail: ManufacturingOntologyEntityDetail }) {
  const strings = useStrings();
  const copy = strings.ontology.entity;

  return (
    <Card className="grid content-start gap-3 p-5" data-entity-facts>
      <dl className="m-0 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
        <div className="grid min-w-0 gap-0.5">
          <dt className="text-xs font-medium text-muted">{copy.type}</dt>
          <dd className="m-0 break-words text-ink">{formatNodeType(detail.node.node_type)}</dd>
        </div>
        <div className="grid min-w-0 gap-0.5">
          <dt className="text-xs font-medium text-muted">{copy.domain}</dt>
          <dd className="m-0 break-words text-ink">{detail.node.domain}</dd>
        </div>
        <div className="grid min-w-0 gap-0.5">
          <dt className="text-xs font-medium text-muted">{copy.source}</dt>
          <dd className="m-0 break-words text-ink">
            {humanizeIdentifier(detail.node.source_system) ?? detail.node.source_system}
          </dd>
        </div>
      </dl>
      <p className="m-0 font-mono text-xs break-all text-muted">{detail.node.node_id}</p>
    </Card>
  );
}

/**
 * Reason and next step for a non-ready entity: the API's own summary, the
 * connected records that are also not ready, and the queue that can resolve
 * it when the entity relates to approvals or workflows.
 */
function EntityAttentionCallout({
  detail,
  onNavigateToNode,
}: {
  detail: ManufacturingOntologyEntityDetail;
  onNavigateToNode?: (nodeId: string) => void;
}) {
  const strings = useStrings();
  const attention = entityAttention(detail);
  if (!attention) {
    return null;
  }
  const copy = strings.ontology.entity.attention;
  const tone =
    attention.status === "action_required"
      ? "border-danger/35 bg-danger/5 dark:bg-danger/10"
      : "border-warning/40 bg-warning/8 dark:bg-warning/10";

  return (
    <section
      aria-label={copy[attention.status]}
      className={`flex min-w-0 items-start gap-3 rounded-2xl border p-4 ${tone}`}
      data-entity-attention={attention.status}
    >
      <TriangleAlert
        aria-hidden="true"
        className={attention.status === "action_required" ? "mt-0.5 shrink-0 text-danger" : "mt-0.5 shrink-0 text-warning"}
        size={18}
      />
      <div className="grid min-w-0 gap-2">
        <p className="m-0 font-medium text-ink">{copy[attention.status]}</p>
        <p className="m-0 text-sm leading-snug text-muted">{attention.reason}</p>
        {attention.peers.length > 0 ? (
          <div className="grid gap-1.5">
            <p className="m-0 text-xs font-medium text-muted">{copy.connected}</p>
            <div className="flex flex-wrap gap-2">
              {attention.peers.map((peer) => (
                <PeerNodeChip
                  key={peer.node_id}
                  label={peer.label}
                  nodeId={peer.node_id}
                  onNavigateToNode={onNavigateToNode}
                />
              ))}
            </div>
          </div>
        ) : null}
        {attention.link ? (
          <Link
            className="inline-flex w-fit items-center text-sm font-medium text-signal hover:underline"
            href={attention.link.href}
          >
            {attention.link.kind === "approvals" ? copy.reviewApprovals : copy.openWorkflows}
          </Link>
        ) : null}
      </div>
    </section>
  );
}

function EntityMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card className="grid content-start gap-2 p-5">
      <Eyebrow>{label}</Eyebrow>
      <p className="font-display m-0 text-2xl break-words text-ink">{value}</p>
      <div aria-hidden="true" className="rule-hairline" />
      <p className="m-0 font-mono text-xs break-words text-muted">{detail}</p>
    </Card>
  );
}

function PeerNodeChip({
  label,
  nodeId,
  onNavigateToNode,
}: {
  label: string;
  nodeId: string;
  onNavigateToNode?: (nodeId: string) => void;
}) {
  const className =
    "inline-flex items-center rounded-full border border-line px-3 py-1 text-xs text-ink transition-colors hover:border-signal/60 hover:text-signal dark:border-white/15";

  if (onNavigateToNode) {
    return (
      <button className={className} onClick={() => onNavigateToNode(nodeId)} type="button">
        {label}
      </button>
    );
  }

  return (
    <Link className={className} href={buildOntologyEntityRoute(nodeId)}>
      {label}
    </Link>
  );
}

export function EntityDetailContent({
  detail,
  layout = "page",
  onNavigateToNode,
  summaryAction,
}: EntityDetailContentProps) {
  const strings = useStrings();
  const isPage = layout === "page";
  const MaybeReveal = isPage ? Reveal : "div";

  return (
    <div className="grid min-w-0 gap-5">
      <Card className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid max-w-2xl gap-1">
          <h2 className="font-display m-0 text-xl text-ink">{strings.clarity.objectSummary}</h2>
          <p className="m-0 text-sm text-muted">{detail.node.summary}</p>
        </div>
        {summaryAction}
      </Card>

      <EntityAttentionCallout detail={detail} onNavigateToNode={onNavigateToNode} />

      <div className={`grid grid-cols-2 gap-4 ${isPage ? "lg:grid-cols-[2fr_1fr_1fr]" : ""}`}>
        <div className={isPage ? "col-span-2 lg:col-span-1" : "col-span-2"}>
          <EntityFacts detail={detail} />
        </div>
        <EntityMetric
          detail={strings.ui.ontologyEntityDetailContent.incomingRelationships}
          label={strings.ui.ontologyEntityDetailContent.inbound}
          value={String(detail.inbound_count)}
        />
        <EntityMetric
          detail={strings.ui.ontologyEntityDetailContent.outgoingRelationships}
          label={strings.ui.ontologyEntityDetailContent.outbound}
          value={String(detail.outbound_count)}
        />
      </div>



      <MaybeReveal>
        <div className={`grid gap-4 ${isPage ? "xl:grid-cols-[3fr_2fr]" : ""}`}>
          <Card className="grid content-start gap-4">
            <div className="flex items-start justify-between gap-3">
              <div className="grid gap-1">
                <Eyebrow>{strings.ui.ontologyEntityDetailContent.relationships}</Eyebrow>
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
                  {index > 0 ? <div aria-hidden="true" className="rule-hairline -mt-4 mb-1" /> : null}
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="grid min-w-0 gap-1">
                      <p
                        className="m-0 inline-flex items-center gap-2 text-sm font-medium text-ink"
                        title={item.relationship.relationship_id}
                      >
                        <ArrowLeftRight className="shrink-0 text-signal" size={14} />
                        {strings.ontology.entity.direction[item.direction]} ·{" "}
                        {humanizeIdentifier(item.relationship.relation_type)} · {item.peer_node.label}
                      </p>
                      <p className="m-0 text-sm text-muted">{item.relationship.summary}</p>
                      <p
                        className="m-0 text-xs text-muted"
                        title={item.relationship.permission_scope}
                      >
                        {humanizeScope(item.relationship.permission_scope)}
                      </p>
                      <p className="m-0 text-xs text-muted">
                        {strings.ontology.entity.ownerVerification(
                          humanizeIdentifier(item.relationship.metadata.owner_role)
                            ?? strings.identifiers.notRecorded,
                          humanizeIdentifier(item.relationship.metadata.verification_status)
                            ?? strings.identifiers.notRecorded,
                        )}
                      </p>
                      {item.relationship.metadata.evidence_refs.length > 0 ? (
                        <details className="text-xs text-muted">
                          <summary className="min-h-6 w-fit cursor-pointer">
                            {strings.ontology.entity.evidenceIds}
                          </summary>
                          <p className="mt-1 mb-0 font-mono break-words">
                            {item.relationship.metadata.evidence_refs.join(", ")}
                          </p>
                        </details>
                      ) : null}
                    </div>
                    <PeerNodeChip
                      label={item.peer_node.label}
                      nodeId={item.peer_node.node_id}
                      onNavigateToNode={onNavigateToNode}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="grid content-start gap-4">
            <div className="grid gap-1">
              <Eyebrow>{strings.ui.ontologyEntityDetailContent.governance}</Eyebrow>
              <h2 className="font-display m-0 text-xl text-ink">{strings.ui.ontologyEntityDetailContent.accessAndEvidence}</h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <section className="grid content-start gap-2">
                <Eyebrow>{strings.ui.common.requiredPermissions}</Eyebrow>
                <TagList items={detail.required_permissions} emptyLabel={strings.ui.ontologyEntityDetailContent.derivedReadScope} />
              </section>
              <section className="grid content-start gap-2">
                <Eyebrow>{strings.ui.common.evidence}</Eyebrow>
                <TagList items={detail.evidence_refs} emptyLabel={strings.ui.ontologyEntityDetailContent.nodeSummaryOnly} />
              </section>
            </div>
            <div aria-hidden="true" className="rule-hairline" />
            <div className="grid gap-4 sm:grid-cols-2">
              <section className="grid content-start gap-2">
                <Eyebrow>{strings.ui.ontologyEntityDetailContent.workflows}</Eyebrow>
                <RelatedNodeList
                  detail={detail}
                  emptyLabel={strings.ui.ontologyEntityDetailContent.noWorkflowRelation}
                  ids={detail.related_workflows}
                  onNavigateToNode={onNavigateToNode}
                />
              </section>
              <section className="grid content-start gap-2">
                <Eyebrow>{strings.ui.ontologyEntityDetailContent.approvals}</Eyebrow>
                <RelatedNodeList
                  detail={detail}
                  emptyLabel={strings.ui.ontologyEntityDetailContent.noApprovalRelation}
                  ids={detail.related_approvals}
                  onNavigateToNode={onNavigateToNode}
                />
              </section>
            </div>
            <div aria-hidden="true" className="rule-hairline" />
            <section className="grid content-start gap-2">
              <Eyebrow>{strings.ui.ontologyEntityDetailContent.agents}</Eyebrow>
              <RelatedNodeList
                detail={detail}
                emptyLabel={strings.ui.ontologyEntityDetailContent.noAgentRelation}
                ids={detail.related_agents}
                onNavigateToNode={onNavigateToNode}
              />
            </section>
          </Card>
        </div>
      </MaybeReveal>

      <MaybeReveal>
        <div className={`grid gap-4 ${isPage ? "lg:grid-cols-2" : ""}`}>
          <Card className="grid content-start gap-3">
            <Eyebrow>{strings.ui.ontologyEntityDetailContent.dataAccess}</Eyebrow>
            <div className="grid gap-3">
              {detail.data_access.map((item) => (
                <div className="flex items-start justify-between gap-3" key={item}>
                  <div className="grid gap-0.5">
                    <p className="m-0 text-sm font-medium text-ink">{item}</p>
                    <p className="m-0 text-xs text-muted">{strings.ui.ontologyEntityDetailContent.publicDemoSummaryOnly}</p>
                  </div>
                  <Database className="shrink-0 text-signal" size={16} />
                </div>
              ))}
            </div>
          </Card>

          <Card className="grid content-start gap-3">
            <Eyebrow>{strings.ui.ontologyEntityDetailContent.detailNotes}</Eyebrow>
            <div className="grid gap-2">
              {detail.detail_notes.map((note) => (
                <p className="m-0 text-sm text-muted" key={note}>
                  {note}
                </p>
              ))}
            </div>
          </Card>
        </div>
      </MaybeReveal>
    </div>
  );
}
