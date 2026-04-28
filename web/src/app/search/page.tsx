import { SearchView } from "@/components/search/SearchView";
import { fetchSearchPage, type SearchSortKey } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import type { Paper } from "@/lib/types";

const SORT_LABELS: Record<SearchSortKey, string> = {
  relevance: "relevance",
  score: "Veros score",
  novelty: "novelty",
  technical: "technical",
  clarity: "clarity",
  impact: "impact",
};

function parseSort(value: string | undefined, hasQuery: boolean): SearchSortKey {
  if (
    value === "relevance" ||
    value === "score" ||
    value === "novelty" ||
    value === "technical" ||
    value === "clarity" ||
    value === "impact"
  ) {
    return value;
  }
  return hasQuery ? "relevance" : "score";
}

const PAGE_SIZE = 20;

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    sort?: string;
    page?: string;
    focus?: string;
    notFound?: string;
    pending?: string;
  }>;
}) {
  const {
    q = "",
    sort,
    page: pageParam = "1",
    focus,
    notFound,
    pending,
  } = await searchParams;
  const query = q.trim();
  const activeSort = parseSort(sort, Boolean(query));
  const currentPage = Math.max(1, parseInt(pageParam, 10) || 1);
  const offset = (currentPage - 1) * PAGE_SIZE;
  const mode = focus ? "specific" : "auto";

  let initialResults: Paper[] = [];
  let initialTotalCount = 0;
  try {
    const page = await fetchSearchPage(query, PAGE_SIZE, offset, mode, activeSort);
    initialResults = page.results.map(adaptPaperOut);
    initialTotalCount = page.total;
  } catch {
    // Server-side fetch failed; client component will retry on mount.
  }
  const totalPages = Math.max(1, Math.ceil(initialTotalCount / PAGE_SIZE));

  return (
    <SearchView
      key={[
        query,
        activeSort,
        currentPage,
        focus ?? "",
        notFound ?? "",
        pending ?? "",
      ].join(":")}
      initialQuery={query}
      initialResults={initialResults}
      initialFocusId={focus}
      initialNotFound={notFound === "1"}
      initialPendingTitle={pending}
      initialTotalCount={initialTotalCount}
      currentPage={currentPage}
      totalPages={totalPages}
      activeSort={activeSort}
      sortLabel={SORT_LABELS[activeSort]}
    />
  );
}
