import Link from "next/link";
import type { Paper } from "@/lib/types";
import { cn, scoreColor } from "@/lib/utils";
import { VerdictPill } from "@/components/brand/VerdictPill";
import { MetricsCell } from "./MetricsCell";

type Props = {
  paper: Paper;
  isFirst?: boolean;
};

export function ResultRow({ paper, isFirst }: Props) {
  return (
    <Link
      href={`/papers/${paper.id}`}
      className={cn(
        "grid items-start gap-5 border-b border-rule-soft py-5 transition hover:bg-paper/60",
        "grid-cols-[78px_70px_1fr_140px_180px_120px]",
        isFirst && "border-t border-rule",
      )}
    >
      {/* Score */}
      <div>
        <div
          className={cn(
            "text-[30px] font-medium leading-none tracking-[-0.02em] tabular-nums",
            scoreColor(paper.score),
          )}
        >
          {paper.score.toFixed(1)}
        </div>
        <div className="mt-1 font-sans text-[11px] text-muted">out of 10</div>
      </div>

      {/* Grade */}
      <div className="pt-1">
        <div className="font-mono text-[16px] font-semibold text-ink">
          {paper.grade}
        </div>
      </div>

      {/* Paper */}
      <div>
        <div className="text-[17px] font-medium leading-snug text-burgundy">
          {paper.title}
        </div>
        <div className="mt-1 font-sans text-[12px] text-muted-2">
          {paper.authors}
        </div>
        <div className="mt-2 max-w-[680px] font-serif text-[13px] italic leading-[1.55] text-prose">
          {paper.tldr}
        </div>
        <div className="mt-2 font-mono text-[11px] text-muted">
          arxiv:{paper.id} · {paper.citations.toLocaleString()} citations
        </div>
      </div>

      {/* Venue */}
      <div className="pt-1">
        <div className="text-[13px] font-medium text-prose">{paper.venue}</div>
        <div className="mt-1 font-mono text-[10px] text-muted">
          {paper.acceptance ? `accepted (${paper.acceptance})` : "—"}
        </div>
      </div>

      {/* Metrics — numbers only, no bars */}
      <div className="pt-1">
        <MetricsCell
          novelty={paper.novelty}
          technical={paper.technical}
          clarity={paper.clarity}
          impact={paper.impact}
        />
      </div>

      {/* Verdict + consensus */}
      <div className="flex flex-col items-start gap-2.5 pt-1">
        <VerdictPill verdict={paper.verdict} />
        <div className="font-sans text-[11px] text-muted">
          consensus
          <br />
          <span className="text-ink">
            {paper.consensus.split(" · ")[0]} ×{paper.consensus.split(" · ").length}
          </span>
        </div>
      </div>
    </Link>
  );
}
