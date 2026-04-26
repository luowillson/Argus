"use client";

import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as THREE from "three";
import type { LandingGraphDTO } from "@/lib/api";

const WIDTH = 1180;
const HEIGHT = 920;
const CLUSTER_COUNT = 8;
const PALETTE = [
  "#c73737",
  "#2fa66f",
  "#c99a21",
  "#3269b8",
  "#a762bf",
  "#8da832",
  "#dc7a44",
  "#2fb2a0",
];

type Props = {
  graph: LandingGraphDTO;
};

type Vec3 = {
  x: number;
  y: number;
  z: number;
};

type LayoutNode = LandingGraphDTO["nodes"][number] & {
  index: number;
  degree: number;
  cluster: number;
  clusterSize: number;
  x: number;
  y: number;
  z: number;
  phase: number;
  radius: number;
  color: string;
};

type Layout = {
  nodes: LayoutNode[];
  edges: LandingGraphDTO["edges"];
  neighbors: Map<string, Set<string>>;
  nodeById: Map<string, LayoutNode>;
  nodeIndex: Map<string, number>;
  incidentEdges: Map<string, number[]>;
  maxIncidentEdges: number;
};

type GraphSceneState = {
  layout: Layout;
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  group: THREE.Group;
  nodesMesh: THREE.InstancedMesh;
  hitMesh: THREE.InstancedMesh;
  edgeLines: THREE.LineSegments;
  activeLines: THREE.LineSegments;
  activeLinePositions: Float32Array;
  raycaster: THREE.Raycaster;
  pointer: THREE.Vector2;
  dummy: THREE.Object3D;
  baseColors: THREE.Color[];
  hoverColors: THREE.Color[];
  hoveredId: string | null;
  animationFrame: number;
  destroyed: boolean;
};

