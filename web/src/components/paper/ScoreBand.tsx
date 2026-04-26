import type { Paper } from "@/lib/types";
import { cn, scoreColor } from "@/lib/utils";
import { VerdictPill } from "@/components/brand/VerdictPill";
import { DimensionTiles } from "./DimensionTiles";
import { MethodologyDialog } from "./MethodologyDialog";

const STRENGTH_COLOR = {
  strong: "text-accept",
  moderate: "text-borderline",
  mixed: "text-borderline",
  split: "text-burgundy",
} as const;

type Props = {
  paper: Paper;
};

export function ScoreBand({ paper }: Props) {
  const score = paper.score;

  return (
    <section className="mt-7 grid grid-cols-[180px_1fr_200px] items-center gap-8 border-y border-y-rule border-t-[1.5px] border-t-ink py-6">
      <div>
        <div className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
          Veros Score
        </div>
        <div className="mt-1 flex items-baseline gap-1.5">
          <span
            className={cn(
              "text-[64px] font-medium leading-none tracking-[-0.04em] tabular-nums",
              scoreColor(paper.score),
            )}
          >
            {score !== null ? score.toFixed(1) : "—"}
          </span>
          <span className="font-sans text-[18px] font-normal text-muted">
            / 10
          </span>
        </div>
        <div className="mt-1.5 font-sans text-[13px] text-muted-2">
          {score === null && "score pending"}
        </div>
        <MethodologyDialog />
      </div>

      <DimensionTiles
        novelty={paper.novelty}
        technical={paper.technical}
        clarity={paper.clarity}
        impact={paper.impact}
      />

      <div className="flex flex-col items-end gap-2.5 text-right">
        <VerdictPill verdict={paper.verdict} />
        <div className="font-sans text-[12px] text-muted-2">
          {paper.reviewerCount} reviewers · consensus{" "}
          <strong className={cn("font-semibold", STRENGTH_COLOR[paper.consensusStrength])}>
            {paper.consensusStrength}
          </strong>
        </div>
      </div>
    </section>
  );
}
