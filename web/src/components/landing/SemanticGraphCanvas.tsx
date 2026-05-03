"use client";

import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as THREE from "three";
import type { LandingGraphDTO } from "@/lib/api";

const WIDTH = 1180;
const HEIGHT = 920;
const BASE_CAMERA_Z = 860;
const BASE_PITCH = -0.1;
const MIN_ZOOM = 0.72;
const MAX_ZOOM = 1.35;
const DRAG_ROTATION_SPEED = 0.0052;
const WHEEL_ZOOM_SPEED = 0.0011;
const DRAG_CLICK_THRESHOLD = 5;
const MIN_PITCH = -0.72;
const MAX_PITCH = 0.62;
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
let shaderPrecisionPrototypePatched = false;

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

type PointerPoint = {
  x: number;
  y: number;
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
  rayHits: THREE.Intersection<THREE.Object3D>[];
  pointer: THREE.Vector2;
  dummy: THREE.Object3D;
  baseColors: THREE.Color[];
  hoverColors: THREE.Color[];
  hoveredId: string | null;
  animationFrame: number;
  destroyed: boolean;
  pointerDirty: boolean;
  transformDirty: boolean;
  visible: boolean;
  documentVisible: boolean;
  lastFrameTime: number;
  yaw: number;
  targetYaw: number;
  pitch: number;
  targetPitch: number;
  yawVelocity: number;
  pitchVelocity: number;
  idleYaw: number;
  zoom: number;
  targetZoom: number;
  dragging: boolean;
  pinching: boolean;
  dragPointerId: number | null;
  lastPointerX: number;
  lastPointerY: number;
  lastDragTime: number;
  dragDistance: number;
  dragMoved: boolean;
  suppressNextClick: boolean;
  suppressClickUntil: number;
  activePointers: Map<number, PointerPoint>;
  lastPinchDistance: number;
  cursor: string;
};

