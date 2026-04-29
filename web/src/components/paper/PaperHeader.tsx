import Link from "next/link";
import type { Paper } from "@/lib/types";
import { SaveButton } from "./SaveButton";

export function PaperHeader({
  paper,
  initialSaved = false,
}: {
  paper: Paper;
  initialSaved?: boolean;
}) {
  const metadata = [
    paper.venue,
    paper.acceptance ? `accepted (${paper.acceptance})` : null,
    `${paper.citations.toLocaleString()} citations`,
    paper.referencesCount !== null ? `${paper.referencesCount.toLocaleString()} references` : null,
  ].filter(Boolean);
  const openreviewUrl =
    paper.openreviewUrl ?? `https://openreview.net/forum?id=${encodeURIComponent(paper.id)}`;

  return (
    <header>
      <div className="flex items-center justify-between font-sans text-[12px] text-muted">
        <div>
          <Link href="/search" className="text-burgundy">
            ← Back to results
          </Link>
          <span className="px-2">·</span>
          {paper.openreviewUrl ? (
            <a
              href={openreviewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono hover:text-ink"
            >
              openreview:{paper.id}
            </a>
          ) : (
            <span className="font-mono">graph:{paper.id}</span>
          )}
        </div>
        <SaveButton paperId={paper.id} initialSaved={initialSaved} />
      </div>

      <h1 className="mt-5 max-w-[880px] text-[38px] font-medium leading-[1.15] tracking-[-0.013em]">
        {paper.title}
      </h1>
      <div className="mt-2.5 font-serif text-[14px] italic text-prose">
        {paper.authors}
      </div>
      <div className="mt-1.5 font-mono text-[12px] text-muted">
        {metadata.join(" · ")}
      </div>
    </header>
  );
}
