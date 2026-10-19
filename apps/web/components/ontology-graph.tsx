"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { Maximize2, Minus, Plus } from "lucide-react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatNodeType, type OntologyNode, type OntologyRelationship } from "@/lib/ontology-demo";
import {
  buildOntologyGraphLayout,
  clientPointToViewBox,
  NODE_HALF,
  NODE_HIT_RADIUS,
  nodeTargetBounds,
  panViewBox,
  STATUS_DOT_OFFSET,
  STATUS_DOT_RADIUS,
  viewBoxScale,
  zoomViewBox,
  type GraphViewBox,
  type OntologyGraphLayoutNode,
} from "@/lib/ontology-graph-layout";
import { buildOntologyEntityRoute } from "@/lib/ontology-routes";
import { platformStatusLabel } from "@/lib/platform-overview";
import { useStrings } from "@/providers/locale-provider";

const WHEEL_ZOOM_SENSITIVITY = 0.0022;
const BUTTON_ZOOM_STEP = 1.4;
const DRAG_THRESHOLD_PX = 4;
/** Below this the graph scrolls inside its region rather than shrink labels. */
const GRAPH_MIN_WIDTH = 560;

type OntologyGraphProps = {
  nodes: OntologyNode[];
  relationships: OntologyRelationship[];
  /** Highlighted node (e.g. the entity currently open). */
  selectedNodeId?: string;
  /** Invoked on click/Enter on a node; defaults to navigating to the entity page. */
  onNodeActivate?: (nodeId: string, trigger: SVGGElement) => void;
};

function diamondPoints(node: OntologyGraphLayoutNode, half: number): string {
  return [
    `${node.x},${node.y - half}`,
    `${node.x + half},${node.y}`,
    `${node.x},${node.y + half}`,
    `${node.x - half},${node.y}`,
  ].join(" ");
}

function GraphControlButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button aria-label={label} className="icon-button" onClick={onClick} type="button">
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="left">{label}</TooltipContent>
    </Tooltip>
  );
}

/**
 * Interactive ontology graph. Diamond nodes echo the AxisMark glyph; edges
 * draw in with the brand `.draw-path` utility (reduced-motion renders them
 * complete). Hovering or focusing a node highlights it and dims non-neighbors;
 * Enter or click activates the node (slide-over detail or navigation).
 * The view zooms with the wheel (cursor-centered) or the +/− controls and
 * pans by dragging — all via viewBox math, so no new animations run.
 */
