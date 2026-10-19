import { describe, expect, it } from "vitest";

import type { OntologyNode, OntologyRelationship } from "./ontology-demo";
import {
  buildOntologyGraphLayout,
  clientPointToViewBox,
  MIN_VIEW_HEIGHT,
  MIN_VIEW_WIDTH,
  NODE_HIT_RADIUS,
  nodeTargetBounds,
  ONTOLOGY_GRAPH_MAX_ZOOM,
  ONTOLOGY_NODE_TIERS,
  panViewBox,
  viewBoxScale,
  zoomViewBox,
  type GraphViewBox,
  type OntologyGraphLayoutNode,
} from "./ontology-graph-layout";

type Box = { left: number; right: number; top: number; bottom: number };

/** The marker half-diagonal (9) plus a small gap; farther reads as floating. */
const MAX_LABEL_GAP = 14;

/** The 13px mono label box, measured independently of the layout module. */
function labelBox(entry: OntologyGraphLayoutNode): Box {
  const width = entry.displayLabel.length * 8;
  const left = entry.labelAnchor === "start"
    ? entry.labelX
    : entry.labelAnchor === "end" ? entry.labelX - width : entry.labelX - width / 2;
  return { left: left - 4, right: left + width + 4, top: entry.labelY - 14, bottom: entry.labelY + 4 };
}

function square(x: number, y: number, half: number): Box {
  return { left: x - half, right: x + half, top: y - half, bottom: y + half };
}

function boxesOverlap(a: Box, b: Box): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

/** Distance from a node centre to the nearest point of a box (0 inside). */
function distanceToBox(x: number, y: number, box: Box): number {
  const dx = Math.max(box.left - x, 0, x - box.right);
  const dy = Math.max(box.top - y, 0, y - box.bottom);
  return Math.hypot(dx, dy);
}

function node(overrides: Partial<OntologyNode> & Pick<OntologyNode, "node_id" | "node_type">): OntologyNode {
  return {
    label: overrides.node_id,
    domain: "Quality",
    status: "ready",
    source_system: "MES",
    summary: "Test node",
    ...overrides,
  };
}

function relationship(
  overrides: Partial<OntologyRelationship> &
    Pick<OntologyRelationship, "relationship_id" | "source_id" | "target_id">,
): OntologyRelationship {
  return {
    relation_type: "governs",
    summary: "Test relationship",
    permission_scope: "ontology:read",
    metadata: {
      owner_role: "Quality Lead",
      source_adapter: "typedb",
      confidence: 0.9,
      evidence_refs: [],
      valid_from: "2026-01-01",
      valid_to: null,
      last_verified_at: "2026-07-01",
      verification_status: "verified",
    },
    ...overrides,
  };
}

const nodes: OntologyNode[] = [
  node({ node_id: "org_plant", node_type: "organization", label: "Ravenna Works" }),
  node({ node_id: "asset_line_2", node_type: "asset", label: "Line 2 Packaging" }),
  node({ node_id: "process_qa", node_type: "process", label: "Quality Assurance" }),
  node({ node_id: "workflow_delay", node_type: "workflow", label: "Supplier Delay Review" }),
  node({ node_id: "agent_supply", node_type: "agent", label: "Supply Risk Agent" }),
  node({ node_id: "system_mes", node_type: "system", label: "MES" }),
  node({ node_id: "risk_batch", node_type: "risk", label: "Batch Risk", status: "watch" }),
  node({ node_id: "policy_egress", node_type: "policy", label: "Egress Policy" }),
  node({ node_id: "approval_expedite", node_type: "approval", label: "Expedite Approval" }),
  node({ node_id: "audit_evt", node_type: "audit_event", label: "Audit Event" }),
];

const relationships: OntologyRelationship[] = [
  relationship({ relationship_id: "rel_1", source_id: "org_plant", target_id: "asset_line_2" }),
  relationship({ relationship_id: "rel_2", source_id: "asset_line_2", target_id: "process_qa" }),
  relationship({ relationship_id: "rel_3", source_id: "policy_egress", target_id: "agent_supply" }),
  relationship({ relationship_id: "rel_4", source_id: "workflow_delay", target_id: "approval_expedite" }),
];

