"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AuthorRankingSearch } from "@/components/ranking/AuthorRankingSearch";
import { AuthorRankingTable } from "@/components/ranking/AuthorRankingTable";
import {
  type AuthorRankingDTO,
  type AuthorRankingOrder,
} from "@/lib/api";
import {
  LOCAL_CORPUS_UPDATED_EVENT,
  searchLocalAuthorRankings,
} from "@/lib/localPapers";
import { cn } from "@/lib/utils";

type Mode = AuthorRankingOrder | "search";

type Props = {
  initialRankings: AuthorRankingDTO[];
  initialMode?: Mode;
  initialQuery?: string;
};

const COPY: Record<Mode, string> = {
  best: "Top 100 authors by average Veros Score. Only authors with at least three scored papers are included.",
  worst: "Bottom 100 authors by average Veros Score. Only authors with at least three scored papers are included.",
  search: "Search any author in the database, including authors with fewer than three scored papers.",
};

function normalizedQueryForMode(mode: Mode, query: string) {
  return mode === "search" ? query.trim() : "";
}

function cacheKey(mode: Mode, query: string) {
  return `${mode}:${query.toLowerCase()}`;
}

function fetchRankings(mode: Mode, query: string) {
  return mode === "search"
    ? searchLocalAuthorRankings(500, 1, "best", query)
    : searchLocalAuthorRankings(100, 3, mode);
}

export function AuthorRankingView({
  initialRankings,
  initialMode = "best",
  initialQuery = "",
}: Props) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [rankings, setRankings] = useState(initialRankings);
  const [query, setQuery] = useState(initialQuery);
  const [loading, setLoading] = useState(initialRankings.length === 0);
  const [error, setError] = useState(false);
  const cache = useRef(
    new Map<string, AuthorRankingDTO[]>([
      [cacheKey(initialMode, normalizedQueryForMode(initialMode, initialQuery)), initialRankings],
    ]),
  );

  const load = useCallback(async (nextMode: Mode, nextQuery = "") => {
    const normalizedQuery = normalizedQueryForMode(nextMode, nextQuery);
    const key = cacheKey(nextMode, normalizedQuery);
    setMode(nextMode);
    setQuery(normalizedQuery);

    const cached = cache.current.get(key);
    if (cached) {
      setRankings(cached);
      setError(false);
      return;
    }

    setLoading(true);
    setError(false);
    try {
      const next = await fetchRankings(nextMode, normalizedQuery);
      cache.current.set(key, next);
      setRankings(next);
    } catch {
      setRankings([]);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const normalizedQuery = normalizedQueryForMode(initialMode, initialQuery);
    const key = cacheKey(initialMode, normalizedQuery);
    cache.current.clear();

    async function hydrateRankings() {
      try {
        const next = await fetchRankings(initialMode, normalizedQuery);
        if (cancelled) return;
        cache.current.set(key, next);
        setMode(initialMode);
        setQuery(normalizedQuery);
        setRankings(next);
        setError(false);
      } catch {
        if (cancelled) return;
        setRankings([]);
        setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void hydrateRankings();
    return () => {
      cancelled = true;
    };
  }, [initialMode, initialQuery]);

  useEffect(() => {
    function refreshRankings() {
      cache.current.clear();
      void load(mode, query);
    }

    window.addEventListener(LOCAL_CORPUS_UPDATED_EVENT, refreshRankings);
    return () => {
      window.removeEventListener(LOCAL_CORPUS_UPDATED_EVENT, refreshRankings);
    };
  }, [load, mode, query]);

  function submitSearch(nextQuery: string) {
    void load("search", nextQuery);
  }

  return (
    <>
      <div className="border-b border-rule pb-6">
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
          Ranking
        </p>
        <h1 className="mt-2 text-[34px] font-medium tracking-[-0.015em]">
          Author rankings
        </h1>
        <p className="mt-3 max-w-[920px] font-sans text-[14px] leading-[1.6] text-muted-2">
          {COPY[mode]}
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <div className="flex gap-3 font-sans text-[13px]">
            <button
              type="button"
              onClick={() => void load("best")}
              className={cn(
                "cursor-pointer whitespace-nowrap border px-3 py-1",
                mode === "best"
                  ? "border-burgundy bg-cream text-burgundy"
                  : "border-rule text-muted-2 hover:border-burgundy hover:text-burgundy",
              )}
            >
              Top 100
            </button>
            <button
              type="button"
              onClick={() => void load("worst")}
              className={cn(
                "cursor-pointer whitespace-nowrap border px-3 py-1",
                mode === "worst"
                  ? "border-burgundy bg-cream text-burgundy"
                  : "border-rule text-muted-2 hover:border-burgundy hover:text-burgundy",
              )}
            >
              Bottom 100
            </button>
          </div>
          <AuthorRankingSearch
            key={`${mode}:${query}`}
            query={query}
            onSubmit={submitSearch}
          />
        </div>
      </div>

      {loading ? (
        <div className="py-16 text-center font-sans text-[14px] text-muted">
          Loading author rankings...
        </div>
      ) : error ? (
        <div className="py-16 text-center font-sans text-[14px] text-muted">
          Author rankings are still warming up. Try again in a moment.
        </div>
      ) : mode === "search" && !query ? (
        <div className="py-16 text-center font-sans text-[14px] text-muted">
          Search for an author to see their rating.
        </div>
      ) : (
        <AuthorRankingTable rankings={rankings} order={mode === "worst" ? "worst" : "best"} />
      )}
    </>
  );
}