export function SemanticGraphCanvas({ graph }: Props) {
  const router = useRouter();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneStateRef = useRef<GraphSceneState | null>(null);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const hoveredIdRef = useRef<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<LayoutNode | null>(null);
  const [webglAvailable, setWebglAvailable] = useState(true);
  const layout = useMemo(() => createLayout(graph), [graph]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = createRenderer(canvas);
    if (!renderer) {
      setWebglAvailable(false);
      return;
    }
    setWebglAvailable(true);
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, WIDTH / HEIGHT, 1, 2200);
    camera.position.set(0, 0, BASE_CAMERA_Z);

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
      rayHits: [],
      pointer: new THREE.Vector2(),
      dummy: new THREE.Object3D(),
      hoveredId: null,
      animationFrame: 0,
      destroyed: false,
      pointerDirty: false,
      transformDirty: false,
      visible: true,
      documentVisible:
        typeof document !== "undefined" ? !document.hidden : true,
      lastFrameTime: 0,
      yaw: 0,
      targetYaw: 0,
      pitch: BASE_PITCH,
      targetPitch: BASE_PITCH,
      yawVelocity: 0,
      pitchVelocity: 0,
      idleYaw: 0,
      zoom: 1,
      targetZoom: 1,
      dragging: false,
      pinching: false,
      dragPointerId: null,
      lastPointerX: 0,
      lastPointerY: 0,
      lastDragTime: 0,
      dragDistance: 0,
      dragMoved: false,
      suppressNextClick: false,
      suppressClickUntil: 0,
      activePointers: new Map(),
      lastPinchDistance: 0,
      cursor: "grab",
    };
    canvas.style.cursor = "grab";
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

      // Pause when off-screen or the tab is hidden — saves CPU/GPU/battery.
      if (!state.visible || !state.documentVisible) {
        state.animationFrame = 0;
        return;
      }

      state.animationFrame = window.requestAnimationFrame(render);

      const previousFrameTime = state.lastFrameTime || now;
      const deltaSeconds = clamp((now - previousFrameTime) * 0.001, 0.001, 0.05);
      state.lastFrameTime = now;

      updateInteractionPhysics(state, deltaSeconds);

      const pointer = pointerRef.current;
      if (pointer && !state.dragging && !state.pinching) {
        // Raycasting is expensive; only run it when the pointer actually moves
        // or when the graph transform changed under a stationary pointer.
        if (state.pointerDirty || state.transformDirty) {
          state.pointer.set(pointer.x, pointer.y);
          state.raycaster.setFromCamera(state.pointer, camera);
          state.rayHits.length = 0;
          const hit = state.raycaster.intersectObject(state.hitMesh, false, state.rayHits)[0];
          const nextId =
            hit?.instanceId == null ? null : (layout.nodes[hit.instanceId]?.id ?? null);
          applyHover(state, nextId, hoveredIdRef, setHoveredNode);
          state.rayHits.length = 0;
          state.pointerDirty = false;
        }
      } else if (state.hoveredId !== null) {
        applyHover(state, null, hoveredIdRef, setHoveredNode);
      }
      state.transformDirty = false;

      renderer.render(scene, camera);
    };

    const startRenderLoop = () => {
      if (state.destroyed) return;
      if (!state.visible || !state.documentVisible) return;
      if (state.animationFrame !== 0) return;
      state.animationFrame = window.requestAnimationFrame(render);
    };

    // Keep the canvas size in sync without forcing a layout read every frame.
    const resizeObserver = new ResizeObserver(() => {
      if (state.destroyed) return;
      resize();
      // If we're paused and a layout change happens, render one frame so the
      // canvas doesn't go stale.
      if (state.animationFrame === 0 && !state.destroyed) {
        renderer.render(scene, camera);
      }
    });
    resizeObserver.observe(canvas);

    // Pause animation when the canvas scrolls out of view.
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          state.visible = entry.isIntersecting;
        }
        if (state.visible) startRenderLoop();
      },
      { threshold: 0 },
    );
    intersectionObserver.observe(canvas);

    // Pause animation when the user switches tabs / minimizes the window.
    const handleVisibilityChange = () => {
      state.documentVisible = !document.hidden;
      if (state.documentVisible) startRenderLoop();
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    resize();
    startRenderLoop();

    return () => {
      state.destroyed = true;
      if (state.animationFrame !== 0) {
        window.cancelAnimationFrame(state.animationFrame);
      }
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
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

  function handlePointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    const state = sceneStateRef.current;
    if (!state) return;

    event.currentTarget.setPointerCapture(event.pointerId);
    state.activePointers.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    syncPointerFromEvent(event, pointerRef);

    if (state.activePointers.size >= 2) {
      state.pinching = true;
      state.dragging = false;
      state.dragPointerId = null;
      state.lastPinchDistance = pointerDistance(state.activePointers);
      suppressClick(state);
      applyHover(state, null, hoveredIdRef, setHoveredNode);
      setCanvasCursor(state, "grabbing");
      return;
    }

    state.dragging = true;
    state.dragPointerId = event.pointerId;
    state.lastPointerX = event.clientX;
    state.lastPointerY = event.clientY;
    state.lastDragTime = event.timeStamp || performance.now();
    state.dragDistance = 0;
    state.dragMoved = false;
    state.yawVelocity = 0;
    state.pitchVelocity = 0;
    applyHover(state, null, hoveredIdRef, setHoveredNode);
    setCanvasCursor(state, "grabbing");
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const state = sceneStateRef.current;
    if (!state) return;

    const activePointer = state.activePointers.get(event.pointerId);
    if (activePointer) {
      activePointer.x = event.clientX;
      activePointer.y = event.clientY;
    }
    syncPointerFromEvent(event, pointerRef);

    if (state.pinching && state.activePointers.size >= 2) {
      const nextDistance = pointerDistance(state.activePointers);
      if (state.lastPinchDistance > 0 && nextDistance > 0) {
        state.targetZoom = clamp(
          state.targetZoom * (nextDistance / state.lastPinchDistance),
          MIN_ZOOM,
          MAX_ZOOM,
        );
        state.transformDirty = true;
      }
      state.lastPinchDistance = nextDistance;
      state.pointerDirty = true;
      return;
    }

    if (state.dragging && state.dragPointerId === event.pointerId) {
      const dx = event.clientX - state.lastPointerX;
      const dy = event.clientY - state.lastPointerY;
      const now = event.timeStamp || performance.now();
      const deltaSeconds = Math.max(0.001, (now - state.lastDragTime) * 0.001);
      const instantYawVelocity = (dx * DRAG_ROTATION_SPEED) / deltaSeconds;
      const instantPitchVelocity = (dy * DRAG_ROTATION_SPEED) / deltaSeconds;

      state.targetYaw += dx * DRAG_ROTATION_SPEED;
      state.targetPitch = clamp(
        state.targetPitch + dy * DRAG_ROTATION_SPEED,
        MIN_PITCH,
        MAX_PITCH,
      );
      state.yawVelocity = state.yawVelocity * 0.28 + instantYawVelocity * 0.72;
      state.pitchVelocity = state.pitchVelocity * 0.28 + instantPitchVelocity * 0.72;
      state.lastPointerX = event.clientX;
      state.lastPointerY = event.clientY;
      state.lastDragTime = now;
      state.dragDistance += Math.hypot(dx, dy);
      if (state.dragDistance > DRAG_CLICK_THRESHOLD) {
        state.dragMoved = true;
        suppressClick(state);
      }
      state.pointerDirty = true;
      state.transformDirty = true;
      return;
    }

    state.pointerDirty = true;
  }

  function handlePointerUp(event: React.PointerEvent<HTMLCanvasElement>) {
    const state = sceneStateRef.current;
    if (!state) return;

    state.activePointers.delete(event.pointerId);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    syncPointerFromEvent(event, pointerRef);

    if (state.pinching && state.activePointers.size < 2) {
      state.pinching = false;
      state.lastPinchDistance = 0;
    }

    if (state.dragPointerId === event.pointerId) {
      state.dragging = false;
      state.dragPointerId = null;
      state.pointerDirty = true;
      state.transformDirty = true;
    }

    if (state.activePointers.size === 0) {
      setCanvasCursor(state, state.hoveredId ? "pointer" : "grab");
    }
  }

  function handlePointerCancel(event: React.PointerEvent<HTMLCanvasElement>) {
    const state = sceneStateRef.current;
    if (!state) return;

    state.activePointers.delete(event.pointerId);
    state.dragging = false;
    state.pinching = false;
    state.dragPointerId = null;
    state.lastPinchDistance = 0;
    if (state.dragMoved) suppressClick(state);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setCanvasCursor(state, "grab");
  }

  function handlePointerLeave() {
    pointerRef.current = null;
    const state = sceneStateRef.current;
    if (state && !state.dragging && !state.pinching) {
      state.pointerDirty = false;
      applyHover(state, null, hoveredIdRef, setHoveredNode);
    }
  }

  function handleWheel(event: React.WheelEvent<HTMLCanvasElement>) {
    const state = sceneStateRef.current;
    if (!state) return;
    event.preventDefault();
    state.targetZoom = clamp(
      state.targetZoom * Math.exp(-event.deltaY * WHEEL_ZOOM_SPEED),
      MIN_ZOOM,
      MAX_ZOOM,
    );
    state.transformDirty = true;
    state.pointerDirty = true;
  }

  function handleClick() {
    const state = sceneStateRef.current;
    if (
      state?.suppressNextClick &&
      (performance.now() <= state.suppressClickUntil || state.suppressClickUntil === 0)
    ) {
      state.suppressNextClick = false;
      state.suppressClickUntil = 0;
      return;
    }
    if (state) state.suppressNextClick = false;
    if (hoveredIdRef.current) openPaper(hoveredIdRef.current);
  }

  return (
    <section className="relative mx-1 mt-2 h-[min(22dvh,170px)] overflow-visible sm:mx-4 sm:h-[min(30dvh,300px)] md:h-[min(34dvh,360px)] lg:mx-6 xl:mx-0 xl:-ml-12 xl:mr-0 xl:mt-0 xl:h-[min(720px,calc(100dvh-11rem))] xl:w-[min(1100px,calc(100%+72px))] xl:max-w-[1100px] xl:self-center">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_48%,rgba(255,255,255,0.56),transparent_22%),radial-gradient(circle_at_48%_50%,rgba(245,231,224,0.96),transparent_44%),radial-gradient(circle_at_72%_26%,rgba(122,28,28,0.11),transparent_18%),radial-gradient(circle_at_28%_68%,rgba(47,107,71,0.09),transparent_19%),radial-gradient(circle_at_55%_78%,rgba(79,115,151,0.08),transparent_18%)] blur-3xl" />
      <div className="relative h-full">
        <canvas
          ref={canvasRef}
          width={WIDTH}
          height={HEIGHT}
          className={`h-full w-full max-w-[1120px] touch-none overflow-visible ${
            webglAvailable ? "cursor-grab" : "pointer-events-none opacity-0"
          }`}
          aria-label="Semantic graph of related papers"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerCancel}
          onPointerLeave={handlePointerLeave}
          onWheel={handleWheel}
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

