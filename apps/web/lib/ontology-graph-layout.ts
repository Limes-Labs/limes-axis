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
  /** Label baseline point, always one of the node's anchor slots. */
  labelX: number;
  labelY: number;
  /** SVG `text-anchor` for the slot: beside a node the label reads away from it. */
  labelAnchor: LabelAnchor;
  displayLabel: string;
  /** False when every slot is crowded; the label then appears on hover/focus. */
  labelVisible: boolean;
};

export type LabelAnchor = "start" | "middle" | "end";

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
  /**
   * The drawn content — nodes, hit targets and every label slot — plus a
   * margin. The graph opens fitted to this box, so the canvas is not left
   * with an empty band wherever the radial rings do not reach.
   */
  viewBox: GraphViewBox;
  nodes: OntologyGraphLayoutNode[];
  edges: OntologyGraphLayoutEdge[];
  /** Adjacency: node id -> ids of directly connected nodes. */
  neighbors: Map<string, Set<string>>;
};

export type OntologyGraphLayoutOptions = {
  width?: number;
  height?: number;
};

/** SVG viewBox rectangle in user (layout) coordinates. */
export type GraphViewBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

/** Maximum zoom-in factor relative to the full layout bounds. */
export const ONTOLOGY_GRAPH_MAX_ZOOM = 8;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** Keep `view` (already sized <= bounds) positioned fully inside `bounds`. */
function clampToBounds(view: GraphViewBox, bounds: GraphViewBox): GraphViewBox {
  return {
    x: round(clamp(view.x, bounds.x, bounds.x + bounds.width - view.width)),
    y: round(clamp(view.y, bounds.y, bounds.y + bounds.height - view.height)),
    width: round(view.width),
    height: round(view.height),
  };
}

/**
 * Zoom the viewBox around the point (cx, cy) in user coordinates.
 * `factor > 1` zooms in. The zoom level is clamped between the full bounds
 * (1x) and `ONTOLOGY_GRAPH_MAX_ZOOM`, preserving the bounds aspect ratio,
 * and the resulting view never leaves the bounds.
 */
export function zoomViewBox(
  viewBox: GraphViewBox,
  factor: number,
  cx: number,
  cy: number,
  bounds: GraphViewBox,
): GraphViewBox {
  const width = clamp(viewBox.width / factor, bounds.width / ONTOLOGY_GRAPH_MAX_ZOOM, bounds.width);
  const height = width * (bounds.height / bounds.width);
  const scale = width / viewBox.width;

  return clampToBounds(
    {
      x: cx - (cx - viewBox.x) * scale,
      y: cy - (cy - viewBox.y) * scale,
      width,
      height,
    },
    bounds,
  );
}

/**
 * Pan the viewBox by (dx, dy) in user coordinates, clamped so the view
 * stays inside the bounds. At full view this is a no-op.
 */
export function panViewBox(
  viewBox: GraphViewBox,
  dx: number,
  dy: number,
  bounds: GraphViewBox,
): GraphViewBox {
  return clampToBounds(
    { x: viewBox.x + dx, y: viewBox.y + dy, width: viewBox.width, height: viewBox.height },
    bounds,
  );
}

type ClientRect = { left: number; top: number; width: number; height: number };

/**
 * Pixels per user unit for an SVG drawn with the default
 * `preserveAspectRatio="xMidYMid meet"`: the view is scaled uniformly to fit
 * and centred, so the smaller axis ratio wins.
 */
export function viewBoxScale(rect: ClientRect, view: GraphViewBox): number {
  if (rect.width <= 0 || rect.height <= 0 || view.width <= 0 || view.height <= 0) {
    return 0;
  }

  return Math.min(rect.width / view.width, rect.height / view.height);
}

/** Map a client (pointer) position to user coordinates, accounting for letterboxing. */
export function clientPointToViewBox(
  rect: ClientRect,
  view: GraphViewBox,
  clientX: number,
  clientY: number,
): { x: number; y: number } | null {
  const scale = viewBoxScale(rect, view);
  if (scale === 0) {
    return null;
  }

  const offsetX = (rect.width - view.width * scale) / 2;
  const offsetY = (rect.height - view.height * scale) / 2;
  return {
    x: view.x + (clientX - rect.left - offsetX) / scale,
    y: view.y + (clientY - rect.top - offsetY) / scale,
  };
}

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

/** Half-diagonal of the diamond marker; the graph draws tier 0 three units larger. */
export const NODE_HALF = 9;
/** The watch/action status dot sits this far right of and above the node centre. */
export const STATUS_DOT_OFFSET = NODE_HALF + 2;
export const STATUS_DOT_RADIUS = 3;
/** Radius of a node's invisible pointer target. */
export const NODE_HIT_RADIUS = NODE_HALF + 12;
/** Approximate advance of the 13px monospace label face. */
const LABEL_CHAR_WIDTH = 8;
/** A label must keep this far from any other node's centre. */
const NODE_CLEARANCE = 14;
const VIEW_PADDING = 12;
/** Smallest opening view, so a sparse graph is not magnified past ~1.2x. */
export const MIN_VIEW_WIDTH = 560;
export const MIN_VIEW_HEIGHT = 460;

type Box = { left: number; right: number; top: number; bottom: number };

type LabelSlot = { dx: number; dy: number; anchor: LabelAnchor };

/** Baseline offsets around a node, each touching the marker. */
const DEFAULT_SLOT: LabelSlot = { dx: 0, dy: 26, anchor: "middle" };
const LABEL_SLOTS: readonly LabelSlot[] = [
  DEFAULT_SLOT,
  { dx: 0, dy: -17, anchor: "middle" },
  { dx: 17, dy: 5, anchor: "start" },
  { dx: -17, dy: 5, anchor: "end" },
  { dx: 12, dy: 24, anchor: "start" },
  { dx: -12, dy: 24, anchor: "end" },
  { dx: 12, dy: -13, anchor: "start" },
  { dx: -12, dy: -13, anchor: "end" },
];