describe("buildOntologyGraphLayout", () => {
  it("is deterministic regardless of input order", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);
    const shuffled = buildOntologyGraphLayout(
      [...nodes].reverse(),
      [...relationships].reverse(),
    );

    expect(shuffled).toEqual(layout);
    expect(buildOntologyGraphLayout(nodes, relationships)).toEqual(layout);
  });

  it("positions every node inside the viewBox with a margin", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);

    expect(layout.nodes).toHaveLength(nodes.length);
    for (const positioned of layout.nodes) {
      expect(positioned.x).toBeGreaterThan(0);
      expect(positioned.x).toBeLessThan(layout.width);
      expect(positioned.y).toBeGreaterThan(0);
      expect(positioned.y).toBeLessThan(layout.height);
    }
  });

  it("places a lone organization at the center and outer tiers farther out", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);
    const cx = layout.width / 2;
    const cy = layout.height / 2;
    const distance = (id: string) => {
      const positioned = layout.nodes.find((entry) => entry.id === id);
      if (!positioned) {
        throw new Error(`missing node ${id}`);
      }
      return Math.hypot(positioned.x - cx, positioned.y - cy);
    };

    expect(distance("org_plant")).toBe(0);
    expect(distance("asset_line_2")).toBeGreaterThan(0);
    expect(distance("policy_egress")).toBeGreaterThan(distance("asset_line_2"));
    expect(distance("agent_supply")).toBeGreaterThan(distance("asset_line_2"));
  });

  it("assigns tiers from the node type map", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);

    for (const positioned of layout.nodes) {
      expect(positioned.tier).toBe(ONTOLOGY_NODE_TIERS[positioned.type]);
    }
  });

  it("anchors every label to its own node and keeps it clear of labels and other markers", () => {
    const populated = Array.from({ length: 18 }, (_, index) => node({
      node_id: `node_${index}`,
      node_type: nodes[index % nodes.length].node_type,
      label: `Supplier Delay Review Batch ${index}`,
    }));
    const layout = buildOntologyGraphLayout(populated, []);
    const visible = layout.nodes.filter((entry) => entry.labelVisible);
    // Most labels fit beside their node; the rest wait for hover/focus rather
    // than drifting to a distant free spot.
    expect(visible.length).toBeGreaterThanOrEqual(populated.length / 2);

    const boxes = visible.map(labelBox);
    boxes.forEach((box, index) => {
      const owner = visible[index];
      // Anchored: the label's box comes within a few units of its own marker.
      expect(distanceToBox(owner.x, owner.y, box)).toBeLessThanOrEqual(MAX_LABEL_GAP);
      for (const other of boxes.slice(index + 1)) {
        expect(boxesOverlap(box, other)).toBe(false);
      }
      for (const marker of layout.nodes) {
        if (marker.id === owner.id) continue;
        expect(boxesOverlap(box, square(marker.x, marker.y, 14))).toBe(false);
      }
    });
  });

  it("never draws a leader line: labels sit in a slot touching the node", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);
    for (const entry of layout.nodes) {
      expect(distanceToBox(entry.x, entry.y, labelBox(entry))).toBeLessThanOrEqual(MAX_LABEL_GAP);
      expect(["start", "middle", "end"]).toContain(entry.labelAnchor);
    }
    // In the reference-sized graph every label fits beside its node.
    expect(layout.nodes.every((entry) => entry.labelVisible)).toBe(true);
  });

  it("defers crowded labels to node focus without dropping their full names", () => {
    const crowded = Array.from({ length: 60 }, (_, index) => node({
      node_id: `node_${index}`,
      node_type: nodes[index % nodes.length].node_type,
      label: `Supplier Delay Review Batch ${index}`,
    }));
    const layout = buildOntologyGraphLayout(crowded, []);
    expect(layout.nodes.some((entry) => !entry.labelVisible)).toBe(true);
    expect(layout.nodes).toHaveLength(crowded.length);
    expect(layout.nodes.map((entry) => entry.label).sort()).toEqual(crowded.map((entry) => entry.label).sort());
    const visible = layout.nodes.filter((entry) => entry.labelVisible).map(labelBox);
    visible.forEach((box, index) => {
      for (const other of visible.slice(index + 1)) {
        expect(boxesOverlap(box, other)).toBe(false);
      }
    });
    // A deferred label still has an anchored slot for when it is focused.
    for (const entry of layout.nodes.filter((item) => !item.labelVisible)) {
      expect(entry.labelAnchor).toBe("middle");
      expect(entry.labelX).toBe(entry.x);
      expect(entry.labelY).toBeGreaterThan(entry.y);
      expect(distanceToBox(entry.x, entry.y, labelBox(entry))).toBeLessThanOrEqual(MAX_LABEL_GAP);
    }
  });

  it("fits the opening view to the drawn content so no side of the canvas is empty", () => {
    for (const payload of [nodes, nodes.slice(0, 3)]) {
      const layout = buildOntologyGraphLayout(payload, []);
      const content = layout.nodes.flatMap((entry) => [square(entry.x, entry.y, NODE_HIT_RADIUS), labelBox(entry)]);
      const left = Math.min(...content.map((box) => box.left));
      const right = Math.max(...content.map((box) => box.right));
      const top = Math.min(...content.map((box) => box.top));
      const bottom = Math.max(...content.map((box) => box.bottom));
      const { viewBox } = layout;

      // Everything drawn is inside the view…
      expect(viewBox.x).toBeLessThanOrEqual(left);
      expect(viewBox.y).toBeLessThanOrEqual(top);
      expect(viewBox.x + viewBox.width).toBeGreaterThanOrEqual(right);
      expect(viewBox.y + viewBox.height).toBeGreaterThanOrEqual(bottom);
      // …centred, so neither side carries an empty band…
      const [marginLeft, marginTop, marginRight, marginBottom] = [
        left - viewBox.x, top - viewBox.y, viewBox.x + viewBox.width - right, viewBox.y + viewBox.height - bottom,
      ];
      expect(Math.abs(marginLeft - marginRight)).toBeLessThan(0.05);
      expect(Math.abs(marginTop - marginBottom)).toBeLessThan(0.05);
      // …and only padded beyond the content when it is smaller than the minimum view.
      if (viewBox.width > MIN_VIEW_WIDTH) expect(marginLeft).toBeLessThanOrEqual(16);
      if (viewBox.height > MIN_VIEW_HEIGHT) expect(marginTop).toBeLessThanOrEqual(16);
      expect(viewBox.width).toBeGreaterThanOrEqual(MIN_VIEW_WIDTH);
      expect(viewBox.height).toBeGreaterThanOrEqual(MIN_VIEW_HEIGHT);
    }
  });

  it("falls back to the full canvas for an empty payload", () => {
    const layout = buildOntologyGraphLayout([], []);
    expect(layout.viewBox).toEqual({ x: 0, y: 0, width: layout.width, height: layout.height });
  });

  it("builds edge paths and symmetric neighbor sets from relationships", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);

    expect(layout.edges).toHaveLength(relationships.length);
    for (const edge of layout.edges) {
      expect(edge.path).toMatch(/^M [\d.-]+ [\d.-]+ Q [\d.-]+ [\d.-]+ [\d.-]+ [\d.-]+$/);
      expect(edge.length).toBeGreaterThan(0);
      expect(layout.neighbors.get(edge.sourceId)?.has(edge.targetId)).toBe(true);
      expect(layout.neighbors.get(edge.targetId)?.has(edge.sourceId)).toBe(true);
    }
  });

  it("skips relationships that reference unknown nodes", () => {
    const layout = buildOntologyGraphLayout(nodes, [
      ...relationships,
      relationship({ relationship_id: "rel_ghost", source_id: "org_plant", target_id: "missing" }),
    ]);

    expect(layout.edges.map((edge) => edge.id)).toEqual(["rel_1", "rel_2", "rel_3", "rel_4"]);
  });

  it("handles an empty payload", () => {
    const layout = buildOntologyGraphLayout([], []);

    expect(layout.nodes).toEqual([]);
    expect(layout.edges).toEqual([]);
    expect(layout.neighbors.size).toBe(0);
  });
});

