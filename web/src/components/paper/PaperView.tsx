import { Paper } from "@/lib/types";
import { PaperHeader } from "./PaperHeader";
import { ScoreBand } from "./ScoreBand";
import { TldrSection } from "./TldrSection";
import { ReadSkimGrid } from "./ReadSkimGrid";
import { ReviewerVoices } from "./ReviewerVoices";
import { CitationGraphSection } from "./CitationGraphSection";

export function PaperView({
  paper,
  aiReady,
  initialSaved = false,
  onEnrichComplete,
}: {
  paper: Paper;
  aiReady: boolean;
  initialSaved?: boolean;
  onEnrichComplete?: () => void;
}) {
  return (
    <article className="mx-auto max-w-[1100px] px-24 pt-9 pb-16">
      <PaperHeader paper={paper} initialSaved={initialSaved} />
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
      <CitationGraphSection
        paperId={paper.id}
        status={paper.citationGraphStatus}
        onEnrichComplete={onEnrichComplete}
      />
    </article>
  );
}
