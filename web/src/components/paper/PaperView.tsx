import { Paper } from "@/lib/types";
import { PaperHeader } from "./PaperHeader";
import { ScoreBand } from "./ScoreBand";
import { TldrSection } from "./TldrSection";
import { ReadSkimGrid } from "./ReadSkimGrid";
import { ReviewerVoices } from "./ReviewerVoices";

export function PaperView({
  paper,
  aiReady,
}: {
  paper: Paper;
  aiReady: boolean;
}) {
  return (
    <article className="mx-auto max-w-[1100px] px-24 pt-9 pb-16">
      <PaperHeader paper={paper} />
      <ScoreBand paper={paper} />
      <TldrSection
        paperId={paper.id}
        tldr={paper.tldr}
        aiReady={aiReady}
        reviewerCount={paper.reviewerCount}
      />
      {(paper.deep.length > 0 || paper.skim.length > 0) && (
        <ReadSkimGrid deep={paper.deep} skim={paper.skim} />
      )}
      <ReviewerVoices paper={paper} />
    </article>
  );
}