export function SemanticGraphCanvas({ graph }: Props) {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneStateRef = useRef<GraphSceneState | null>(null);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const hoveredIdRef = useRef<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<LayoutNode | null>(null);
  const layout = useMemo(() => createLayout(graph), [graph]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, WIDTH / HEIGHT, 1, 2200);
    camera.position.set(0, 0, 860);

    const group = new THREE.Group();
    group.rotation.x = -0.1;
    scene.add(group);

    const objects = createSceneObjects(layout);
    group.add(objects.edgeLines, objects.activeLines, objects.nodesMesh, objects.hitMesh);

    const state: GraphSceneState = {
      layout,
      renderer,
      scene,
      camera,
      group,
      ...objects,
      raycaster: new THREE.Raycaster(),
      pointer: new THREE.Vector2(),
      dummy: new THREE.Object3D(),
      hoveredId: null,
      animationFrame: 0,
      destroyed: false,
    };
    sceneStateRef.current = state;

    const resize = () => {
      const width = Math.max(1, canvas.clientWidth);
      const height = Math.max(1, canvas.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    const render = (now: number) => {
      if (state.destroyed) return;
      state.animationFrame = window.requestAnimationFrame(render);
      resize();

      const time = now * 0.001;
      group.rotation.y = time * 0.1;
      group.rotation.x = -0.1 + Math.sin(time * 0.24) * 0.085;
      group.rotation.z = Math.sin(time * 0.16) * 0.03;
      group.updateMatrixWorld();

      const pointer = pointerRef.current;
      if (pointer) {
        state.pointer.set(pointer.x, pointer.y);
        state.raycaster.setFromCamera(state.pointer, camera);
        const hit = state.raycaster.intersectObject(state.hitMesh, false)[0];
        const nextId =
          hit?.instanceId == null ? null : (layout.nodes[hit.instanceId]?.id ?? null);
        applyHover(state, nextId, hoveredIdRef, setHoveredNode);
      } else {
        applyHover(state, null, hoveredIdRef, setHoveredNode);
      }

      renderer.render(scene, camera);
    };

    resize();
    state.animationFrame = window.requestAnimationFrame(render);

    return () => {
      state.destroyed = true;
      window.cancelAnimationFrame(state.animationFrame);
      sceneStateRef.current = null;
      hoveredIdRef.current = null;
      setHoveredNode(null);
      objects.nodesMesh.geometry.dispose();
      objects.hitMesh.geometry.dispose();
      objects.edgeLines.geometry.dispose();
      objects.activeLines.geometry.dispose();
      disposeMaterial(objects.nodesMesh.material);
      disposeMaterial(objects.hitMesh.material);
      disposeMaterial(objects.edgeLines.material);
      disposeMaterial(objects.activeLines.material);
      renderer.dispose();
    };
  }, [layout]);

  function openPaper(paperId: string) {
    startTransition(() => {
      router.push(`/papers/${encodeURIComponent(paperId)}`);
    });
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    pointerRef.current = {
      x: ((event.clientX - rect.left) / rect.width) * 2 - 1,
      y: -(((event.clientY - rect.top) / rect.height) * 2 - 1),
    };
  }

  function handlePointerLeave() {
    pointerRef.current = null;
    const state = sceneStateRef.current;
    if (state) applyHover(state, null, hoveredIdRef, setHoveredNode);
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
    const hash = hashString(node.id);
    const angle = slot * 2.3999632297 + (hash % 53) * 0.053;
    const localRadius = Math.min(
      98,
      16 + Math.sqrt(slot) * (6.55 + Math.min(clusterSize, 120) * 0.011),
    );
    const depthJitter = (((hashString(`z:${node.id}`) % 1000) / 1000) - 0.5) * 72;
    const radius = 3.15 + Math.min(degrees.get(node.id) ?? 0, 12) * 0.1 + (node.score ?? 0) * 0.035;

    return {
      ...node,
      index,
      degree: degrees.get(node.id) ?? 0,
      cluster,
      clusterSize,
      x: center.x + Math.cos(angle) * localRadius,
      y: center.y + Math.sin(angle) * localRadius * 0.72,
      z: center.z + depthJitter,
      phase: (hashString(`p:${node.id}`) % 628) / 100,
      radius,
      color: PALETTE[cluster % PALETTE.length],
    };
  });

  relaxLayout(nodes, graph.edges, weights, clusterCenters);
  normalizeToVolume(nodes);

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const nodeIndex = new Map(nodes.map((node, index) => [node.id, index]));
  const incidentEdges = new Map<string, number[]>();
  for (const node of nodes) incidentEdges.set(node.id, []);

  graph.edges.forEach((edge, index) => {
    incidentEdges.get(edge.source)?.push(index);
    incidentEdges.get(edge.target)?.push(index);
  });

  let maxIncidentEdges = 1;
  for (const edgeIndexes of incidentEdges.values()) {
    maxIncidentEdges = Math.max(maxIncidentEdges, edgeIndexes.length);
  }

  return {
    nodes,
    edges: graph.edges,
    neighbors,
    nodeById,
    nodeIndex,
    incidentEdges,
    maxIncidentEdges,
  };
}