export function OntologyGraph({
  nodes,
  relationships,
  selectedNodeId,
  onNodeActivate,
}: OntologyGraphProps) {
  const strings = useStrings();
  const router = useRouter();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [drawn, setDrawn] = useState(false);

  const layout = useMemo(
    () => buildOntologyGraphLayout(nodes, relationships),
    [nodes, relationships],
  );
  // The view opens fitted to the drawn content, not the fixed layout canvas.
  const bounds = layout.viewBox;

  const svgRef = useRef<SVGSVGElement | null>(null);
  const [viewBox, setViewBox] = useState<GraphViewBox>(bounds);
  const [lastBounds, setLastBounds] = useState<GraphViewBox>(bounds);
  const [isPanning, setIsPanning] = useState(false);
  const panStateRef = useRef<{
    pointerId: number;
    lastX: number;
    lastY: number;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);
  const suppressActivateRef = useRef(false);

  // Reset the view when the layout (and thus its bounds) changes —
  // state adjustment during render, per the React docs, not an effect.
  if (lastBounds !== bounds) {
    setLastBounds(bounds);
    setViewBox(bounds);
  }

  useEffect(() => {
    // Flip after mount so the stroke draw-in transition runs.
    const frame = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) {
      return;
    }

    // Native listener: React's onWheel cannot preventDefault page scroll.
    const onWheel = (event: WheelEvent) => {
      // Only an explicit zoom gesture is intercepted — ctrl/⌘ + wheel, which is
      // also what a trackpad pinch emits. A bare wheel must still scroll the
      // page, or the graph swallows scrolling for the whole route.
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }

      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      const factor = Math.exp(-event.deltaY * WHEEL_ZOOM_SENSITIVITY);
      setViewBox((current) => {
        const point = clientPointToViewBox(rect, current, event.clientX, event.clientY);
        return point ? zoomViewBox(current, factor, point.x, point.y, bounds) : current;
      });
    };

    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [bounds]);

  const focusId = activeId ?? selectedNodeId ?? null;
  const isZoomed = viewBox.width < bounds.width;
  const focusNeighbors = focusId ? (layout.neighbors.get(focusId) ?? new Set<string>()) : null;

  const isDimmed = (id: string) =>
    Boolean(focusId && id !== focusId && !(focusNeighbors?.has(id) ?? false));
  const isEdgeActive = (sourceId: string, targetId: string) =>
    Boolean(focusId && (sourceId === focusId || targetId === focusId));

  function openNode(nodeId: string, trigger: SVGGElement) {
    if (suppressActivateRef.current) {
      return;
    }

    if (onNodeActivate) {
      onNodeActivate(nodeId, trigger);
      return;
    }

    router.push(buildOntologyEntityRoute(nodeId));
  }

  function onNodeKeyDown(event: KeyboardEvent<SVGGElement>, nodeId: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openNode(nodeId, event.currentTarget);
    }
  }

  function zoomBy(factor: number) {
    setViewBox((current) =>
      zoomViewBox(
        current,
        factor,
        current.x + current.width / 2,
        current.y + current.height / 2,
        bounds,
      ),
    );
  }

  function onPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) {
      return;
    }

    panStateRef.current = {
      pointerId: event.pointerId,
      lastX: event.clientX,
      lastY: event.clientY,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
  }

  function onPointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const state = panStateRef.current;
    if (!state || state.pointerId !== event.pointerId) {
      return;
    }

    if (
      !state.moved &&
      Math.hypot(event.clientX - state.startX, event.clientY - state.startY) < DRAG_THRESHOLD_PX
    ) {
      return;
    }

    if (!state.moved) {
      state.moved = true;
      suppressActivateRef.current = true;
      setIsPanning(true);
      event.currentTarget.setPointerCapture(event.pointerId);
    }

    const scale = viewBoxScale(event.currentTarget.getBoundingClientRect(), viewBox);
    if (scale === 0) {
      return;
    }

    const dx = (state.lastX - event.clientX) / scale;
    const dy = (state.lastY - event.clientY) / scale;
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    setViewBox((current) => panViewBox(current, dx, dy, bounds));
  }

  function onPointerEnd(event: ReactPointerEvent<SVGSVGElement>) {
    const state = panStateRef.current;
    if (!state || state.pointerId !== event.pointerId) {
      return;
    }

    panStateRef.current = null;
    setIsPanning(false);

    if (state.moved) {
      // Let the click that follows pointerup pass before re-enabling activation.
      setTimeout(() => {
        suppressActivateRef.current = false;
      }, 0);
    }
  }

  return (
    <div className="relative min-w-0">
      <div className="max-h-[560px] overflow-auto rounded-xl" tabIndex={0} role="region" aria-label={strings.clarity.graphRegion}>
        <svg
          // Full view uses native scrolling. Once zoomed, touch drags must pan
          // the viewBox to reach nodes outside it; Reset restores native scroll.
          // Fills the card width and keeps the content's aspect ratio up to the
          // region's height; the default `meet` centres the fitted graph.
          className={`mx-auto block h-auto w-full max-h-[560px] ${isZoomed ? "touch-none" : "touch-auto"} select-none ${isPanning ? "cursor-grabbing" : "cursor-grab"}`}
          style={{ aspectRatio: `${bounds.width} / ${bounds.height}`, minWidth: GRAPH_MIN_WIDTH }}
          data-testid="ontology-graph"
          ref={svgRef}
          role="group"
          aria-label={strings.ui.ontologyGraph.graphLabel(layout.nodes.length, layout.edges.length)}
          viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
          onPointerCancel={onPointerEnd}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
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
                aria-label={`${node.label} — ${formatNodeType(node.type)}, ${platformStatusLabel(node.status, strings)}`}
                opacity={dimmed ? 0.25 : 1}
                onBlur={() => setActiveId((current) => (current === node.id ? null : current))}
                onClick={(event) => openNode(node.id, event.currentTarget)}
                onFocus={() => setActiveId(node.id)}
                onKeyDown={(event) => onNodeKeyDown(event, node.id)}
                onMouseEnter={() => setActiveId(node.id)}
                onMouseLeave={() => setActiveId((current) => (current === node.id ? null : current))}
              >
                {/* Focus outline echoes the AxisMark diamond. */}
                {focused ? (
                  <polygon
                    fill="none"
                    points={diamondPoints(node, NODE_HALF + 3)}
                    stroke="rgb(var(--signal))"
                    strokeWidth={1.5}
                  />
                ) : null}
                {/* Generous invisible hit target; with a label shown it spans
                    node and label, so there is no dead gap between them. */}
                <circle cx={node.x} cy={node.y} fill="transparent" r={NODE_HIT_RADIUS} />
                {node.labelVisible || focused ? (() => {
                  const target = nodeTargetBounds(node);
                  return <rect data-node-target fill="transparent" height={target.height} width={target.width} x={target.x} y={target.y} />;
                })() : null}
                <polygon
                  fill={fill}
                  points={diamondPoints(node, node.tier === 0 ? NODE_HALF + 3 : NODE_HALF)}
                  stroke="rgb(var(--bg))"
                  strokeWidth={1.5}
                />
                {node.status !== "ready" ? (
                  <circle
                    cx={node.x + STATUS_DOT_OFFSET}
                    cy={node.y - STATUS_DOT_OFFSET}
                    fill={
                      node.status === "action_required" ? "rgb(var(--danger))" : "rgb(var(--warning))"
                    }
                    r={STATUS_DOT_RADIUS}
                  >
                    <title>{platformStatusLabel(node.status, strings)}</title>
                  </circle>
                ) : null}
                {/* Labels sit in a slot touching their node, so no leader line;
                    the label is part of the node's target, so it opens it too. */}
                {node.labelVisible || focused ? <text
                  className="font-mono"
                  data-label-anchor={node.labelAnchor}
                  fill={focused ? "rgb(var(--signal))" : "rgb(var(--muted))"}
                  fontSize={13}
                  textAnchor={node.labelAnchor}
                  x={node.labelX}
                  y={node.labelY}
                  stroke="rgb(var(--bg))"
                  strokeWidth={4}
                  paintOrder="stroke"
                >
                  <title>{node.label}</title>
                  {node.displayLabel}
                </text> : null}
              </g>
            );
          })}
        </svg>
      </div>

      <div
        aria-label={strings.ontology.graph.controlsLabel}
        className="absolute top-2 right-2 flex flex-col gap-1.5"
        role="group"
      >
        <TooltipProvider delayDuration={150}>
          <GraphControlButton
            label={strings.ontology.graph.zoomIn}
            onClick={() => zoomBy(BUTTON_ZOOM_STEP)}
          >
            <Plus aria-hidden="true" size={15} />
          </GraphControlButton>
          <GraphControlButton
            label={strings.ontology.graph.zoomOut}
            onClick={() => zoomBy(1 / BUTTON_ZOOM_STEP)}
          >
            <Minus aria-hidden="true" size={15} />
          </GraphControlButton>
          <GraphControlButton
            label={strings.ontology.graph.resetView}
            onClick={() => setViewBox(bounds)}
          >
            <Maximize2 aria-hidden="true" size={15} />
          </GraphControlButton>
        </TooltipProvider>
      </div>
    </div>
  );
}
