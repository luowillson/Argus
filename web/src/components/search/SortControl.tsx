import Link from "next/link";
import type { SearchSortKey } from "@/lib/api";
import { cn } from "@/lib/utils";

const SORT_OPTIONS: { key: SearchSortKey; label: string }[] = [
  { key: "relevance", label: "Relevance" },
  { key: "score", label: "Veros score" },
  { key: "novelty", label: "Novelty" },
  { key: "technical", label: "Technical" },
  { key: "clarity", label: "Clarity" },
  { key: "impact", label: "Impact" },
];

type Props = {
  query: string;
  activeSort: SearchSortKey;
};

function hrefFor(query: string, sort: SearchSortKey): string {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (query) {
    params.set("sort", sort);
  } else if (sort !== "score") {
    params.set("sort", sort);
  }
  const qs = params.toString();
  return qs ? `/search?${qs}` : "/search";
}

export function SortControl({ query, activeSort }: Props) {
  const options = query
    ? SORT_OPTIONS
    : SORT_OPTIONS.filter((option) => option.key !== "relevance");

  return (
    <div className="flex flex-wrap items-center gap-2 font-sans text-[12px]">
      <span className="mr-1 text-muted">Sort by</span>
      {options.map((option) => {
        const active = option.key === activeSort;
        return (
          <Link
            key={option.key}
            href={hrefFor(query, option.key)}
            className={cn(
              "cursor-pointer border border-rule px-2.5 py-1 transition hover:border-burgundy hover:text-burgundy",
              active && "border-burgundy bg-cream text-burgundy",
            )}
          >
            {option.label}
          </Link>
        );
      })}
    </div>
  );
}
