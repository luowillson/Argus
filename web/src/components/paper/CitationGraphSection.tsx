"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const POLL_INTERVAL_MS = 3_000;
const MAX_POLL_ATTEMPTS = 60; // stop after ~3 minutes
const PAGE_SIZE = 20;

export function CitationGraphSection({ paperId, status }: Props) {
  const [localStatus, setLocalStatus] = useState(status);
  const [graph, setGraph] = useState<CitationGraphDTO | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">(status === "enriched" ? "loading" : "ready");
  const [message, setMessage] = useState<string>("");
  const [polling, setPolling] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollCountRef = useRef(0);

  // Search & pagination state
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  /** Fetch and apply the citation graph. Returns true if enrichment is done. */
  const loadGraph = useCallback(
    async (signal?: AbortSignal): Promise<boolean> => {
      try {
        const nextGraph = await fetchPaperCitations(paperId, signal ? { signal } : undefined);
        setGraph(nextGraph);
        setState("ready");
        if (nextGraph.status === "enriched") {
          const refs = nextGraph.nodes.filter((n) => n.id !== nextGraph.paper_id);
          if (refs.length > 0) {
            setLocalStatus("enriched");
            setMessage("");
            return true;
          }
        }
        if (nextGraph.status === "failed") {
          setLocalStatus("failed");
          setMessage("Citation enrichment did not find a provider match.");
          return true;
        }
        return false;
      } catch {
        if (!signal?.aborted) setState("error");
        return true; // stop polling on hard error
      }
    },
    [paperId],
  );

  // Initial load when paper is already enriched
  useEffect(() => {
    if (status !== "enriched") return;
    const controller = new AbortController();
    loadGraph(controller.signal);
    return () => controller.abort();
  }, [paperId, status, loadGraph]);

  // Polling loop — started by handleEnrich, stopped when enrichment completes
  useEffect(() => {
    if (!polling) return;
    const controller = new AbortController();

    async function tick() {
      if (controller.signal.aborted) return;
      pollCountRef.current += 1;

      if (pollCountRef.current > MAX_POLL_ATTEMPTS) {
        setPolling(false);
        setMessage("Enrichment is taking longer than expected. Try refreshing the page later.");
        return;
      }

      const done = await loadGraph(controller.signal);
      if (done || controller.signal.aborted) {
        setPolling(false);
        return;
      }

      const elapsed = pollCountRef.current * Math.round(POLL_INTERVAL_MS / 1000);
      setMessage(`Fetching references… (${elapsed}s elapsed)`);
      pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    }

    // Start with a small initial delay to give the worker time to begin
    pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);

    return () => {
      controller.abort();
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [polling, loadGraph]);

  const references = useMemo(
    () => graph?.nodes.filter((node) => node.id !== graph.paper_id) ?? [],
    [graph],
  );
  const actionLabel = localStatus === "enriched" ? "Refresh references" : "Fetch references";

  // Search filtering
  const filtered = useMemo(() => {
    if (!search.trim()) return references;
    const terms = search.toLowerCase().split(/\s+/).filter(Boolean);
    return references.filter((p) => {
      const haystack = `${p.title} ${p.authors} ${p.venue ?? ""} ${p.year ?? ""}`.toLowerCase();
      return terms.every((t) => haystack.includes(t));
    });
  }, [references, search]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const pageStart = safePage * PAGE_SIZE;
  const pageEnd = Math.min(pageStart + PAGE_SIZE, filtered.length);
  const pageSlice = filtered.slice(pageStart, pageEnd);

  // Reset to first page when search changes
  useEffect(() => { setPage(0); }, [search]);

  async function handleEnrich() {
    setMessage("Queueing citation enrichment\u2026");
    setLocalStatus("not_enriched");
    setState("loading");
    pollCountRef.current = 0;
    try {
      await enrichPaperCitations(paperId);
      setMessage("Citation enrichment queued. Waiting for worker\u2026");
      setPolling(true);
    } catch {
      setMessage("Could not queue citation enrichment.");
      setState("ready");
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
          disabled={polling}
          className={cn(
            "pointer-events-auto border border-rule bg-paper px-3 py-2 font-sans text-[12px] font-medium transition",
            polling ? "cursor-wait text-muted" : "text-burgundy hover:bg-cream",
          )}
        >
          {polling ? "Fetching\u2026" : actionLabel}
        </button>
      </div>

      {message && (
        <div className="mt-3 flex items-center gap-2 font-sans text-[12px] text-muted-2">
          {polling && (
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-burgundy/60" />
          )}
          {message}
        </div>
      )}
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

          {/* Search + summary bar */}
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <div className="relative">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search references…"
                className="w-[280px] border border-rule bg-paper py-2 pl-8 pr-3 font-sans text-[13px] text-ink placeholder:text-muted-2 focus:border-burgundy focus:outline-none"
              />
              <svg
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
              </svg>
            </div>
            <div className="font-sans text-[12px] text-muted tabular-nums">
              {search.trim()
                ? `${filtered.length} of ${references.length} references`
                : `${references.length} references`}
              {filtered.length > PAGE_SIZE && ` · showing ${pageStart + 1}\u2013${pageEnd}`}
            </div>
          </div>

          {/* Reference rows */}
          {filtered.length === 0 && search.trim() && (
            <div className="mt-5 font-sans text-[13px] text-muted">
              No references match &ldquo;{search.trim()}&rdquo;
            </div>
          )}
          {pageSlice.length > 0 && (
            <div className="mt-2 divide-y divide-rule-soft border-y border-rule-soft">
              {pageSlice.map((paper) => (
                <ReferenceRow key={paper.id} paper={paper} />
              ))}
            </div>
          )}

          {/* Pagination controls */}
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                type="button"
                disabled={safePage === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className={cn(
                  "border border-rule bg-paper px-3 py-1.5 font-sans text-[12px] font-medium transition",
                  safePage === 0 ? "cursor-not-allowed text-muted/40" : "text-burgundy hover:bg-cream",
                )}
              >
                ← Prev
              </button>
              <span className="px-2 font-mono text-[12px] text-muted tabular-nums">
                {safePage + 1} / {totalPages}
              </span>
              <button
                type="button"
                disabled={safePage >= totalPages - 1}
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                className={cn(
                  "border border-rule bg-paper px-3 py-1.5 font-sans text-[12px] font-medium transition",
                  safePage >= totalPages - 1 ? "cursor-not-allowed text-muted/40" : "text-burgundy hover:bg-cream",
                )}
              >
                Next →
              </button>
            </div>
          )}
        </>
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
