import Link from "next/link";
import type { Paper } from "@/lib/types";
import { SaveButton } from "./SaveButton";

function openreviewUrl(id: string) {
  return `https://openreview.net/forum?id=${encodeURIComponent(id)}`;
}

export function PaperHeader({
  paper,
  initialSaved = false,
}: {
  paper: Paper;
  initialSaved?: boolean;
}) {
  return (
    <header>
      <div className="flex items-center justify-between font-sans text-[12px] text-muted">
        <div>
          <Link href="/search" className="text-burgundy">
            ← Back to results
          </Link>
          <span className="px-2">·</span>
          <a
            href={openreviewUrl(paper.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono hover:text-ink"
          >
            openreview:{paper.id}
          </a>
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
        {paper.venue} · {paper.citations.toLocaleString()} citations
        {paper.acceptance ? ` · accepted (${paper.acceptance})` : ""}
      </div>
    </header>
  );
}
