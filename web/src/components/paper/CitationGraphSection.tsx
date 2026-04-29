"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  enrichPaperCitations,
  fetchPaperCitations,
  type CitationGraphDTO,
  type CitationPaperDTO,
} from "@/lib/api";
import { cn, scoreColor } from "@/lib/utils";

type Props = {
  paperId: string;
  status: "not_enriched" | "enriched" | "failed";
};

export function CitationGraphSection({ paperId, status }: Props) {
  const [localStatus, setLocalStatus] = useState(status);
  const [graph, setGraph] = useState<CitationGraphDTO | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">(status === "enriched" ? "loading" : "ready");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (status !== "enriched") return;
    const controller = new AbortController();
    fetchPaperCitations(paperId, { signal: controller.signal })
      .then((nextGraph) => {
        setGraph(nextGraph);
        setState("ready");
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });
    return () => controller.abort();
  }, [paperId, status]);

  const references = useMemo(
    () => graph?.nodes.filter((node) => node.id !== graph.paper_id) ?? [],
    [graph],
  );
  const graphNodes = useMemo(() => layoutCitationGraph(graph), [graph]);
  const actionLabel = localStatus === "enriched" ? "Refresh references" : "Fetch references";

  async function handleEnrich() {
    setMessage("Queueing citation enrichment...");
    setLocalStatus("not_enriched");
    try {
      await enrichPaperCitations(paperId);
      setMessage("Citation enrichment queued. References will appear after the worker finishes.");
    } catch {
      setMessage("Could not queue citation enrichment.");
    }
  }

  return (
    <section className="mt-10 border-t border-rule pt-7">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-sans text-[12px] font-semibold uppercase tracking-[0.16em] text-muted">
            Citation Graph
          </h2>
          <div className="mt-1 font-serif text-[15px] italic text-prose">
            References this paper builds on.
          </div>
        </div>
        <button
          type="button"
          onClick={handleEnrich}
          className="pointer-events-auto border border-rule bg-paper px-3 py-2 font-sans text-[12px] font-medium text-burgundy transition hover:bg-cream"
        >
          {actionLabel}
        </button>
      </div>

      {message && <div className="mt-3 font-sans text-[12px] text-muted-2">{message}</div>}
      {state === "loading" && (
        <div className="mt-5 font-sans text-[13px] text-muted">Loading citation graph...</div>
      )}
      {state === "error" && (
        <div className="mt-5 font-sans text-[13px] text-burgundy">
          Citation graph unavailable.
        </div>
      )}
      {state === "ready" && localStatus === "failed" && !message && (
        <div className="mt-5 font-sans text-[13px] text-burgundy">
          Citation enrichment did not find a provider match.
        </div>
      )}
      {state === "ready" && localStatus === "not_enriched" && !message && (
        <div className="mt-5 font-sans text-[13px] text-muted">
          References have not been fetched for this paper yet.
        </div>
      )}
      {state === "ready" && localStatus === "enriched" && references.length === 0 && (
        <div className="mt-5 font-sans text-[13px] text-muted">
          Semantic Scholar found this paper, but no reference rows are stored yet.
        </div>
      )}
      {references.length > 0 && (
        <>
          <CitationGraphSvg graph={graph} layout={graphNodes} />
          <div className="mt-5 divide-y divide-rule-soft border-y border-rule-soft">
            {references.map((paper) => (
              <ReferenceRow key={paper.id} paper={paper} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

type GraphLayoutNode = CitationPaperDTO & {
  x: number;
  y: number;
  radius: number;
  isSeed: boolean;
};

function layoutCitationGraph(graph: CitationGraphDTO | null): GraphLayoutNode[] {
  if (!graph) return [];
  const nodes = graph.nodes;
  const seed = nodes.find((node) => node.id === graph.paper_id) ?? nodes[0];
  if (!seed) return [];
  const references = nodes.filter((node) => node.id !== seed.id).slice(0, 24);
  const center = { x: 420, y: 220 };
  const ringRadius = references.length > 12 ? 164 : 142;
  const laidOut: GraphLayoutNode[] = [
    { ...seed, ...center, radius: 20, isSeed: true },
  ];
  references.forEach((node, index) => {
    const angle = -Math.PI / 2 + (index / Math.max(1, references.length)) * Math.PI * 2;
    const radius = ringRadius + (index % 2) * 24;
    laidOut.push({
      ...node,
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius,
      radius: node.score !== null ? 12 : 9,
      isSeed: false,
    });
  });
  return laidOut;
}

function CitationGraphSvg({
  graph,
  layout,
}: {
  graph: CitationGraphDTO | null;
  layout: GraphLayoutNode[];
}) {
  if (!graph || layout.length <= 1) return null;
  const nodeById = new Map(layout.map((node) => [node.id, node]));
  const edges = graph.edges
    .map((edge) => {
      const source = nodeById.get(edge.source);
      const target = nodeById.get(edge.target);
      return source && target ? { source, target } : null;
    })
    .filter((edge): edge is { source: GraphLayoutNode; target: GraphLayoutNode } => edge !== null);

  return (
    <div className="mt-5 border-y border-rule-soft py-4">
      <svg viewBox="0 0 840 440" role="img" aria-label="Citation graph" className="h-[360px] w-full">
        <rect x="0" y="0" width="840" height="440" fill="transparent" />
        {edges.map(({ source, target }) => (
          <line
            key={`${source.id}-${target.id}`}
            x1={source.x}
            y1={source.y}
            x2={target.x}
            y2={target.y}
            stroke="rgba(113, 93, 76, 0.34)"
            strokeWidth="1.2"
          />
        ))}
        {layout.map((node) => (
          <g key={node.id}>
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              className={cn(
                node.isSeed
                  ? "fill-burgundy stroke-burgundy"
                  : node.score !== null
                    ? "fill-accept/80 stroke-accept"
                    : "fill-paper stroke-rule",
              )}
              strokeWidth={node.isSeed ? 2 : 1.5}
            />
            <title>
              {node.title}
              {node.score !== null ? ` · Veros ${node.score.toFixed(1)}` : " · Not scored"}
            </title>
          </g>
        ))}
        <text x="420" y="256" textAnchor="middle" className="fill-muted font-mono text-[10px]">
          seed
        </text>
      </svg>
      <div className="flex flex-wrap gap-x-5 gap-y-2 font-sans text-[12px] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-burgundy" />
          Seed paper
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-accept" />
          Scored reference
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-rule bg-paper" />
          Graph-only reference
        </span>
      </div>
    </div>
  );
}

function ReferenceRow({ paper }: { paper: CitationPaperDTO }) {
  const href = `/papers/${encodeURIComponent(paper.id)}`;
  const externalHref = paper.openreview_url ?? paper.provider_url;

  return (
    <div className="grid grid-cols-[76px_minmax(0,1fr)_132px] gap-4 py-4">
      <div>
        <div className={cn("text-[24px] font-medium leading-none tabular-nums", scoreColor(paper.score))}>
          {paper.score !== null ? paper.score.toFixed(1) : "-"}
        </div>
        <div className="mt-1 font-sans text-[11px] text-muted">
          {paper.score !== null ? "Veros" : "Not scored"}
        </div>
      </div>
      <div className="min-w-0">
        <Link href={href} className="font-sans text-[15px] font-medium leading-snug text-burgundy hover:text-ink">
          {paper.title}
        </Link>
        <div className="mt-1 truncate font-sans text-[12px] text-muted-2">{paper.authors}</div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-muted">
          {paper.venue && <span>{paper.venue}</span>}
          {paper.year && <span>{paper.year}</span>}
          <span>{(paper.citations ?? 0).toLocaleString()} cites</span>
          {externalHref && (
            <a
              href={externalHref}
              target="_blank"
              rel="noopener noreferrer"
              className="relative z-10 hover:text-burgundy"
            >
              source
            </a>
          )}
        </div>
      </div>
      <div className="pt-1 text-right font-sans text-[12px] text-muted">
        {paper.references_count !== null
          ? `${paper.references_count.toLocaleString()} refs`
          : "refs unknown"}
      </div>
    </div>
  );
}
