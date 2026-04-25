import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { VEROS_PAPERS } from "@/lib/mock-papers";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const query = q.trim();

  // M1: filter mock list by simple substring on title/authors/tldr.
  // M7 will replace this with the API + pgvector cosine search.
  const filtered = query
    ? VEROS_PAPERS.filter((p) => {
        const hay = `${p.title} ${p.authors} ${p.tldr} ${p.venue}`.toLowerCase();
        return hay.includes(query.toLowerCase());
      })
    : VEROS_PAPERS;

  const results = [...filtered].sort((a, b) => b.score - a.score);

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
