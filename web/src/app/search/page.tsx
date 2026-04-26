import { SearchView } from "@/components/search/SearchView";
import { fetchSearch } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";
import type { Paper } from "@/lib/types";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    focus?: string;
    notFound?: string;
    pending?: string;
  }>;
}) {
  const {
    q = "",
    focus,
    notFound,
    pending,
  } = await searchParams;
  const query = q.trim();
  const mode = focus ? "specific" : "topic";

  let results: Paper[] = [];
  let fromApi = false;

  try {
    const dtos = await fetchSearch(query, 20, 0, mode);
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
    results = [...filtered].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  }

  return (
    <SearchView
      initialQuery={query}
      initialResults={results}
      initialFocusId={focus}
      initialNotFound={notFound === "1"}
      initialPendingTitle={pending}
    />
  );
}
