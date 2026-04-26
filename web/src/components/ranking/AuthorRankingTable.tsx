import Link from "next/link";
import type { AuthorRankingDTO, AuthorRankingOrder } from "@/lib/api";

type Props = {
  rankings: AuthorRankingDTO[];
  order: AuthorRankingOrder;
};

export function AuthorRankingTable({ rankings, order }: Props) {
  const isWorst = order === "worst";

  if (rankings.length === 0) {
    return (
      <div className="py-16 text-center font-sans text-[14px] text-muted">
        No author rankings are available yet.
      </div>
    );
  }

  return (
    <div className="mt-7">
      <div className="grid grid-cols-[72px_minmax(0,1fr)_140px_140px_minmax(0,1.1fr)] gap-5 border-b border-rule pb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
        <span>Rank</span>
        <span>Author</span>
        <span>Avg score</span>
        <span>Papers</span>
        <span>{isWorst ? "Lowest paper" : "Top paper"}</span>
      </div>
      {rankings.map((ranking, index) => {
        const paperId = isWorst ? ranking.lowest_paper_id : ranking.top_paper_id;
        const paperTitle = isWorst ? ranking.lowest_paper_title : ranking.top_paper_title;
        const paperScore = isWorst ? ranking.lowest_score : ranking.top_score;

        return (
          <div
            key={ranking.author}
            className="grid grid-cols-[72px_minmax(0,1fr)_140px_140px_minmax(0,1.1fr)] gap-5 border-b border-rule-soft py-4"
          >
            <div className="font-mono text-[13px] text-muted">#{index + 1}</div>
            <div className="min-w-0">
              <div className="truncate text-[18px] font-medium text-burgundy">
                {ranking.author}
              </div>
            </div>
            <div className="font-mono text-[18px] text-ink">
              {ranking.average_score.toFixed(2)}
            </div>
            <div className="font-sans text-[14px] text-muted-2">
              {ranking.paper_count}
            </div>
            <div className="min-w-0 font-sans text-[13px] leading-snug text-muted-2">
              {paperId && paperTitle ? (
                <Link
                  href={`/papers/${encodeURIComponent(paperId)}`}
                  className="line-clamp-2 cursor-pointer hover:text-burgundy"
                >
                  {paperTitle}
                  {paperScore !== null ? ` (${paperScore.toFixed(1)})` : ""}
                </Link>
              ) : (
                "—"
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
