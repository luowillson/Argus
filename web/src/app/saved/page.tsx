"use client";

import { useEffect, useState } from "react";
import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import {
  type PaperDetailDTO,
  fetchPaperClient,
  getCachedPaper,
  getLocalSavedPaperIds,
} from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { localSavedPapers } from "@/lib/localPapers";
import type { Paper } from "@/lib/types";

export default function SavedPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [savedCount, setSavedCount] = useState(0);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSavedPapers() {
      const ids = getLocalSavedPaperIds();
      const cached = ids
        .map((id) => getCachedPaper(id))
        .filter((paper): paper is PaperDetailDTO => paper !== null);
      const localPapers = await localSavedPapers(ids);

      if (cancelled) return;
      setSavedCount(ids.length);
      setPapers(localPapers.length > 0 ? localPapers : cached.map(adaptPaperDetail));
      setLoaded(true);

      const visibleIds = new Set(localPapers.map((paper) => paper.id));
      cached.forEach((paper) => visibleIds.add(paper.id));
      const missing = ids.filter((id) => !visibleIds.has(id));
      if (missing.length === 0) return;

      const fetched = await Promise.all(
        missing.map((id) =>
          fetchPaperClient(id).catch(() => null),
        ),
      );
      if (cancelled) return;

      const hydrated = fetched.filter(
        (paper) => paper && paper !== "queued" && paper !== "failed",
      );
      setPapers((current) => {
        const byId = new Map(current.map((paper) => [paper.id, paper]));
        hydrated.forEach((paper) => {
          if (paper && paper !== "queued" && paper !== "failed") {
            byId.set(paper.id, adaptPaperDetail(paper));
          }
        });
        return ids.map((id) => byId.get(id)).filter((paper) => paper !== undefined);
      });
    }

    loadSavedPapers();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-paper">
      <SearchHeaderBar />

      <div className="px-16 pt-9 pb-1.5">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          Your reading list
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {savedCount} paper{savedCount !== 1 ? "s" : ""} saved
        </div>
      </div>

      <div className="px-16 pb-16">
        {loaded && savedCount === 0 ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            No papers saved yet. Click{" "}
            <span className="font-medium text-ink">Save</span> on any paper to
            add it here.
          </div>
        ) : papers.length === 0 ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            Loading saved papers…
          </div>
        ) : (
          <ResultsGrid papers={papers} />
        )}
      </div>
    </div>
  );
}
