"use client";

import { startTransition, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { LandingGraphDTO } from "@/lib/api";

const WIDTH = 1180;
const HEIGHT = 920;
const CENTER_X = WIDTH / 2 - 34;
const CENTER_Y = HEIGHT / 2 + 6;
const GRAPH_RADIUS = 414;
const LABEL_COUNT = 3;
const CLUSTER_COUNT = 8;
const FRAME_INTERVAL_MS = 50;
const PALETTE = [
  "#7a1c1c",
  "#2f6b47",
  "#8d6b14",
  "#4f7397",
  "#7b5a89",
  "#74833f",
  "#b86a42",
  "#4f9b8a",
];

type Props = {
  graph: LandingGraphDTO;
};

type Vec2 = {
  x: number;
  y: number;
};

type LayoutNode = LandingGraphDTO["nodes"][number] & {
  index: number;
  degree: number;
  cluster: number;
  clusterSize: number;
  x: number;
  y: number;
  phase: number;
  drift: number;
  color: string;
};

type FrameNode = LayoutNode & {
  drawX: number;
  drawY: number;
  radius: number;
  glowRadius: number;
};

type Layout = {
  nodes: LayoutNode[];
  edges: LandingGraphDTO["edges"];
  neighbors: Map<string, Set<string>>;
  clusterCenters: Vec2[];
};

export function SemanticGraphCanvas({ graph }: Props) {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const layoutRef = useRef<Layout>(createLayout(graph));
  const frameNodesRef = useRef<FrameNode[]>([]);
  const hoveredIdRef = useRef<string | null>(null);
  const hoveredNodeRef = useRef<FrameNode | null>(null);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const [hoveredNode, setHoveredNode] = useState<FrameNode | null>(null);

  useEffect(() => {
    layoutRef.current = createLayout(graph);
  }, [graph]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d", { alpha: true, desynchronized: true });
    if (!context) return;

    let frame = 0;
    let lastPaint = 0;

    const render = (now: number) => {
      frame = window.requestAnimationFrame(render);
      if (now - lastPaint < FRAME_INTERVAL_MS) return;
      lastPaint = now;

      paintScene(context, canvas, layoutRef.current, now, hoveredIdRef.current, frameNodesRef);
    };

    frame = window.requestAnimationFrame(render);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function openPaper(paperId: string) {
    startTransition(() => {
      router.push(`/papers/${encodeURIComponent(paperId)}`);
    });
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const point = canvasPoint(event);
    pointerRef.current = point;
    const hit = findHoveredNode(point, frameNodesRef.current);
    if (hit?.id !== hoveredIdRef.current) {
      hoveredIdRef.current = hit?.id ?? null;
      hoveredNodeRef.current = hit ?? null;
      setHoveredNode(hit ?? null);
    }
  }

  function handlePointerLeave() {
    pointerRef.current = null;
    hoveredIdRef.current = null;
    hoveredNodeRef.current = null;
    setHoveredNode(null);
  }

  function handleClick() {
    if (hoveredIdRef.current) openPaper(hoveredIdRef.current);
  }

  return (
    <section className="relative mx-1 mt-2 mb-10 overflow-visible sm:mx-4 lg:mx-6 xl:mx-0 xl:-ml-12 xl:mr-0 xl:mt-18 xl:w-[min(1100px,calc(100%+72px))] xl:max-w-[1100px] xl:self-stretch">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_48%,rgba(255,255,255,0.56),transparent_22%),radial-gradient(circle_at_48%_50%,rgba(245,231,224,0.96),transparent_44%),radial-gradient(circle_at_72%_26%,rgba(122,28,28,0.11),transparent_18%),radial-gradient(circle_at_28%_68%,rgba(47,107,71,0.09),transparent_19%),radial-gradient(circle_at_55%_78%,rgba(79,115,151,0.08),transparent_18%)] blur-3xl" />
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={WIDTH}
          height={HEIGHT}
          className="aspect-[118/92] h-auto w-full max-w-[1120px] cursor-pointer overflow-visible"
          aria-label="Semantic graph of related papers"
          onPointerMove={handlePointerMove}
          onPointerLeave={handlePointerLeave}
          onClick={handleClick}
        />

        {hoveredNode ? (
          <div className="pointer-events-none absolute left-5 top-5 max-w-[360px] border border-white/70 bg-paper/92 px-4 py-3 shadow-[0_18px_55px_rgba(28,24,21,0.12)] backdrop-blur-sm">
            <div className="font-sans text-[11px] font-semibold tracking-[0.16em] uppercase text-burgundy">
              {hoveredNode.venue ?? "OpenReview"}
            </div>
            <div className="mt-1 font-serif text-[19px] leading-6 text-ink">
              {hoveredNode.title}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-sans text-[12px] text-muted-2">
              <span>{hoveredNode.verdict}</span>
              <span>{hoveredNode.degree} links</span>
              <span>cluster {hoveredNode.cluster + 1}</span>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function createLayout(graph: LandingGraphDTO): Layout {
  const neighbors = new Map<string, Set<string>>();
  const degrees = new Map<string, number>();
  const weights = new Map<string, Map<string, number>>();

  for (const node of graph.nodes) {
    neighbors.set(node.id, new Set());
    degrees.set(node.id, 0);
    weights.set(node.id, new Map());
  }

  for (const edge of graph.edges) {
    neighbors.get(edge.source)?.add(edge.target);
    neighbors.get(edge.target)?.add(edge.source);
    weights.get(edge.source)?.set(edge.target, edge.weight);
    weights.get(edge.target)?.set(edge.source, edge.weight);
    degrees.set(edge.source, (degrees.get(edge.source) ?? 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) ?? 0) + 1);
  }

  const anchors = pickAnchors(graph.nodes, degrees, neighbors);
  const clusterAssignments = assignClusters(graph.nodes, anchors, neighbors);
  const clusterCenters = buildClusterCenters(Math.max(anchors.length, 1));
  const clusterBuckets = new Map<number, LandingGraphDTO["nodes"]>();

  for (const node of graph.nodes) {
    const cluster = clusterAssignments.get(node.id) ?? 0;
    const bucket = clusterBuckets.get(cluster) ?? [];
    bucket.push(node);
    clusterBuckets.set(cluster, bucket);
  }

  const clusterSlots = new Map<string, number>();
  for (const bucket of clusterBuckets.values()) {
    const ranked = [...bucket].sort(
      (left, right) => (degrees.get(right.id) ?? 0) - (degrees.get(left.id) ?? 0),
    );
    ranked.forEach((node, index) => {
      clusterSlots.set(node.id, index);
    });
  }

  const nodes: LayoutNode[] = graph.nodes.map((node, index) => {
    const cluster = clusterAssignments.get(node.id) ?? 0;
    const clusterSize = clusterBuckets.get(cluster)?.length ?? 1;
    const center = clusterCenters[cluster % clusterCenters.length];
    const slot = clusterSlots.get(node.id) ?? 0;
    const angle = slot * 2.3999632297 + (hashString(node.id) % 37) * 0.07;
    const localRadius = Math.min(150, 24 + Math.sqrt(slot) * (8.8 + Math.min(clusterSize, 90) * 0.02));

    return {
      ...node,
      index,
      degree: degrees.get(node.id) ?? 0,
      cluster,
      clusterSize,
      x: center.x + Math.cos(angle) * localRadius,
      y: center.y + Math.sin(angle) * localRadius,
      phase: (hashString(`p:${node.id}`) % 628) / 100,
      drift: 0.5 + (hashString(`d:${node.id}`) % 7) * 0.06,
      color: PALETTE[cluster % PALETTE.length],
    };
  });

  relaxLayout(nodes, graph.edges, weights, clusterCenters);
  normalizeToCircle(nodes);

  return {
    nodes,
    edges: graph.edges,
    neighbors,
    clusterCenters,
  };
}

function relaxLayout(
  nodes: LayoutNode[],
  edges: LandingGraphDTO["edges"],
  weights: Map<string, Map<string, number>>,
  clusterCenters: Vec2[],
) {
  const nodeIndex = new Map(nodes.map((node, index) => [node.id, index]));
  const velocities = nodes.map(() => ({ x: 0, y: 0 }));
  const maxRadius = GRAPH_RADIUS * 0.94;

  for (let iteration = 0; iteration < 110; iteration += 1) {
    for (const velocity of velocities) {
      velocity.x = 0;
      velocity.y = 0;
    }

    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      const left = nodes[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const right = nodes[rightIndex];
        let dx = right.x - left.x;
        let dy = right.y - left.y;
        let distSq = dx * dx + dy * dy;
        if (distSq < 1) distSq = 1;
        const distance = Math.sqrt(distSq);
        dx /= distance;
        dy /= distance;

        const sameCluster = left.cluster === right.cluster;
        const minDistance = sameCluster ? 16 : 11;
        let repulsion = sameCluster ? 1600 / distSq : 820 / distSq;
        if (distance < minDistance) {
          repulsion += (minDistance - distance) * 0.75;
        }

        velocities[leftIndex].x -= dx * repulsion;
        velocities[leftIndex].y -= dy * repulsion;
        velocities[rightIndex].x += dx * repulsion;
        velocities[rightIndex].y += dy * repulsion;
      }
    }

    for (const edge of edges) {
      const sourceIndex = nodeIndex.get(edge.source);
      const targetIndex = nodeIndex.get(edge.target);
      if (sourceIndex == null || targetIndex == null) continue;
      const source = nodes[sourceIndex];
      const target = nodes[targetIndex];
      let dx = target.x - source.x;
      let dy = target.y - source.y;
      let distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < 1) distance = 1;
      dx /= distance;
      dy /= distance;
      const targetDistance = 18 + (1 - edge.weight) * 92;
      const spring = (distance - targetDistance) * 0.024;

      velocities[sourceIndex].x += dx * spring;
      velocities[sourceIndex].y += dy * spring;
      velocities[targetIndex].x -= dx * spring;
      velocities[targetIndex].y -= dy * spring;
    }

    nodes.forEach((node, index) => {
      const clusterCenter = clusterCenters[node.cluster % clusterCenters.length];
      const clusterPull = 0.0039 / Math.max(1, Math.sqrt(node.clusterSize));
      const centerPull = 0.00135;
      velocities[index].x += (clusterCenter.x - node.x) * clusterPull;
      velocities[index].y += (clusterCenter.y - node.y) * clusterPull;
      velocities[index].x += -node.x * centerPull;
      velocities[index].y += -node.y * centerPull;

      node.x += velocities[index].x * 0.9;
      node.y += velocities[index].y * 0.9;

      const radius = Math.sqrt(node.x * node.x + node.y * node.y);
      if (radius > maxRadius) {
        const scale = maxRadius / radius;
        node.x *= scale;
        node.y *= scale;
      }
    });
  }

  for (let pass = 0; pass < 18; pass += 1) {
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      const left = nodes[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const right = nodes[rightIndex];
        if (left.cluster !== right.cluster) continue;
        let dx = right.x - left.x;
        let dy = right.y - left.y;
        let distance = Math.sqrt(dx * dx + dy * dy);
        if (distance < 1) distance = 1;
        const minDistance = 16 + Math.min(6, Math.sqrt(left.clusterSize) * 0.16);
        if (distance >= minDistance) continue;
        dx /= distance;
        dy /= distance;
        const push = (minDistance - distance) * 0.18;
        left.x -= dx * push;
        left.y -= dy * push;
        right.x += dx * push;
        right.y += dy * push;
      }
    }
  }

  // Light semantic smoothing from each node's strongest neighbors.
  for (const node of nodes) {
    const neighborsByWeight = [...(weights.get(node.id)?.entries() ?? [])]
      .sort((left, right) => right[1] - left[1])
      .slice(0, 4);
    if (neighborsByWeight.length === 0) continue;

    let avgX = 0;
    let avgY = 0;
    let total = 0;
    for (const [neighborId, weight] of neighborsByWeight) {
      const neighbor = nodes[nodeIndex.get(neighborId) ?? -1];
      if (!neighbor) continue;
      const influence = clamp(weight, 0.24, 0.92);
      avgX += neighbor.x * influence;
      avgY += neighbor.y * influence;
      total += influence;
    }
    if (total > 0) {
      node.x = node.x * 0.91 + (avgX / total) * 0.09;
      node.y = node.y * 0.91 + (avgY / total) * 0.09;
    }
  }
}

