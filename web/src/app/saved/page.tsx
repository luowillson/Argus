import { TopNav } from "@/components/nav/TopNav";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { fetchSaved } from "@/lib/api";
import { adaptPaperOut } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";
import type { Paper } from "@/lib/types";

export default async function SavedPage() {
  let papers: Paper[] = [];
  let fromApi = false;

  try {
    const dtos = await fetchSaved();
    papers = dtos.map(adaptPaperOut);
    fromApi = true;
  } catch {
    // API unreachable — fall through to mock data.
  }

  if (!fromApi) {
    papers = VEROS_PAPERS.slice(0, 3);
  }

  return (
    <div className="min-h-screen bg-paper">
      <TopNav />

      <div className="px-16 pt-9 pb-1.5">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          Your reading list
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {papers.length} paper{papers.length !== 1 ? "s" : ""} saved
        </div>
      </div>

      <div className="px-16 pb-16">
        {papers.length === 0 && fromApi ? (
          <div className="border-t border-rule px-0 py-16 text-center font-sans text-[13px] text-muted">
            No papers saved yet. Click{" "}
            <span className="font-medium text-ink">Save</span> on any paper to
            add it here.
          </div>
        ) : (
          <ResultsGrid papers={papers} />
        )}
      </div>
    </div>
  );
}
