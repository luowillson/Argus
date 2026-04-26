import { API_BASE_URL } from "@/lib/api";

const STATS_TIMEOUT_MS = 1200;

async function fetchStats(): Promise<{ paper_count: number; review_count: number }> {
  try {
    const res = await fetch(`${API_BASE_URL}/stats`, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(STATS_TIMEOUT_MS),
    });
    if (res.ok) return res.json();
  } catch {
    // API unreachable — show placeholder
  }
  return { paper_count: 0, review_count: 0 };
}

export async function StatsFooter() {
  const { paper_count, review_count } = await fetchStats();
  const hasCounts = paper_count > 0;

  return (
    <footer className="absolute bottom-0 left-0 right-0 flex items-center justify-between border-t border-rule px-24 py-5 font-sans text-[13px] text-muted-2">
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