function normalizeToCircle(nodes: LayoutNode[]) {
  let maxRadius = 1;
  let maxDegree = 1;
  for (const node of nodes) {
    maxRadius = Math.max(maxRadius, Math.sqrt(node.x * node.x + node.y * node.y));
    maxDegree = Math.max(maxDegree, node.degree);
  }
  const scale = (GRAPH_RADIUS * 0.99) / maxRadius;
  for (const node of nodes) {
    node.x *= scale;
    node.y *= scale;
    const radius = Math.sqrt(node.x * node.x + node.y * node.y);
    const radialT = clamp(radius / (GRAPH_RADIUS * 0.99), 0, 1);
    const degreeBias = clamp(node.degree / maxDegree, 0, 1);
    const shellCurve = Math.pow(radialT, 1.08);
    const inwardBias = 1 - degreeBias * 0.18;
    const targetRadius = GRAPH_RADIUS * 0.99 * shellCurve * inwardBias;
    if (radius > 0) {
      const radialScale = targetRadius / radius;
      node.x *= radialScale;
      node.y *= radialScale;
    }
  }
}

function paintScene(
  context: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  layout: Layout,
  now: number,
  hoveredId: string | null,
  frameNodesRef: { current: FrameNode[] },
) {
  const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
  if (canvas.width !== WIDTH * dpr || canvas.height !== HEIGHT * dpr) {
    canvas.width = WIDTH * dpr;
    canvas.height = HEIGHT * dpr;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  context.clearRect(0, 0, WIDTH, HEIGHT);
  drawBackdrop(context);

  const frameNodes = frameProject(layout.nodes, now);
  frameNodesRef.current = frameNodes;
  const nodeById = new Map(frameNodes.map((node) => [node.id, node]));
  const activeIds = hoveredId ? new Set([hoveredId, ...(layout.neighbors.get(hoveredId) ?? [])]) : null;
  const labels = hoveredId
    ? frameNodes.filter((node) => node.id === hoveredId)
    : [...frameNodes]
        .sort((left, right) => right.degree + right.clusterSize * 0.03 - (left.degree + left.clusterSize * 0.03))
        .slice(0, LABEL_COUNT);

  for (const edge of layout.edges) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) continue;
    const active = !activeIds || (activeIds.has(source.id) && activeIds.has(target.id));
    context.beginPath();
    context.moveTo(source.drawX, source.drawY);
    context.lineTo(target.drawX, target.drawY);
    context.strokeStyle = active
      ? `rgba(96, 83, 70, ${0.06 + edge.weight * 0.16})`
      : `rgba(130, 118, 106, ${0.012 + edge.weight * 0.045})`;
    context.lineWidth = 0.35 + edge.weight * 1.45;
    context.stroke();
  }

  for (const node of frameNodes) {
    const active = !activeIds || activeIds.has(node.id);
    const showHalo = hoveredId === node.id || node.degree >= 10;
    if (showHalo) {
      context.fillStyle = withAlpha(node.color, active ? 0.14 : 0.05);
      context.beginPath();
      context.arc(node.drawX, node.drawY, node.glowRadius, 0, Math.PI * 2);
      context.fill();
    }

    context.fillStyle = withAlpha(node.color, active ? 0.9 : 0.48);
    context.beginPath();
    context.arc(node.drawX, node.drawY, node.radius, 0, Math.PI * 2);
    context.fill();

    context.strokeStyle = hoveredId === node.id ? "rgba(28,24,21,0.9)" : "rgba(255,255,255,0.94)";
    context.lineWidth = hoveredId === node.id ? 1.55 : 0.9;
    context.stroke();
  }

  context.font = "12px var(--font-inter), system-ui, sans-serif";
  context.fillStyle = "rgba(28,24,21,0.68)";
  for (const node of labels) {
    context.globalAlpha = 0.92;
    context.fillText(truncate(node.title, 26), node.drawX + 12, node.drawY - 10);
  }
  context.globalAlpha = 1;
}

