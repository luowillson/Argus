"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultRow } from "@/components/search/ResultRow";
import { PaperPendingCard } from "@/components/search/PaperPendingCard";
import { PaginationBar } from "@/components/search/PaginationBar";
import { SortControl } from "@/components/search/SortControl";
import {
  fetchSaved,
  fetchSearchPage,
  type SearchMode,
  type SearchSortKey,
} from "@/lib/api";
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
  activeSort?: SearchSortKey;
  sortLabel?: string;
};

const DEBOUNCE_MS = 450;
const PAGE_SIZE = 20;
const MIN_LIVE_QUERY_CHARS = 3;
const SORT_LABELS: Record<SearchSortKey, string> = {
  relevance: "relevance",
  score: "Veros score",
  novelty: "novelty",
  technical: "technical",
  clarity: "clarity",
  impact: "impact",
};

function sortForQuery(query: string, sort: SearchSortKey): SearchSortKey {
  return !query && sort === "relevance" ? "score" : sort;
}

function liveSearchHref(query: string, sort: SearchSortKey) {
  const normalizedSort = sortForQuery(query, sort);
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (normalizedSort !== (query ? "relevance" : "score")) {
    params.set("sort", normalizedSort);
  }
  const qs = params.toString();
  return qs ? `/search?${qs}` : "/search";
}

function replaceBrowserUrl(href: string) {
  window.history.replaceState(window.history.state, "", href);
}

function queryFromBrowserUrl() {
  return new URLSearchParams(window.location.search).get("q")?.trim() ?? "";
}

function pageFromBrowserUrl() {
  const raw = new URLSearchParams(window.location.search).get("page");
  return Math.max(1, parseInt(raw ?? "1", 10) || 1);
}