const bounds: GraphViewBox = { x: 0, y: 0, width: 720, height: 560 };

describe("zoomViewBox", () => {
  it("zooms in around the given point, keeping it at the same viewport fraction", () => {
    const zoomed = zoomViewBox(bounds, 2, 180, 140, bounds);

    expect(zoomed.width).toBeCloseTo(360);
    expect(zoomed.height).toBeCloseTo(280);
    // (180, 140) sat at 25% of the old view; it stays at 25% of the new one.
    expect((180 - zoomed.x) / zoomed.width).toBeCloseTo(0.25);
    expect((140 - zoomed.y) / zoomed.height).toBeCloseTo(0.25);
  });

  it("preserves the bounds aspect ratio", () => {
    const zoomed = zoomViewBox(bounds, 3, 100, 100, bounds);

    expect(zoomed.width / zoomed.height).toBeCloseTo(bounds.width / bounds.height);
  });

  it("clamps zoom-out at the full bounds", () => {
    const zoomedIn = zoomViewBox(bounds, 2, 360, 280, bounds);
    const zoomedOut = zoomViewBox(zoomedIn, 0.1, 360, 280, bounds);

    expect(zoomedOut).toEqual(bounds);
  });

  it("clamps zoom-in at the maximum zoom factor", () => {
    const zoomed = zoomViewBox(bounds, 1000, 360, 280, bounds);

    expect(zoomed.width).toBeCloseTo(bounds.width / ONTOLOGY_GRAPH_MAX_ZOOM);
    expect(zoomed.height).toBeCloseTo(bounds.height / ONTOLOGY_GRAPH_MAX_ZOOM);
  });

  it("keeps the view inside the bounds when zooming near an edge", () => {
    const zoomedIn = zoomViewBox(bounds, 4, 700, 550, bounds);
    const zoomedOut = zoomViewBox(zoomedIn, 0.5, 700, 550, bounds);

    for (const view of [zoomedIn, zoomedOut]) {
      expect(view.x).toBeGreaterThanOrEqual(bounds.x);
      expect(view.y).toBeGreaterThanOrEqual(bounds.y);
      expect(view.x + view.width).toBeLessThanOrEqual(bounds.x + bounds.width);
      expect(view.y + view.height).toBeLessThanOrEqual(bounds.y + bounds.height);
    }
  });
});