function frameProject(nodes: LayoutNode[], now: number): FrameNode[] {
  const rotation = now * 0.00012;
  const cos = Math.cos(rotation);
  const sin = Math.sin(rotation);

  return nodes.map((node) => {
    const driftX = Math.sin(now * 0.00036 + node.phase) * node.drift;
    const driftY = Math.cos(now * 0.00032 + node.phase * 1.17) * node.drift;
    const rotatedX = node.x * cos - node.y * sin;
    const rotatedY = node.x * sin + node.y * cos;
    const x = CENTER_X + rotatedX + driftX;
    const y = CENTER_Y + rotatedY + driftY;
    const radius = 2.5 + Math.min(node.degree, 10) * 0.11 + (node.score ?? 0) * 0.03;

    return {
      ...node,
      drawX: x,
      drawY: y,
      radius,
      glowRadius: radius * 2.4,
    };
  });
}

function pickAnchors(
  nodes: LandingGraphDTO["nodes"],
  degrees: Map<string, number>,
  neighbors: Map<string, Set<string>>,
) {
  const ranked = [...nodes].sort((left, right) => (degrees.get(right.id) ?? 0) - (degrees.get(left.id) ?? 0));
  const anchors: LandingGraphDTO["nodes"] = [];

  for (const candidate of ranked) {
    if (anchors.length >= CLUSTER_COUNT) break;
    const tooClose = anchors.some((anchor) => neighbors.get(anchor.id)?.has(candidate.id));
    if (!tooClose) anchors.push(candidate);
  }

  return anchors.length > 0 ? anchors : ranked.slice(0, CLUSTER_COUNT);
}

