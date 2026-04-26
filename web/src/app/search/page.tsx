import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { SortControl } from "@/components/search/SortControl";
import { fetchSearch, type SearchSortKey } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";
import type { Paper } from "@/lib/types";

const SORT_LABELS: Record<SearchSortKey, string> = {
  score: "Veros score",
  novelty: "novelty",
  technical: "technical",
  clarity: "clarity",
  impact: "impact",
};

function parseSort(value: string | undefined): SearchSortKey {
  if (
    value === "novelty" ||
    value === "technical" ||
    value === "clarity" ||
    value === "impact"
  ) {
    return value;
  }
  return "score";
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; sort?: string }>;
}) {
  const { q = "", sort } = await searchParams;
  const query = q.trim();
  const activeSort = parseSort(sort);

  let results: Paper[] = [];
  let fromApi = false;

  try {
    const dtos = await fetchSearch(query, 20, 0, activeSort);
    if (dtos.length > 0) {
      results = dtos.map(adaptPaperOut);
      fromApi = true;
    }
  } catch {
    // API unreachable — fall through to mock data.
  }

  if (!fromApi) {
    const filtered = query
      ? VEROS_PAPERS.filter((p) => {
          const hay = `${p.title} ${p.authors} ${p.tldr} ${p.venue}`.toLowerCase();
          return hay.includes(query.toLowerCase());
        })
      : VEROS_PAPERS;
    results = [...filtered].sort((a, b) => {
      const left = activeSort === "score" ? (a.score ?? 0) : a[activeSort];
      const right = activeSort === "score" ? (b.score ?? 0) : b[activeSort];
      return right - left || (b.score ?? 0) - (a.score ?? 0);
    });
  }

  return (
    <div className="min-h-screen bg-paper">
      <SearchHeaderBar initialQuery={query} />

      <div className="px-16 pt-9 pb-1.5">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          {query ? (
            <>
              Results for{" "}
              <em className="font-serif italic text-burgundy">
                &ldquo;{query}&rdquo;
              </em>
            </>
          ) : (
            <>All papers</>
          )}
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {results.length.toLocaleString()} papers · sorted by {SORT_LABELS[activeSort]}
        </div>
        <div className="mt-4">
          <SortControl query={query} activeSort={activeSort} />
        </div>
      </div>

      <div className="px-16 pb-16">
        <ResultsGrid papers={results} />
      </div>
    </div>
  );
}
