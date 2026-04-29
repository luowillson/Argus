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

  async function handleEnrich() {
    setMessage("Queueing citation enrichment...");
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
        {status !== "enriched" && (
          <button
            type="button"
            onClick={handleEnrich}
            className="pointer-events-auto border border-rule bg-paper px-3 py-2 font-sans text-[12px] font-medium text-burgundy transition hover:bg-cream"
          >
            Fetch references
          </button>
        )}
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
      {state === "ready" && status === "failed" && (
        <div className="mt-5 font-sans text-[13px] text-burgundy">
          Citation enrichment did not find a provider match.
        </div>
      )}
      {state === "ready" && status === "not_enriched" && !message && (
        <div className="mt-5 font-sans text-[13px] text-muted">
          References have not been fetched for this paper yet.
        </div>
      )}
      {state === "ready" && status === "enriched" && references.length === 0 && (
        <div className="mt-5 font-sans text-[13px] text-muted">No references stored yet.</div>
      )}
      {references.length > 0 && (
        <div className="mt-5 divide-y divide-rule-soft border-y border-rule-soft">
          {references.map((paper) => (
            <ReferenceRow key={paper.id} paper={paper} />
          ))}
        </div>
      )}
    </section>
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
