import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { fetchSearch } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";
import type { Paper } from "@/lib/types";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const query = q.trim();

  let results: Paper[] = [];
  let fromApi = false;

  try {
    const dtos = await fetchSearch(query);
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
    results = [...filtered].sort((a, b) => b.score - a.score);
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
          {results.length.toLocaleString()} papers · sorted by Veros score
        </div>
      </div>

      <div className="px-16 pb-16">
        <ResultsGrid papers={results} />
      </div>
    </div>
  );
}