function relaxLayout(
  nodes: LayoutNode[],
  edges: LandingGraphDTO["edges"],
  weights: Map<string, Map<string, number>>,
  clusterCenters: Vec3[],
) {
  const nodeIndex = new Map(nodes.map((node, index) => [node.id, index]));
  const velocities = nodes.map(() => ({ x: 0, y: 0, z: 0 }));
  const bounds = { x: 520, y: 360, z: 340 };

  const iterationCount = nodes.length > 750 ? 54 : 78;

  for (let iteration = 0; iteration < iterationCount; iteration += 1) {
    for (const velocity of velocities) {
      velocity.x = 0;
      velocity.y = 0;
      velocity.z = 0;
    }

    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      const left = nodes[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const right = nodes[rightIndex];
        let dx = right.x - left.x;
        let dy = right.y - left.y;
        let dz = right.z - left.z;
        let distSq = dx * dx + dy * dy + dz * dz;
        if (distSq < 1) distSq = 1;
        const distance = Math.sqrt(distSq);
        dx /= distance;
        dy /= distance;
        dz /= distance;

        const sameCluster = left.cluster === right.cluster;
        const minDistance = sameCluster ? 19 : 13;
        let repulsion = sameCluster ? 2100 / distSq : 980 / distSq;
        if (distance < minDistance) repulsion += (minDistance - distance) * 0.92;

        velocities[leftIndex].x -= dx * repulsion;
        velocities[leftIndex].y -= dy * repulsion;
        velocities[leftIndex].z -= dz * repulsion;
        velocities[rightIndex].x += dx * repulsion;
        velocities[rightIndex].y += dy * repulsion;
        velocities[rightIndex].z += dz * repulsion;
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
      let dz = target.z - source.z;
      let distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (distance < 1) distance = 1;
      dx /= distance;
      dy /= distance;
      dz /= distance;
      const targetDistance = 26 + (1 - edge.weight) * 101;
      const spring = (distance - targetDistance) * 0.018;

      velocities[sourceIndex].x += dx * spring;
      velocities[sourceIndex].y += dy * spring;
      velocities[sourceIndex].z += dz * spring;
      velocities[targetIndex].x -= dx * spring;
      velocities[targetIndex].y -= dy * spring;
      velocities[targetIndex].z -= dz * spring;
    }

    nodes.forEach((node, index) => {
      const clusterCenter = clusterCenters[node.cluster % clusterCenters.length];
      const clusterPull = 0.0058 / Math.max(1, Math.sqrt(node.clusterSize));
      const centerPull = 0.00042;
      velocities[index].x += (clusterCenter.x - node.x) * clusterPull;
      velocities[index].y += (clusterCenter.y - node.y) * clusterPull;
      velocities[index].z += (clusterCenter.z - node.z) * clusterPull;
      velocities[index].x += -node.x * centerPull;
      velocities[index].y += -node.y * centerPull;
      velocities[index].z += -node.z * centerPull * 0.55;

      node.x += velocities[index].x * 0.82;
      node.y += velocities[index].y * 0.82;
      node.z += velocities[index].z * 0.82;

      node.x = clamp(node.x, -bounds.x, bounds.x);
      node.y = clamp(node.y, -bounds.y, bounds.y);
      node.z = clamp(node.z, -bounds.z, bounds.z);
    });
  }

  for (let pass = 0; pass < 14; pass += 1) {
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      const left = nodes[leftIndex];
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        const right = nodes[rightIndex];
        if (left.cluster !== right.cluster) continue;
        let dx = right.x - left.x;
        let dy = right.y - left.y;
        let dz = right.z - left.z;
        let distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (distance < 1) distance = 1;
        const minDistance = 18 + Math.min(7, Math.sqrt(left.clusterSize) * 0.18);
        if (distance >= minDistance) continue;
        dx /= distance;
        dy /= distance;
        dz /= distance;
        const push = (minDistance - distance) * 0.22;
        left.x -= dx * push;
        left.y -= dy * push;
        left.z -= dz * push;
        right.x += dx * push;
        right.y += dy * push;
        right.z += dz * push;
      }
    }
  }

  for (const node of nodes) {
    const neighborsByWeight = [...(weights.get(node.id)?.entries() ?? [])]
      .sort((left, right) => right[1] - left[1])
      .slice(0, 4);
    if (neighborsByWeight.length === 0) continue;

    let avgX = 0;
    let avgY = 0;
    let avgZ = 0;
    let total = 0;
    for (const [neighborId, weight] of neighborsByWeight) {
      const neighbor = nodes[nodeIndex.get(neighborId) ?? -1];
      if (!neighbor) continue;
      const influence = clamp(weight, 0.24, 0.92);
      avgX += neighbor.x * influence;
      avgY += neighbor.y * influence;
      avgZ += neighbor.z * influence;
      total += influence;
    }
    if (total > 0) {
      node.x = node.x * 0.917 + (avgX / total) * 0.083;
      node.y = node.y * 0.917 + (avgY / total) * 0.083;
      node.z = node.z * 0.917 + (avgZ / total) * 0.083;
    }
  }
}

