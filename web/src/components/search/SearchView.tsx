"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultRow } from "@/components/search/ResultRow";
import { PaperPendingCard } from "@/components/search/PaperPendingCard";
import { PaginationBar } from "@/components/search/PaginationBar";
import { fetchSearchLive } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { submitSearch } from "@/lib/searchSubmit";
import type { Paper } from "@/lib/types";

type Props = {
  initialQuery: string;
  initialResults: Paper[];
  initialFocusId?: string;
  initialNotFound?: boolean;
  initialPendingTitle?: string;
  initialTotalCount?: number;
  currentPage?: number;
  totalPages?: number;
};

const DEBOUNCE_MS = 250;

export function SearchView({
  initialQuery,
  initialResults,
  initialFocusId,
  initialNotFound = false,
  initialPendingTitle,
  initialTotalCount,
  currentPage = 1,
  totalPages = 1,
}: Props) {
  const router = useRouter();

  const [q, setQ] = useState(initialQuery);
  const [results, setResults] = useState<Paper[]>(initialResults);
  const [focusId, setFocusId] = useState<string | null>(initialFocusId ?? null);
  const [pendingTitle, setPendingTitle] = useState<string | null>(
    initialPendingTitle ?? null,
  );
  const [notFound, setNotFound] = useState(initialNotFound);
  const [submitting, setSubmitting] = useState(false);
  const [sortMode, setSortMode] = useState<"score" | "relevance">(
    initialFocusId ? "relevance" : "score",
  );

  // Debounced live topic search on typing.
  const lastIssuedQ = useRef(initialQuery);
  useEffect(() => {
    if (q === lastIssuedQ.current) return;
    const trimmed = q.trim();
    const controller = new AbortController();
    const handle = setTimeout(async () => {
      lastIssuedQ.current = q;
      try {
        const dtos = await fetchSearchLive(trimmed, controller.signal);
        const mapped = dtos.map(adaptPaperOut);
        // Live typing always re-enters topic mode and clears focus/notFound.
        setResults(mapped);
        setFocusId(null);
        setPendingTitle(null);
        setNotFound(false);
        setSortMode("score");
      } catch (err) {
        if ((err as { name?: string })?.name !== "AbortError") {
          // swallow other errors silently — keep prior results
        }
      }
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(handle);
      controller.abort();
    };
  }, [q]);

  async function handleSubmit(query: string) {
    if (!query.trim() || submitting) return;
    setSubmitting(true);
    try {
      // submitSearch handles the URL/ID fast-path, the lookupSearch call,
      // and navigation. The page server-renders the new params and SearchView
      // re-mounts with the right initial state.
      await submitSearch(query, router, { replace: true });
    } finally {
      setSubmitting(false);
    }
  }

  // Reorder results so the focused paper sits first.
  const orderedResults = (() => {
    if (!focusId) return results;
    const focused = results.find((p) => p.id === focusId);
    if (!focused) return results;
    return [focused, ...results.filter((p) => p.id !== focusId)];
  })();

  const showPendingCard = focusId && pendingTitle && !results.some((p) => p.id === focusId);
  const totalCount =
    initialTotalCount ?? orderedResults.length + (showPendingCard ? 1 : 0);
  const sortLabel =
    sortMode === "relevance" ? "sorted by relevance" : "sorted by Veros score";

  return (
    <div className="min-h-screen bg-paper">
      <SearchHeaderBar
        initialQuery={initialQuery}
        value={q}
        onChange={setQ}
        onSubmitOverride={handleSubmit}
      />

      <div className="px-16 pt-9 pb-1.5">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          {q.trim() ? (
            <>
              Results for{" "}
              <em className="font-serif italic text-burgundy">
                &ldquo;{q.trim()}&rdquo;
              </em>
            </>
          ) : (
            <>All papers</>
          )}
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {totalCount.toLocaleString()} papers · {sortLabel}
          {submitting && " · looking up…"}
        </div>
        {notFound && (
          <div className="mt-3 border-l-2 border-burgundy/60 bg-cream/50 px-3 py-2 font-sans text-[13px] text-prose">
            We couldn&rsquo;t find a paper matching{" "}
            <em className="font-serif italic">&ldquo;{q.trim()}&rdquo;</em>{" "}
            on OpenReview. Showing closest matches from your library instead.
          </div>
        )}
      </div>

      <div className="px-16 pb-16">
        {totalCount === 0 ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            No papers match this query yet. Try a different keyword or paste a
            forum URL.
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-[92px_minmax(0,1.55fr)_150px_220px] gap-5 border-b border-rule pb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
              <span>Score</span>
              <span>Paper</span>
              <span>Venue</span>
              <span>Metrics</span>
            </div>
            {showPendingCard && (
              <PaperPendingCard
                paperId={focusId!}
                title={pendingTitle!}
                isFirst
              />
            )}
            {orderedResults.map((p, i) => (
              <ResultRow
                key={p.id}
                paper={p}
                isFirst={!showPendingCard && i === 0}
              />
            ))}
            {!focusId && (
              <PaginationBar
                query={initialQuery}
                currentPage={currentPage}
                totalPages={totalPages}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
