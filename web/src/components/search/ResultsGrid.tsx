import type { Paper } from "@/lib/types";
import { ResultRow } from "./ResultRow";

type Props = { papers: Paper[] };

export function ResultsGrid({ papers }: Props) {
  if (papers.length === 0) {
    return (
      <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
        No papers match this query yet. Try a different keyword or paste a forum URL.
      </div>
    );
  }

  return (
    <div>
      {/* Column header */}
      <div className="grid grid-cols-[92px_minmax(0,1.55fr)_150px_220px] gap-5 border-b border-rule pb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
        <span>Score</span>
        <span>Paper</span>
        <span>Venue</span>
        <span>Metrics</span>
      </div>

      {papers.map((p, i) => (
        <ResultRow key={p.id} paper={p} isFirst={i === 0} />
      ))}
    </div>
  );
}
