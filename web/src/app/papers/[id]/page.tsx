import { notFound } from "next/navigation";
import { TopNav } from "@/components/nav/TopNav";
import { PaperHeader } from "@/components/paper/PaperHeader";
import { ScoreBand } from "@/components/paper/ScoreBand";
import { TldrSection } from "@/components/paper/TldrSection";
import { ReadSkimGrid } from "@/components/paper/ReadSkimGrid";
import { ReviewerVoices } from "@/components/paper/ReviewerVoices";
import { fetchPaper } from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let paper = null;
  let aiReady = true;

  try {
    const dto = await fetchPaper(id);
    if (dto) {
      paper = adaptPaperDetail(dto);
      aiReady = dto.status === "ready";
    }
  } catch {
    // API unreachable — fall through to mock data so the page still renders.
  }

  if (!paper) {
    paper = VEROS_PAPERS.find((p) => p.id === id) ?? null;
    if (!paper) notFound();
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <TopNav />

      <article className="mx-auto max-w-[1100px] px-24 pt-9 pb-16">
        <PaperHeader paper={paper} />
        <ScoreBand paper={paper} aiReady={aiReady} />
        <TldrSection tldr={paper.tldr} aiReady={aiReady} />
        {(paper.deep.length > 0 || paper.skim.length > 0) && (
          <ReadSkimGrid deep={paper.deep} skim={paper.skim} />
        )}
        <ReviewerVoices paper={paper} />
      </article>
    </div>
  );
}
