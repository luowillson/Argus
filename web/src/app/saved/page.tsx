"use client";

import { useEffect, useState } from "react";
import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { fetchSaved } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import type { Paper } from "@/lib/types";

export default function SavedPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchSaved({ signal: controller.signal })
      .then((dtos) => {
        if (controller.signal.aborted) return;
        setPapers(dtos.map(adaptPaperOut));
        setLoaded(true);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Failed to load saved papers");
        setLoaded(true);
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="min-h-screen bg-paper">
      <SearchHeaderBar />

      <div className="mx-auto max-w-[1100px] px-6 pt-9 pb-1.5 sm:px-10 lg:px-16">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          Your reading list
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {papers.length} paper{papers.length !== 1 ? "s" : ""} saved
        </div>
      </div>

      <div className="mx-auto max-w-[1100px] px-6 pb-16 sm:px-10 lg:px-16">
        {!loaded ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            Loading saved papers…
          </div>
        ) : error ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            {error}
          </div>
        ) : papers.length === 0 ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            No papers saved yet. Click{" "}
            <span className="font-medium text-ink">Save</span> on any paper to
            add it here.
          </div>
        ) : (
          <ResultsGrid papers={papers} />
        )}
      </div>
    </div>
  );
}
