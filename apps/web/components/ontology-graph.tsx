"use client";

import { useEffect, useMemo, useState, type CSSProperties, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";

import { formatNodeType, type OntologyNode, type OntologyRelationship } from "@/lib/ontology-demo";
import {
  buildOntologyGraphLayout,
  type OntologyGraphLayoutNode,
} from "@/lib/ontology-graph-layout";
import { platformStatusLabel } from "@/lib/platform-overview";

const NODE_HALF = 9; // half-diagonal of the diamond marker

type OntologyGraphProps = {
  nodes: OntologyNode[];
  relationships: OntologyRelationship[];
  /** Highlighted node (e.g. the entity currently open). */
  selectedNodeId?: string;
};

function diamondPoints(node: OntologyGraphLayoutNode, half: number): string {
  return [
    `${node.x},${node.y - half}`,
    `${node.x + half},${node.y}`,
    `${node.x},${node.y + half}`,
    `${node.x - half},${node.y}`,
  ].join(" ");
}

/**
 * Interactive ontology graph. Diamond nodes echo the AxisMark glyph; edges
 * draw in with the brand `.draw-path` utility (reduced-motion renders them
 * complete). Hovering or focusing a node pings it and dims non-neighbors;
 * Enter or click navigates to the entity detail page.
 */
export function OntologyGraph({ nodes, relationships, selectedNodeId }: OntologyGraphProps) {
  const router = useRouter();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [drawn, setDrawn] = useState(false);

  const layout = useMemo(
    () => buildOntologyGraphLayout(nodes, relationships),
    [nodes, relationships],
  );

  useEffect(() => {
    // Flip after mount so the stroke draw-in transition runs.
    const frame = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const focusId = activeId ?? selectedNodeId ?? null;
  const focusNeighbors = focusId ? (layout.neighbors.get(focusId) ?? new Set<string>()) : null;

  const isDimmed = (id: string) =>
    Boolean(focusId && id !== focusId && !(focusNeighbors?.has(id) ?? false));
  const isEdgeActive = (sourceId: string, targetId: string) =>
    Boolean(focusId && (sourceId === focusId || targetId === focusId));

  function openNode(nodeId: string) {
    router.push(`/ontology/${nodeId}`);
  }

  function onNodeKeyDown(event: KeyboardEvent<SVGGElement>, nodeId: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openNode(nodeId);
    }
  }

  return (
    <svg
      className="h-auto w-full"
      data-testid="ontology-graph"
      role="group"
      aria-label={`Ontology graph with ${layout.nodes.length} nodes and ${layout.edges.length} relationships`}
      viewBox={`0 0 ${layout.width} ${layout.height}`}
    >
      {/* Edges */}
      <g fill="none">
        {layout.edges.map((edge) => {
          const active = isEdgeActive(edge.sourceId, edge.targetId);
          const muted = Boolean(focusId) && !active;

          return (
            <path
              className={`draw-path${drawn ? " drawn" : ""}`}
              d={edge.path}
              key={edge.id}
              stroke="rgb(var(--signal))"
              strokeOpacity={active ? 0.9 : muted ? 0.12 : 0.38}
              strokeWidth={active ? 2 : 1.25}
              style={{ "--path-length": `${Math.ceil(edge.length) + 2}` } as CSSProperties}
            >
              <title>{edge.relationType}</title>
            </path>
          );
        })}
      </g>

      {/* Nodes */}
      {layout.nodes.map((node) => {
        const focused = node.id === focusId;
        const dimmed = isDimmed(node.id);
        const fill = focused ? "rgb(var(--signal))" : "rgb(var(--ink))";

        return (
          <g
            className="cursor-pointer outline-none focus-visible:[&>polygon]:stroke-[rgb(var(--signal))] focus-visible:[&>polygon]:stroke-2"
            key={node.id}
            role="link"
            tabIndex={0}
            aria-label={`${node.label} — ${formatNodeType(node.type)}, ${platformStatusLabel(node.status)}`}
            opacity={dimmed ? 0.25 : 1}
            onBlur={() => setActiveId((current) => (current === node.id ? null : current))}
            onClick={() => openNode(node.id)}
            onFocus={() => setActiveId(node.id)}
            onKeyDown={(event) => onNodeKeyDown(event, node.id)}
            onMouseEnter={() => setActiveId(node.id)}
            onMouseLeave={() => setActiveId((current) => (current === node.id ? null : current))}
          >
            {/* Hover ping halo (echoes the AxisMark diamond) */}
            {focused ? (
              <polygon
                fill="none"
                points={diamondPoints(node, NODE_HALF + 3)}
                stroke="rgb(var(--signal))"
                strokeWidth={1.5}
                style={{
                  animation: "node-ping 1.4s cubic-bezier(0, 0, 0.2, 1) infinite",
                  transformOrigin: `${node.x}px ${node.y}px`,
                }}
              />
            ) : null}
            {/* Generous invisible hit target */}
            <circle cx={node.x} cy={node.y} fill="transparent" r={NODE_HALF + 12} />
            <polygon
              fill={fill}
              points={diamondPoints(node, node.tier === 0 ? NODE_HALF + 3 : NODE_HALF)}
              stroke="rgb(var(--bg))"
              strokeWidth={1.5}
            />
            {node.status !== "ready" ? (
              <circle
                cx={node.x + NODE_HALF + 2}
                cy={node.y - NODE_HALF - 2}
                fill={
                  node.status === "action_required" ? "rgb(var(--danger))" : "rgb(var(--warning))"
                }
                r={3}
              >
                <title>{platformStatusLabel(node.status)}</title>
              </circle>
            ) : null}
            <text
              className="font-mono"
              fill={focused ? "rgb(var(--signal))" : "rgb(var(--muted))"}
              fontSize={10.5}
              textAnchor="middle"
              x={node.x}
              y={node.y + NODE_HALF + 16}
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