function assignClusters(
  nodes: LandingGraphDTO["nodes"],
  anchors: LandingGraphDTO["nodes"],
  neighbors: Map<string, Set<string>>,
) {
  const assignments = new Map<string, number>();
  const queue: Array<{ id: string; cluster: number }> = [];

  anchors.forEach((anchor, cluster) => {
    assignments.set(anchor.id, cluster);
    queue.push({ id: anchor.id, cluster });
  });

  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const neighbor of neighbors.get(current.id) ?? []) {
      if (assignments.has(neighbor)) continue;
      assignments.set(neighbor, current.cluster);
      queue.push({ id: neighbor, cluster: current.cluster });
    }
  }

  for (const node of nodes) {
    if (!assignments.has(node.id)) {
      assignments.set(node.id, hashString(node.id) % Math.max(anchors.length, 1));
    }
  }

  return assignments;
}

function buildClusterCenters(count: number): Vec2[] {
  const radius = GRAPH_RADIUS * 0.44;
  return Array.from({ length: count }, (_, index) => {
    const angle = (-Math.PI / 2) + (index / Math.max(count, 1)) * Math.PI * 2;
    const ring = index % 2 === 0 ? 1 : 0.83;
    return {
      x: Math.cos(angle) * radius * ring,
      y: Math.sin(angle) * radius * ring,
    };
  });
}

