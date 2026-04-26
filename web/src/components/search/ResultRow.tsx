import Link from "next/link";
import type { Paper } from "@/lib/types";
import { cn, scoreColor } from "@/lib/utils";
import { MetricsCell } from "./MetricsCell";

type Props = {
  paper: Paper;
  isFirst?: boolean;
};

export function ResultRow({ paper, isFirst }: Props) {
  const dest = `/papers/${paper.id}`;
  const score = paper.score;

  return (
    <div
      className={cn(
        "group relative grid cursor-pointer items-start gap-5 border-b border-rule-soft py-5 transition hover:bg-cream/40",
        "grid-cols-[92px_minmax(0,1.55fr)_150px_220px]",
        isFirst && "border-t border-rule",
      )}
    >
      <Link
        href={dest}
        aria-label={`Open ${paper.title}`}
        className="absolute inset-0 z-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-burgundy"
      />
      {/* Score */}
      <div className="pointer-events-none relative z-10">
        <div className="mt-0.5 flex items-baseline gap-1.5">
          <div
            className={cn(
              "text-[32px] font-medium leading-none tracking-[-0.02em] tabular-nums",
              scoreColor(paper.score),
            )}
          >
            {score !== null ? score.toFixed(1) : "—"}
          </div>
          <div className="font-sans text-[13px] text-muted">/ 10</div>
        </div>
      </div>

      {/* Paper */}
      <div className="pointer-events-none relative z-10">
        <div className="text-[18px] font-medium leading-snug text-burgundy">
          {paper.title}
        </div>
        <div className="mt-1 font-sans text-[12px] text-muted-2">
          {paper.authors}
        </div>
        <div className="mt-2 max-w-[680px] font-serif text-[13px] italic leading-[1.55] text-prose">
          {paper.tldr}
        </div>
        <div className="mt-2 font-mono text-[11px] text-muted">
          <a
            href={`https://openreview.net/forum?id=${encodeURIComponent(paper.id)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="pointer-events-auto relative z-20 cursor-pointer hover:text-burgundy"
          >
            openreview:{paper.id}
          </a>
          {paper.citations > 0 && (
            <> · {paper.citations.toLocaleString()} citations</>
          )}
        </div>
      </div>

      {/* Venue */}
      <div className="pointer-events-none relative z-10 pt-1">
        <div className="text-[14px] font-medium text-prose">{paper.venue}</div>
      </div>

      {/* Metrics — numbers only, no bars */}
      <div className="pointer-events-none relative z-10 pt-1">
        <MetricsCell
          novelty={paper.novelty}
          technical={paper.technical}
          clarity={paper.clarity}
          impact={paper.impact}
        />
      </div>
    </div>
  );
}
