import Link from "next/link";

interface Props {
  query: string;
  currentPage: number;
  totalPages: number;
}

function pageHref(query: string, page: number) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  params.set("page", String(page));
  return `/search?${params.toString()}`;
}

export function PaginationBar({ query, currentPage, totalPages }: Props) {
  if (totalPages <= 1) return null;

  // Build visible page numbers: always show first, last, current ±2, with ellipsis gaps.
  const pages: (number | "…")[] = [];
  const addPage = (n: number) => {
    if (n < 1 || n > totalPages) return;
    if (pages[pages.length - 1] !== n) pages.push(n);
  };

  const near = new Set([1, totalPages, currentPage - 2, currentPage - 1, currentPage, currentPage + 1, currentPage + 2].filter((n) => n >= 1 && n <= totalPages));
  let prev = 0;
  for (const n of [...near].sort((a, b) => a - b)) {
    if (prev && n - prev > 1) pages.push("…");
    pages.push(n);
    prev = n;
  }

  const btnBase =
    "inline-flex h-8 min-w-[2rem] items-center justify-center rounded px-2 font-mono text-[12px] transition-colors";
  const active = `${btnBase} bg-burgundy text-paper font-semibold`;
  const normal = `${btnBase} text-ink hover:bg-rule-soft`;
  const disabled = `${btnBase} text-muted cursor-not-allowed opacity-40`;

  return (
    <nav
      aria-label="Pagination"
      className="mt-8 flex items-center justify-center gap-1"
    >
      {currentPage > 1 ? (
        <Link href={pageHref(query, currentPage - 1)} className={normal} aria-label="Previous page">
          ←
        </Link>
      ) : (
        <span className={disabled}>←</span>
      )}

      {pages.map((p, i) =>
        p === "…" ? (
          <span key={`ellipsis-${i}`} className="px-1 font-mono text-[12px] text-muted select-none">
            …
          </span>
        ) : (
          <Link
            key={p}
            href={pageHref(query, p)}
            className={p === currentPage ? active : normal}
            aria-current={p === currentPage ? "page" : undefined}
          >
            {p}
          </Link>
        ),
      )}

      {currentPage < totalPages ? (
        <Link href={pageHref(query, currentPage + 1)} className={normal} aria-label="Next page">
          →
        </Link>
      ) : (
        <span className={disabled}>→</span>
      )}
    </nav>
  );
}
