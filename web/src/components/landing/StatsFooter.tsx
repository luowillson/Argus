import { readFile } from "node:fs/promises";
import path from "node:path";

type StaticCorpusPaper = {
  reviewers?: unknown[];
};

async function fetchStats(): Promise<{ paper_count: number; review_count: number }> {
  try {
    const filePath = path.join(process.cwd(), "public", "data", "papers.json");
    const raw = await readFile(filePath, "utf-8");
    const parsed = JSON.parse(raw) as {
      paper_count?: number;
      papers?: StaticCorpusPaper[];
    };
    const papers = parsed.papers ?? [];
    return {
      paper_count: parsed.paper_count ?? papers.length,
      review_count: papers.reduce(
        (sum, paper) => sum + (Array.isArray(paper.reviewers) ? paper.reviewers.length : 0),
        0,
      ),
    };
  } catch {
    // Static corpus unavailable — show placeholder.
  }
  return { paper_count: 0, review_count: 0 };
}

export async function StatsFooter() {
  const { paper_count, review_count } = await fetchStats();
  const hasCounts = paper_count > 0;

  return (
    <footer className="absolute bottom-0 left-0 right-0 flex flex-col gap-1.5 border-t border-rule px-6 py-4 font-sans text-[13px] text-muted-2 sm:px-10 lg:flex-row lg:items-center lg:justify-between lg:px-16 xl:px-24">
      <div>
        {hasCounts ? (
          <>
            <Stat>{paper_count.toLocaleString()}</Stat> paper
            {paper_count !== 1 ? "s" : ""} analyzed &nbsp;·&nbsp;{" "}
            <Stat>{review_count.toLocaleString()}</Stat> reviewer comments
            indexed
          </>
        ) : (
          <>Ingest a paper to get started &nbsp;·&nbsp; score updates in real time</>
        )}
      </div>
      <div className="font-mono text-[11px] text-muted">
        Veros · open peer review, distilled
      </div>
    </footer>
  );
}

function Stat({ children }: { children: React.ReactNode }) {
  return (
    <strong className="font-serif text-[16px] font-medium text-ink">
      {children}
    </strong>
  );
}