describe("panViewBox", () => {
  it("shifts the view by the given delta", () => {
    const zoomed = zoomViewBox(bounds, 2, 360, 280, bounds);
    const panned = panViewBox(zoomed, 40, -30, bounds);

    expect(panned.x).toBeCloseTo(zoomed.x + 40);
    expect(panned.y).toBeCloseTo(zoomed.y - 30);
    expect(panned.width).toBe(zoomed.width);
    expect(panned.height).toBe(zoomed.height);
  });

  it("clamps panning at the bounds edges", () => {
    const zoomed = zoomViewBox(bounds, 2, 360, 280, bounds);
    const pannedFar = panViewBox(zoomed, 10_000, 10_000, bounds);

    expect(pannedFar.x).toBeCloseTo(bounds.x + bounds.width - zoomed.width);
    expect(pannedFar.y).toBeCloseTo(bounds.y + bounds.height - zoomed.height);

    const pannedBack = panViewBox(pannedFar, -10_000, -10_000, bounds);
    expect(pannedBack.x).toBe(bounds.x);
    expect(pannedBack.y).toBe(bounds.y);
  });

  it("is a no-op at full view", () => {
    expect(panViewBox(bounds, 50, 50, bounds)).toEqual(bounds);
  });
});

describe("client to viewBox mapping", () => {
  const view: GraphViewBox = { x: 100, y: 50, width: 400, height: 200 };

  it("scales by the limiting axis, as preserveAspectRatio meet does", () => {
    // 800x200 px for a 2:1 view: height limits, so 1 unit = 1 px.
    expect(viewBoxScale({ left: 0, top: 0, width: 800, height: 200 }, view)).toBe(1);
    expect(viewBoxScale({ left: 0, top: 0, width: 200, height: 400 }, view)).toBe(0.5);
    expect(viewBoxScale({ left: 0, top: 0, width: 0, height: 400 }, view)).toBe(0);
  });

  it("gives each labelled node one gap-free target over the node and its label", () => {
    const layout = buildOntologyGraphLayout(nodes, relationships);
    for (const entry of layout.nodes) {
      const target = nodeTargetBounds(entry);
      const label = labelBox(entry);
      expect(target.x).toBeLessThanOrEqual(Math.min(entry.x - NODE_HIT_RADIUS, label.left) + 0.01);
      expect(target.y).toBeLessThanOrEqual(Math.min(entry.y - NODE_HIT_RADIUS, label.top) + 0.01);
      expect(target.x + target.width).toBeGreaterThanOrEqual(Math.max(entry.x + NODE_HIT_RADIUS, label.right) - 0.01);
      expect(target.y + target.height).toBeGreaterThanOrEqual(Math.max(entry.y + NODE_HIT_RADIUS, label.bottom) - 0.01);
    }
  });

  it("maps pointer positions through the centred letterbox", () => {
    const rect = { left: 10, top: 20, width: 800, height: 200 };
    // The 400px-wide drawing is centred in 800px: 200px of letterbox each side.
    expect(clientPointToViewBox(rect, view, 10 + 200, 20)).toEqual({ x: 100, y: 50 });
    expect(clientPointToViewBox(rect, view, 10 + 400, 20 + 100)).toEqual({ x: 300, y: 150 });
    expect(clientPointToViewBox({ left: 0, top: 0, width: 0, height: 0 }, view, 5, 5)).toBeNull();
  });
});