function drawBackdrop(context: CanvasRenderingContext2D) {
  const gradient = context.createRadialGradient(CENTER_X, CENTER_Y, 30, CENTER_X, CENTER_Y, GRAPH_RADIUS * 1.34);
  gradient.addColorStop(0, "rgba(255,255,255,0.36)");
  gradient.addColorStop(0.58, "rgba(245,231,224,0.22)");
  gradient.addColorStop(1, "rgba(245,231,224,0)");
  context.fillStyle = gradient;
  context.beginPath();
  context.arc(CENTER_X, CENTER_Y, GRAPH_RADIUS * 1.28, 0, Math.PI * 2);
  context.fill();
}

function findHoveredNode(point: { x: number; y: number }, nodes: FrameNode[]) {
  let best: FrameNode | null = null;
  let bestDistance = Infinity;

  for (const node of nodes) {
    const dx = point.x - node.drawX;
    const dy = point.y - node.drawY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const hitRadius = Math.max(node.radius + 4, 7);
    if (distance <= hitRadius && distance < bestDistance) {
      best = node;
      bestDistance = distance;
    }
  }

  return best;
}

function canvasPoint(event: React.PointerEvent<HTMLCanvasElement>) {
  const rect = event.currentTarget.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * WIDTH,
    y: ((event.clientY - rect.top) / rect.height) * HEIGHT,
  };
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function withAlpha(hex: string, alpha: number) {
  const normalized = hex.replace("#", "");
  const r = Number.parseInt(normalized.slice(0, 2), 16);
  const g = Number.parseInt(normalized.slice(2, 4), 16);
  const b = Number.parseInt(normalized.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function truncate(value: string, max: number) {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 3)}...`;
}
