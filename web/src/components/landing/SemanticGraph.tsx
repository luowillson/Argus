import { fetchLandingGraph } from "@/lib/api";
import { SemanticGraphClient } from "./SemanticGraphClient";

export async function SemanticGraph() {
  const graph = await fetchLandingGraph();
  if (!graph || graph.nodes.length < 8 || graph.edges.length === 0) {
    return null;
  }
  return <SemanticGraphClient graph={graph} />;
}
