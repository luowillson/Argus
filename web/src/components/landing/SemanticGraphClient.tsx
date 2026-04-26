"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { fetchLandingGraph, type LandingGraphDTO } from "@/lib/api";

type Props = {
  graph?: LandingGraphDTO | null;
};

const SemanticGraphCanvas = dynamic(
  () => import("./SemanticGraphCanvas").then((mod) => mod.SemanticGraphCanvas),
  { ssr: false },
);

export function SemanticGraphClient({ graph: initialGraph = null }: Props) {
  const [graph, setGraph] = useState<LandingGraphDTO | null>(initialGraph);

  useEffect(() => {
    if (graph) return;
    let cancelled = false;

    async function loadGraph() {
      const nextGraph = await fetchLandingGraph();
      if (
        !cancelled &&
        nextGraph &&
        nextGraph.nodes.length >= 8 &&
        nextGraph.edges.length > 0
      ) {
        setGraph(nextGraph);
      }
    }

    void loadGraph();
    return () => {
      cancelled = true;
    };
  }, [graph]);

  if (!graph || graph.nodes.length < 8 || graph.edges.length === 0) return null;
  return <SemanticGraphCanvas graph={graph} />;
}
