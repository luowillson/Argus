import { TopNav } from "@/components/nav/TopNav";
import { ResultsGrid } from "@/components/search/ResultsGrid";
import { VEROS_PAPERS } from "@/lib/mock-papers";

export default function SavedPage() {
  // M1 stub: hardcoded subset. M8 wires this to GET /saved.
  const saved = VEROS_PAPERS.slice(0, 3);

  return (
    <div className="min-h-screen bg-paper">
      <TopNav />

      <div className="px-16 pt-9 pb-1.5">
        <h1 className="text-[26px] font-medium tracking-[-0.011em]">
          Your reading list
        </h1>
        <div className="mt-1.5 font-sans text-[13px] text-muted">
          {saved.length} papers saved
        </div>
      </div>

      <div className="px-16 pb-16">
        <ResultsGrid papers={saved} />
      </div>
    </div>
  );
}
