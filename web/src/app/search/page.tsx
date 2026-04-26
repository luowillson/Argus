import { SearchHeaderBar } from "@/components/nav/SearchHeaderBar";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { PaginationBar } from "@/components/search/PaginationBar";
import { fetchSearch, fetchSearchCount } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";
import type { Paper } from "@/lib/types";

const PAGE_SIZE = 20;

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const { q = "", page: pageParam = "1" } = await searchParams;
  const query = q.trim();
  const currentPage = Math.max(1, parseInt(pageParam, 10) || 1);
  const offset = (currentPage - 1) * PAGE_SIZE;

  let results: Paper[] = [];
  let totalPages = 1;
  let totalCount = 0;
  let fromApi = false;

  try {
    const [dtos, total] = await Promise.all([
      fetchSearch(query, PAGE_SIZE, offset),
      fetchSearchCount(query),
    ]);
    if (total > 0 || dtos.length > 0) {
      results = dtos.map(adaptPaperOut);
      totalCount = total;
      totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      fromApi = true;
    }
  } catch {
    // API unreachable — fall through to mock data.
  }

  if (!fromApi) {
    const all = query
      ? VEROS_PAPERS.filter((p) => {
          const hay = `${p.title} ${p.authors} ${p.tldr} ${p.venue}`.toLowerCase();
          return hay.includes(query.toLowerCase());
        })
      : VEROS_PAPERS;
    const sorted = [...all].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    totalCount = sorted.length;
    totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
    results = sorted.slice(offset, offset + PAGE_SIZE);
  }

  const pageLabel =
    totalPages > 1 ? ` · page ${currentPage} of ${totalPages}` : "";

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
          {totalCount.toLocaleString()} papers · sorted by Veros score{pageLabel}
        </div>
      </div>

      <div className="px-16 pb-16">
        <ResultsGrid papers={results} />
        <PaginationBar query={query} currentPage={currentPage} totalPages={totalPages} />
      </div>
    </div>
  );
}