function normalizeToVolume(nodes: LayoutNode[]) {
  if (nodes.length === 0) return;

  const bounds = nodes.reduce(
    (acc, node) => ({
      minX: Math.min(acc.minX, node.x),
      maxX: Math.max(acc.maxX, node.x),
      minY: Math.min(acc.minY, node.y),
      maxY: Math.max(acc.maxY, node.y),
      minZ: Math.min(acc.minZ, node.z),
      maxZ: Math.max(acc.maxZ, node.z),
    }),
    {
      minX: Infinity,
      maxX: -Infinity,
      minY: Infinity,
      maxY: -Infinity,
      minZ: Infinity,
      maxZ: -Infinity,
    },
  );

  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  const centerZ = (bounds.minZ + bounds.maxZ) / 2;
  const scaleX = 292 / Math.max(1, (bounds.maxX - bounds.minX) / 2);
  const scaleY = 218 / Math.max(1, (bounds.maxY - bounds.minY) / 2);
  const scaleZ = 206 / Math.max(1, (bounds.maxZ - bounds.minZ) / 2);

  for (const node of nodes) {
    node.x = (node.x - centerX) * scaleX;
    node.y = (node.y - centerY) * scaleY - 24;
    node.z = (node.z - centerZ) * scaleZ;
  }
}

function createSceneObjects(layout: Layout) {
  const nodeGeometry = new THREE.SphereGeometry(1, 12, 8);
  const hitGeometry = new THREE.SphereGeometry(1, 8, 6);
  const nodeMaterial = new THREE.ShaderMaterial({
    transparent: true,
    toneMapped: false,
    vertexShader: `
      varying vec3 vColor;

      void main() {
        vColor = instanceColor;
        vec4 mvPosition = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;

      void main() {
        gl_FragColor = vec4(vColor, 0.88);
      }
    `,
  });
  const hitMaterial = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    colorWrite: false,
    depthWrite: false,
    transparent: true,
    opacity: 0,
  });
  const nodesMesh = new THREE.InstancedMesh(nodeGeometry, nodeMaterial, layout.nodes.length);
  const hitMesh = new THREE.InstancedMesh(hitGeometry, hitMaterial, layout.nodes.length);
  nodesMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  hitMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  nodesMesh.frustumCulled = false;
  hitMesh.frustumCulled = false;

  const dummy = new THREE.Object3D();
  const baseColors: THREE.Color[] = [];
  const hoverColors: THREE.Color[] = [];

  layout.nodes.forEach((node, index) => {
    setNodeMatrix(nodesMesh, dummy, node, node.radius);
    setNodeMatrix(hitMesh, dummy, node, node.radius * 3.25);
    const baseColor = new THREE.Color(node.color).lerp(new THREE.Color("#fff8ef"), 0.09);
    const hoverColor = new THREE.Color(node.color).lerp(new THREE.Color("#fff8ef"), 0.25);
    baseColors.push(baseColor);
    hoverColors.push(hoverColor);
    nodesMesh.setColorAt(index, baseColor);
  });
  nodesMesh.instanceMatrix.needsUpdate = true;
  hitMesh.instanceMatrix.needsUpdate = true;
  if (nodesMesh.instanceColor) {
    nodesMesh.instanceColor.setUsage(THREE.DynamicDrawUsage);
    nodesMesh.instanceColor.needsUpdate = true;
  }
  nodesMesh.computeBoundingSphere();
  hitMesh.computeBoundingSphere();

  const edgePositions = new Float32Array(layout.edges.length * 6);
  layout.edges.forEach((edge, index) => {
    const source = layout.nodeById.get(edge.source);
    const target = layout.nodeById.get(edge.target);
    if (!source || !target) return;
    writeEdgePosition(edgePositions, index, source, target);
  });
  const edgeGeometry = new THREE.BufferGeometry();
  edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions, 3));
  const edgeMaterial = new THREE.LineBasicMaterial({
    color: 0x6c6256,
    transparent: true,
    opacity: 0.14,
    depthWrite: false,
  });
  const edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
  edgeLines.frustumCulled = false;

  const activeLinePositions = new Float32Array(layout.maxIncidentEdges * 6);
  const activeGeometry = new THREE.BufferGeometry();
  activeGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(activeLinePositions, 3).setUsage(THREE.DynamicDrawUsage),
  );
  activeGeometry.setDrawRange(0, 0);
  const activeMaterial = new THREE.LineBasicMaterial({
    color: 0x1c1815,
    transparent: true,
    opacity: 0.56,
    depthWrite: false,
  });
  const activeLines = new THREE.LineSegments(activeGeometry, activeMaterial);
  activeLines.frustumCulled = false;
  activeLines.renderOrder = 2;

  return {
    nodesMesh,
    hitMesh,
    edgeLines,
    activeLines,
    activeLinePositions,
    baseColors,
    hoverColors,
  };
}