export function SearchView({
  initialQuery,
  initialResults,
  initialFocusId,
  initialNotFound = false,
  initialPendingTitle,
  initialTotalCount,
  currentPage = 1,
  totalPages = 1,
  activeSort = "score",
  sortLabel = "Veros score",
}: Props) {
  const router = useRouter();

  const [q, setQ] = useState(initialQuery);
  const [results, setResults] = useState<Paper[]>(initialResults);
  const [focusId, setFocusId] = useState<string | null>(initialFocusId ?? null);
  const [pendingTitle, setPendingTitle] = useState<string | null>(
    initialPendingTitle ?? null,
  );
  const [notFound, setNotFound] = useState(initialNotFound);
  const [remoteTotalCount, setRemoteTotalCount] = useState(
    initialTotalCount ?? initialResults.length,
  );
  const [remoteTotalPages, setRemoteTotalPages] = useState(totalPages);
  const [displayPage, setDisplayPage] = useState(currentPage);
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());
  const [submitting, setSubmitting] = useState(false);
  const lastIssuedQ = useRef(initialQuery);

  // Pull saved-paper ids from the API (single source of truth) on mount and
  // whenever the tab regains focus, so the bookmark indicator stays fresh
  // across tabs/devices.
  useEffect(() => {
    const controller = new AbortController();
    function refreshSaved() {
      fetchSaved({ signal: controller.signal })
        .then((dtos) => setSavedIds(new Set(dtos.map((d) => d.id))))
        .catch(() => undefined);
    }
    refreshSaved();
    window.addEventListener("focus", refreshSaved);
    return () => {
      controller.abort();
      window.removeEventListener("focus", refreshSaved);
    };
  }, []);

  useEffect(() => {
    function syncInputToUrl() {
      const urlQuery = queryFromBrowserUrl();
      lastIssuedQ.current = urlQuery;
      setQ(urlQuery);
      setDisplayPage(pageFromBrowserUrl());
    }

    syncInputToUrl();
    window.addEventListener("popstate", syncInputToUrl);
    return () => {
      window.removeEventListener("popstate", syncInputToUrl);
    };
  }, []);

  // Debounced live topic search on typing.
  useEffect(() => {
    if (q === lastIssuedQ.current) return;
    const trimmed = q.trim();
    if (trimmed.length > 0 && trimmed.length < MIN_LIVE_QUERY_CHARS) return;
    const controller = new AbortController();
    const handle = setTimeout(async () => {
      lastIssuedQ.current = q;
      try {
        const normalizedSort = sortForQuery(trimmed, activeSort);
        const page = await fetchSearchPage(
          trimmed,
          PAGE_SIZE,
          0,
          "topic",
          normalizedSort,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        setResults(page.results.map(adaptPaperOut));
        setRemoteTotalCount(page.total);
        setRemoteTotalPages(Math.max(1, Math.ceil(page.total / PAGE_SIZE)));
        setFocusId(null);
        setPendingTitle(null);
        setNotFound(false);
        setDisplayPage(1);
        replaceBrowserUrl(liveSearchHref(trimmed, normalizedSort));
      } catch (err) {
        if ((err as { name?: string })?.name !== "AbortError") {
          // Keep prior results on error.
        }
      }
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(handle);
      controller.abort();
    };
  }, [activeSort, q]);

  async function handleSubmit(query: string) {
    const trimmed = query.trim();
    if (!trimmed) {
      lastIssuedQ.current = "";
      setQ("");
      const mode: SearchMode = "topic";
      try {
        const page = await fetchSearchPage("", PAGE_SIZE, 0, mode, "score");
        setResults(page.results.map(adaptPaperOut));
        setRemoteTotalCount(page.total);
        setRemoteTotalPages(Math.max(1, Math.ceil(page.total / PAGE_SIZE)));
      } catch {
        setResults([]);
        setRemoteTotalCount(0);
        setRemoteTotalPages(1);
      }
      setFocusId(null);
      setPendingTitle(null);
      setNotFound(false);
      setDisplayPage(1);
      replaceBrowserUrl("/search");
      return;
    }
    if (submitting) return;
    setSubmitting(true);
    try {
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
    remoteTotalCount ?? orderedResults.length + (showPendingCard ? 1 : 0);
  const effectiveTotalPages = remoteTotalPages || totalPages;
  const trimmedQuery = q.trim();
  const showSavedIndicators = !trimmedQuery && !focusId;
  const effectiveSort = sortForQuery(trimmedQuery, activeSort);
  const effectiveSortLabel =
    trimmedQuery && effectiveSort === "relevance"
      ? "sorted by relevance"
      : `sorted by ${SORT_LABELS[effectiveSort] ?? sortLabel}`;

  return (
    <div className="min-h-screen bg-paper">
      <SearchHeaderBar
        initialQuery={initialQuery}
        value={q}
        onChange={setQ}
        onSubmitOverride={handleSubmit}
      />

      <div className="mx-auto max-w-[1100px] px-6 pt-9 pb-1.5 sm:px-10 lg:px-16">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          {trimmedQuery ? (
            <>
              Results for{" "}
              <em className="font-serif italic text-burgundy">
                &ldquo;{trimmedQuery}&rdquo;
              </em>
            </>
          ) : (
            <>All papers</>
          )}
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {totalCount.toLocaleString()} papers · {effectiveSortLabel}
          {submitting && " · looking up…"}
        </div>
        {!focusId && (
          <div className="mt-4">
            <SortControl query={trimmedQuery} activeSort={effectiveSort} />
          </div>
        )}
        {notFound && (
          <div className="mt-3 border-l-2 border-burgundy/60 bg-cream/50 px-3 py-2 font-sans text-[13px] text-prose">
            We couldn&rsquo;t find a paper matching{" "}
            <em className="font-serif italic">&ldquo;{trimmedQuery}&rdquo;</em>{" "}
            on OpenReview. Showing closest matches from your library instead.
          </div>
        )}
      </div>

      <div className="mx-auto max-w-[1100px] px-6 pb-16 sm:px-10 lg:px-16">
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
                saved={showSavedIndicators && savedIds.has(p.id)}
              />
            ))}
            {!focusId && (
              <PaginationBar
                query={trimmedQuery}
                currentPage={displayPage}
                totalPages={effectiveTotalPages}
                activeSort={effectiveSort}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