function createRenderer(canvas: HTMLCanvasElement) {
  const contextAttributes: WebGLContextAttributes = {
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
  };

  patchShaderPrecisionFormatPrototype();

  const context = canvas.getContext("webgl2", contextAttributes);

  if (!context || !context.getContextAttributes()) return null;

  patchShaderPrecisionFormat(context);

  try {
    return new THREE.WebGLRenderer({
      canvas,
      context: context as unknown as WebGLRenderingContext,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
  } catch (error) {
    console.warn("Semantic graph WebGL renderer could not start.", error);
    return null;
  }
}

function patchShaderPrecisionFormatPrototype() {
  if (shaderPrecisionPrototypePatched) return;
  if (typeof WebGL2RenderingContext === "undefined") return;

  const prototype = WebGL2RenderingContext.prototype;
  const originalGetShaderPrecisionFormat = prototype.getShaderPrecisionFormat;

  const getShaderPrecisionFormat = function (
    this: WebGL2RenderingContext,
    shaderType: GLenum,
    precisionType: GLenum,
  ): WebGLShaderPrecisionFormat {
    return (
      originalGetShaderPrecisionFormat.call(this, shaderType, precisionType) ??
      fallbackShaderPrecisionFormat(this, precisionType)
    );
  };

  try {
    Object.defineProperty(prototype, "getShaderPrecisionFormat", {
      configurable: true,
      value: getShaderPrecisionFormat,
    });
    shaderPrecisionPrototypePatched = true;
  } catch {
    // Some browsers lock native WebGL methods; the per-context patch below is
    // still attempted before renderer startup.
  }
}

function patchShaderPrecisionFormat(context: WebGL2RenderingContext) {
  const originalGetShaderPrecisionFormat =
    context.getShaderPrecisionFormat.bind(context);

  const getShaderPrecisionFormat = (
    shaderType: GLenum,
    precisionType: GLenum,
  ): WebGLShaderPrecisionFormat => {
    const precision = originalGetShaderPrecisionFormat(shaderType, precisionType);
    if (precision) return precision;

    return fallbackShaderPrecisionFormat(context, precisionType);
  };

  try {
    Object.defineProperty(context, "getShaderPrecisionFormat", {
      configurable: true,
      value: getShaderPrecisionFormat,
    });
  } catch {
    try {
      context.getShaderPrecisionFormat = getShaderPrecisionFormat;
    } catch {
      // If the context is not patchable, renderer startup will fall back safely.
    }
  }
}

function fallbackShaderPrecisionFormat(
  context: WebGL2RenderingContext,
  precisionType: GLenum,
) {
  return {
    rangeMin: precisionType === context.HIGH_FLOAT ? 127 : 14,
    rangeMax: precisionType === context.HIGH_FLOAT ? 127 : 14,
    precision: precisionType === context.HIGH_FLOAT ? 23 : 10,
  } as WebGLShaderPrecisionFormat;
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

function updateInteractionPhysics(state: GraphSceneState, deltaSeconds: number) {
  if (!state.dragging && !state.pinching) {
    const velocityDamping = Math.exp(-5.8 * deltaSeconds);
    state.targetYaw += state.yawVelocity * deltaSeconds;
    state.targetPitch = clamp(
      state.targetPitch + state.pitchVelocity * deltaSeconds,
      MIN_PITCH,
      MAX_PITCH,
    );
    state.yawVelocity *= velocityDamping;
    state.pitchVelocity *= velocityDamping;

    if (Math.abs(state.yawVelocity) < 0.002) state.yawVelocity = 0;
    if (Math.abs(state.pitchVelocity) < 0.002) state.pitchVelocity = 0;
    if (state.yawVelocity === 0 && state.pitchVelocity === 0) {
      state.idleYaw += deltaSeconds * 0.055;
    }
  }

  const rotationEase = 1 - Math.exp(-24 * deltaSeconds);
  const zoomEase = 1 - Math.exp(-18 * deltaSeconds);
  const previousYaw = state.yaw;
  const previousPitch = state.pitch;
  const previousZoom = state.zoom;

  state.yaw += (state.targetYaw - state.yaw) * rotationEase;
  state.pitch += (state.targetPitch - state.pitch) * rotationEase;
  state.zoom += (state.targetZoom - state.zoom) * zoomEase;

  const time = state.lastFrameTime * 0.001;
  const idlePitch = !state.dragging && !state.pinching ? Math.sin(time * 0.24) * 0.04 : 0;
  const idleRoll = !state.dragging && !state.pinching ? Math.sin(time * 0.16) * 0.018 : 0;

  state.group.rotation.y = state.idleYaw + state.yaw;
  state.group.rotation.x = state.pitch + idlePitch;
  state.group.rotation.z = idleRoll;
  state.group.scale.setScalar(state.zoom);

  if (
    Math.abs(previousYaw - state.yaw) > 0.0001 ||
    Math.abs(previousPitch - state.pitch) > 0.0001 ||
    Math.abs(previousZoom - state.zoom) > 0.0001
  ) {
    state.transformDirty = true;
  }
}

function syncPointerFromEvent(
  event: React.PointerEvent<HTMLCanvasElement>,
  pointerRef: React.MutableRefObject<{ x: number; y: number } | null>,
) {
  const rect = event.currentTarget.getBoundingClientRect();
  pointerRef.current = {
    x: ((event.clientX - rect.left) / rect.width) * 2 - 1,
    y: -(((event.clientY - rect.top) / rect.height) * 2 - 1),
  };
}

function pointerDistance(pointers: Map<number, PointerPoint>) {
  let first: PointerPoint | null = null;
  let second: PointerPoint | null = null;

  for (const pointer of pointers.values()) {
    if (!first) {
      first = pointer;
    } else {
      second = pointer;
      break;
    }
  }

  if (!first || !second) return 0;
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function setCanvasCursor(state: GraphSceneState, cursor: string) {
  if (state.cursor === cursor) return;
  state.cursor = cursor;
  state.renderer.domElement.style.cursor = cursor;
}

function suppressClick(state: GraphSceneState) {
  state.suppressNextClick = true;
  state.suppressClickUntil = performance.now() + 450;
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
  if (!state.dragging && !state.pinching) {
    setCanvasCursor(state, nextId ? "pointer" : "grab");
  }
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