function labelBox(x: number, y: number, anchor: LabelAnchor, textWidth: number): Box {
  const left = anchor === "start" ? x : anchor === "end" ? x - textWidth : x - textWidth / 2;
  return { left: left - 4, right: left + textWidth + 4, top: y - 14, bottom: y + 4 };
}

/**
 * One rectangle covering a node's hit circle and its label slot, so the node
 * and its label are a single, gap-free pointer target.
 */
export function nodeTargetBounds(node: OntologyGraphLayoutNode): GraphViewBox {
  const circle = squareBox(node.x, node.y, NODE_HIT_RADIUS);
  const label = labelBox(node.labelX, node.labelY, node.labelAnchor, node.displayLabel.length * LABEL_CHAR_WIDTH);
  const left = Math.min(circle.left, label.left);
  const top = Math.min(circle.top, label.top);
  return {
    x: round(left),
    y: round(top),
    width: round(Math.max(circle.right, label.right) - left),
    height: round(Math.max(circle.bottom, label.bottom) - top),
  };
}

function squareBox(x: number, y: number, half: number): Box {
  return { left: x - half, right: x + half, top: y - half, bottom: y + half };
}

function overlaps(a: Box, b: Box): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

/**
 * Prefer the slot that points away from the centre, so a label reads outward
 * into free space rather than across the inner rings. Ties keep slot order.
 */
function slotPreference(slot: LabelSlot, outward: { x: number; y: number }): number {
  const direction = slot.anchor === "start" ? 1 : slot.anchor === "end" ? -1 : 0;
  const vertical = slot.dy > 10 ? 1 : slot.dy < -10 ? -1 : 0;
  const length = Math.hypot(outward.x, outward.y) || 1;
  return (direction * outward.x + vertical * outward.y) / length;
}

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
        labelX: x,
        labelY: y + DEFAULT_SLOT.dy,
        labelAnchor: DEFAULT_SLOT.anchor,
        displayLabel: node.label.length > 28 ? `${node.label.slice(0, 27)}…` : node.label,
        labelVisible: false,
      });
    });
  }

  // Labels sit in one of a few slots touching their own node — below, above,
  // beside or diagonal — never in free space elsewhere on the canvas. (The old
  // search counted a node's own marker as an obstacle, so the slot under the
  // node always failed and labels drifted off behind leader lines.) A label
  // with no free slot is shown on hover/focus instead.
  const labelBoxes: Box[] = [];
  for (const node of layoutNodes) {
    const textWidth = node.displayLabel.length * LABEL_CHAR_WIDTH;
    const outward = { x: node.x - cx, y: node.y - cy };
    const slots = [...LABEL_SLOTS].sort(
      (left, right) => slotPreference(right, outward) - slotPreference(left, outward),
    );
    // Its own marker only has to stay uncovered (tier 0 draws 3 units larger).
    const ownHalf = node.tier === 0 ? NODE_HALF + 3 : NODE_HALF;
    for (const slot of slots) {
      const x = node.x + slot.dx;
      const y = node.y + slot.dy;
      const box = labelBox(x, y, slot.anchor, textWidth);
      const overlapsLabel = labelBoxes.some((other) => overlaps(box, other));
      const overlapsNode = layoutNodes.some((other) =>
        overlaps(box, squareBox(other.x, other.y, other.id === node.id ? ownHalf : NODE_CLEARANCE))
        // A status dot is part of the marker; a label must not cover it.
        || (other.status !== "ready"
          && overlaps(box, squareBox(other.x + STATUS_DOT_OFFSET, other.y - STATUS_DOT_OFFSET, STATUS_DOT_RADIUS))),
      );
      if (!overlapsLabel && !overlapsNode) {
        node.labelX = round(x);
        node.labelY = round(y);
        node.labelAnchor = slot.anchor;
        node.labelVisible = true;
        labelBoxes.push(box);
        break;
      }
    }
  }

  // Fit the opening view to what is drawn, including the below-node slot a
  // hidden label uses on focus, so nothing is clipped and no band is empty.
  const contentBoxes = layoutNodes.flatMap((node) => [
    squareBox(node.x, node.y, NODE_HIT_RADIUS),
    labelBox(node.labelX, node.labelY, node.labelAnchor, node.displayLabel.length * LABEL_CHAR_WIDTH),
  ]);
  const viewBox: GraphViewBox = contentBoxes.length === 0
    ? { x: 0, y: 0, width, height }
    : (() => {
        const left = Math.min(...contentBoxes.map((box) => box.left)) - VIEW_PADDING;
        const top = Math.min(...contentBoxes.map((box) => box.top)) - VIEW_PADDING;
        const right = Math.max(...contentBoxes.map((box) => box.right)) + VIEW_PADDING;
        const bottom = Math.max(...contentBoxes.map((box) => box.bottom)) + VIEW_PADDING;
        // A small graph is centred in a minimum-sized view rather than blown
        // up until a handful of nodes and labels fill the whole card.
        const viewWidth = Math.max(right - left, MIN_VIEW_WIDTH);
        const viewHeight = Math.max(bottom - top, MIN_VIEW_HEIGHT);
        return {
          x: round((left + right - viewWidth) / 2),
          y: round((top + bottom - viewHeight) / 2),
          width: round(viewWidth),
          height: round(viewHeight),
        };
      })();

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

  return { width, height, viewBox, nodes: layoutNodes, edges, neighbors };
}
