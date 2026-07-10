import type { OntologyNode, OntologyNodeType, OntologyRelationship } from "./ontology-demo";
import type { PlatformStatus } from "./platform-overview";

/**
 * Deterministic radial layout for the ontology graph.
 *
 * Node types are grouped into tiers around a shared center: organizations sit
 * innermost, operational entities on the middle ring, and governance /
 * evidence entities outermost. Within a ring, nodes are ordered by
 * (type, label, id) and spread evenly by angle — no randomness, so the same
 * API payload always produces the same picture and the module is unit-testable.
 */

export type OntologyGraphLayoutNode = {
  id: string;
  label: string;
  type: OntologyNodeType;
  status: PlatformStatus;
  tier: number;
  x: number;
  y: number;
};

export type OntologyGraphLayoutEdge = {
  id: string;
  sourceId: string;
  targetId: string;
  relationType: string;
  /** SVG path (quadratic curve bowed toward the center). */
  path: string;
  /** Approximate path length for stroke draw-in animations. */
  length: number;
};

export type OntologyGraphLayout = {
  width: number;
  height: number;
  nodes: OntologyGraphLayoutNode[];
  edges: OntologyGraphLayoutEdge[];
  /** Adjacency: node id -> ids of directly connected nodes. */
  neighbors: Map<string, Set<string>>;
};

export type OntologyGraphLayoutOptions = {
  width?: number;
  height?: number;
};

/** Tier per node type — lower tiers render closer to the center. */
export const ONTOLOGY_NODE_TIERS: Record<OntologyNodeType, number> = {
  organization: 0,
  asset: 1,
  process: 1,
  workflow: 1,
  system: 2,
  agent: 2,
  risk: 2,
  policy: 3,
  approval: 3,
  audit_event: 3,
};

const TIER_COUNT = 4;

function nodeSortKey(node: OntologyNode): string {
  return `${ONTOLOGY_NODE_TIERS[node.node_type]}:${node.node_type}:${node.label}:${node.node_id}`;
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

export function buildOntologyGraphLayout(
  nodes: OntologyNode[],
  relationships: OntologyRelationship[],
  options: OntologyGraphLayoutOptions = {},
): OntologyGraphLayout {
  const width = options.width ?? 720;
  const height = options.height ?? 560;
  const cx = width / 2;
  const cy = height / 2;
  const maxRadius = Math.min(width, height) / 2 - 56;

  const sorted = [...nodes].sort((left, right) =>
    nodeSortKey(left).localeCompare(nodeSortKey(right)),
  );

  const tiers = new Map<number, OntologyNode[]>();
  for (const node of sorted) {
    const tier = ONTOLOGY_NODE_TIERS[node.node_type];
    const bucket = tiers.get(tier) ?? [];
    bucket.push(node);
    tiers.set(tier, bucket);
  }

  const layoutNodes: OntologyGraphLayoutNode[] = [];
  const positionById = new Map<string, { x: number; y: number }>();

  for (const [tier, bucket] of Array.from(tiers.entries()).sort((a, b) => a[0] - b[0])) {
    // Tier 0 with a single node sits exactly at the center.
    const radius =
      tier === 0 && bucket.length === 1 ? 0 : maxRadius * ((tier + 1) / TIER_COUNT);
    // Offset each ring so nodes on adjacent rings do not align radially.
    const angleOffset = -Math.PI / 2 + (tier * Math.PI) / 7;

    bucket.forEach((node, index) => {
      const angle = angleOffset + (Math.PI * 2 * index) / bucket.length;
      const x = round(cx + Math.cos(angle) * radius);
      const y = round(cy + Math.sin(angle) * radius);

      positionById.set(node.node_id, { x, y });
      layoutNodes.push({
        id: node.node_id,
        label: node.label,
        type: node.node_type,
        status: node.status,
        tier,
        x,
        y,
      });
    });
  }

  const neighbors = new Map<string, Set<string>>();
  const addNeighbor = (from: string, to: string) => {
    const set = neighbors.get(from) ?? new Set<string>();
    set.add(to);
    neighbors.set(from, set);
  };

  const edges: OntologyGraphLayoutEdge[] = [];
  const sortedRelationships = [...relationships].sort((left, right) =>
    left.relationship_id.localeCompare(right.relationship_id),
  );

  for (const relationship of sortedRelationships) {
    const source = positionById.get(relationship.source_id);
    const target = positionById.get(relationship.target_id);

    if (!source || !target) {
      continue;
    }

    addNeighbor(relationship.source_id, relationship.target_id);
    addNeighbor(relationship.target_id, relationship.source_id);

    // Quadratic curve whose control point is pulled 18% toward the center,
    // so edges bow inward instead of crossing node labels.
    const mx = (source.x + target.x) / 2;
    const my = (source.y + target.y) / 2;
    const controlX = round(mx + (cx - mx) * 0.18);
    const controlY = round(my + (cy - my) * 0.18);

    const chord = Math.hypot(target.x - source.x, target.y - source.y);
    const viaControl =
      Math.hypot(controlX - source.x, controlY - source.y) +
      Math.hypot(target.x - controlX, target.y - controlY);
    const length = round((chord + viaControl) / 2);

    edges.push({
      id: relationship.relationship_id,
      sourceId: relationship.source_id,
      targetId: relationship.target_id,
      relationType: relationship.relation_type,
      path: `M ${source.x} ${source.y} Q ${controlX} ${controlY} ${target.x} ${target.y}`,
      length,
    });
  }

  return { width, height, nodes: layoutNodes, edges, neighbors };
}