function applyHover(
  state: GraphSceneState,
  nextId: string | null,
  hoveredIdRef: React.MutableRefObject<string | null>,
  setHoveredNode: (node: LayoutNode | null) => void,
) {
  if (state.hoveredId === nextId || state.destroyed) return;

  const previousIndex =
    state.hoveredId == null ? undefined : state.layout.nodeIndex.get(state.hoveredId);
  const nextIndex = nextId == null ? undefined : state.layout.nodeIndex.get(nextId);

  if (previousIndex != null) updateNodeInstance(state, previousIndex, false);
  if (nextIndex != null) updateNodeInstance(state, nextIndex, true);

  state.hoveredId = nextId;
  hoveredIdRef.current = nextId;
  updateActiveEdges(state, nextId);
  setHoveredNode(nextId ? (state.layout.nodeById.get(nextId) ?? null) : null);
}

function updateNodeInstance(state: GraphSceneState, index: number, hovered: boolean) {
  const node = state.layout.nodes[index];
  if (!node) return;
  setNodeMatrix(state.nodesMesh, state.dummy, node, hovered ? node.radius * 1.95 : node.radius);
  state.nodesMesh.setColorAt(index, hovered ? state.hoverColors[index] : state.baseColors[index]);
  state.nodesMesh.instanceMatrix.needsUpdate = true;
  if (state.nodesMesh.instanceColor) state.nodesMesh.instanceColor.needsUpdate = true;
}

function updateActiveEdges(state: GraphSceneState, hoveredId: string | null) {
  const edgeIndexes = hoveredId ? (state.layout.incidentEdges.get(hoveredId) ?? []) : [];
  edgeIndexes.forEach((edgeIndex, drawIndex) => {
    const edge = state.layout.edges[edgeIndex];
    const source = state.layout.nodeById.get(edge.source);
    const target = state.layout.nodeById.get(edge.target);
    if (!source || !target) return;
    writeEdgePosition(state.activeLinePositions, drawIndex, source, target);
  });

  const position = state.activeLines.geometry.getAttribute("position");
  position.needsUpdate = true;
  state.activeLines.geometry.setDrawRange(0, edgeIndexes.length * 2);
}

function setNodeMatrix(
  mesh: THREE.InstancedMesh,
  dummy: THREE.Object3D,
  node: LayoutNode,
  radius: number,
) {
  dummy.position.set(node.x, node.y, node.z);
  dummy.scale.setScalar(radius);
  dummy.updateMatrix();
  mesh.setMatrixAt(node.index, dummy.matrix);
}

function writeEdgePosition(
  positions: Float32Array,
  edgeIndex: number,
  source: LayoutNode,
  target: LayoutNode,
) {
  const offset = edgeIndex * 6;
  positions[offset] = source.x;
  positions[offset + 1] = source.y;
  positions[offset + 2] = source.z;
  positions[offset + 3] = target.x;
  positions[offset + 4] = target.y;
  positions[offset + 5] = target.z;
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

function buildClusterCenters(count: number): Vec3[] {
  const baseCenters: Vec3[] = [
    { x: -230, y: -92, z: -42 },
    { x: -78, y: 104, z: 86 },
    { x: 126, y: -58, z: -18 },
    { x: 268, y: 88, z: 72 },
    { x: -286, y: 80, z: 28 },
    { x: 48, y: -158, z: 116 },
    { x: 230, y: -150, z: -112 },
    { x: -6, y: 4, z: -146 },
  ];

  return Array.from({ length: count }, (_, index) => baseCenters[index % baseCenters.length]);
}

function disposeMaterial(material: THREE.Material | THREE.Material[]) {
  if (Array.isArray(material)) {
    for (const entry of material) entry.dispose();
  } else {
    material.dispose();
  }
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index++) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
