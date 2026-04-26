"use client";

import dynamic from "next/dynamic";
import type { LandingGraphDTO } from "@/lib/api";

type Props = {
  graph: LandingGraphDTO;
};

const SemanticGraphCanvas = dynamic(
  () => import("./SemanticGraphCanvas").then((mod) => mod.SemanticGraphCanvas),
  { ssr: false },
);

export function SemanticGraphClient({ graph }: Props) {
  return <SemanticGraphCanvas graph={graph} />;
}
