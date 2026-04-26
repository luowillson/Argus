import { SearchView } from "@/components/search/SearchView";
import { fetchSearch, fetchSearchCount, type SearchSortKey } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";
import type { Paper } from "@/lib/types";

const SORT_LABELS: Record<SearchSortKey, string> = {
  relevance: "relevance",
  score: "Veros score",
  novelty: "novelty",
  technical: "technical",
  clarity: "clarity",
  impact: "impact",
};

function parseSort(
  value: string | undefined,
  hasQuery: boolean,
): SearchSortKey {
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
  const mode = focus ? "specific" : "topic";

  let results: Paper[] = [];
  let totalPages = 1;
  let totalCount = 0;
  let fromApi = false;

  try {
    const [dtos, total] = await Promise.all([
      fetchSearch(query, PAGE_SIZE, offset, mode, activeSort),
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
    const sorted = [...all].sort((a, b) => {
      if (activeSort === "relevance") {
        const qn = query.toLowerCase();
        const rank = (paper: Paper) => {
          const title = paper.title.toLowerCase();
          const abstract = paper.tldr.toLowerCase();
          return (
            (title.includes(qn) ? 2 : 0) +
            (abstract.includes(qn) ? 1 : 0)
          );
        };
        return rank(b) - rank(a) || (b.score ?? 0) - (a.score ?? 0);
      }
      const left = activeSort === "score" ? (a.score ?? 0) : a[activeSort];
      const right = activeSort === "score" ? (b.score ?? 0) : b[activeSort];
      return right - left || (b.score ?? 0) - (a.score ?? 0);
    });
    totalCount = sorted.length;
    totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
    results = sorted.slice(offset, offset + PAGE_SIZE);
  }

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
      initialResults={results}
      initialFocusId={focus}
      initialNotFound={notFound === "1"}
      initialPendingTitle={pending}
      initialTotalCount={totalCount}
      currentPage={currentPage}
      totalPages={totalPages}
      activeSort={activeSort}
      sortLabel={SORT_LABELS[activeSort]}
      sortExplicit={sort !== undefined || Boolean(query)}
    />
  );
}
