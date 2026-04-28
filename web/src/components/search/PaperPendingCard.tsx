"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchPaper, fetchPaperStatus } from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { cn } from "@/lib/utils";
import type { Paper } from "@/lib/types";
import { ResultRow } from "./ResultRow";

type Props = {
  paperId: string;
  title: string;
  isFirst?: boolean;
};

type Phase = "ingesting" | "analyzing" | "loading";

const PHASE_LABEL: Record<Phase, string> = {
  ingesting: "Fetching reviews from OpenReview…",
  analyzing: "Generating AI insights…",
  loading: "Loading paper…",
};

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 90_000;

export function PaperPendingCard({ paperId, title, isFirst }: Props) {
  const router = useRouter();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [phase, setPhase] = useState<Phase>("ingesting");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const startedAt = Date.now();

    async function poll() {
      if (cancelled) return;
      try {
        const status = await fetchPaperStatus(paperId);
        if (status.ingest === "failed") {
          if (!cancelled) setFailed(true);
          return;
        }
        if (status.ingest === "ready" && status.analysis === "pending") {
          setPhase("analyzing");
        }
        if (status.analysis === "ready" || status.ingest === "ready") {
          setPhase("loading");
          const result = await fetchPaper(paperId);
          if (!cancelled && result.kind === "ready") {
            setPaper(adaptPaperDetail(result.paper));
            return;
          }
        }
      } catch {
        // swallow transient poll errors; try again next tick
      }
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        if (!cancelled) setFailed(true);
        return;
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS);
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [paperId]);

  if (paper) {
    return <ResultRow paper={paper} isFirst={isFirst} />;
  }

  if (failed) {
    return (
      <div
        className={cn(
          "grid items-start gap-5 border-b border-rule-soft py-5",
          "grid-cols-[92px_minmax(0,1.55fr)_150px_220px]",
          isFirst && "border-t border-rule",
        )}
      >
        <div>
          <div className="mt-0.5 font-mono text-[18px] tabular-nums text-muted">—</div>
        </div>
        <div>
          <div className="text-[18px] font-medium leading-snug text-burgundy">
            {title}
          </div>
          <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.12em] text-burgundy">
            Import failed
          </div>
          <div className="mt-2 max-w-[680px] font-sans text-[13px] leading-[1.55] text-muted">
            We couldn&rsquo;t fetch{" "}
            <code className="font-mono text-[11px]">{paperId}</code> from
            OpenReview. The forum id may not exist, the venue may require
            login, or the worker may have crashed. Check the Celery worker
            terminal.
          </div>
        </div>
        <div />
        <div />
      </div>
    );
  }

  const dest = `/papers/${paperId}`;
  return (
    <div
      role="link"
      tabIndex={0}
      onClick={() => router.push(dest)}
      onKeyDown={(e) => e.key === "Enter" && router.push(dest)}
      className={cn(
        "grid cursor-pointer items-start gap-5 border-b border-rule-soft py-5 transition hover:bg-cream/40",
        "grid-cols-[92px_minmax(0,1.55fr)_150px_220px]",
        isFirst && "border-t border-rule",
      )}
    >
      <div>
        <div className="mt-0.5 flex items-baseline gap-1.5">
          <div className="h-8 w-12 animate-pulse rounded bg-rule-soft" />
          <div className="font-sans text-[13px] text-muted">/ 10</div>
        </div>
      </div>

      <div>
        <div className="text-[18px] font-medium leading-snug text-burgundy">
          {title}
        </div>
        <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
          Just imported · {PHASE_LABEL[phase]}
        </div>
        <div className="mt-2 space-y-1.5">
          <div className="h-3 w-full animate-pulse rounded bg-rule-soft" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-rule-soft" />
        </div>
      </div>

      <div className="pt-1">
        <div className="h-4 w-24 animate-pulse rounded bg-rule-soft" />
      </div>

      <div className="pt-1 space-y-1.5">
        <div className="h-3 w-32 animate-pulse rounded bg-rule-soft" />
        <div className="h-3 w-28 animate-pulse rounded bg-rule-soft" />
        <div className="h-3 w-32 animate-pulse rounded bg-rule-soft" />
        <div className="h-3 w-24 animate-pulse rounded bg-rule-soft" />
      </div>
    </div>
  );
}
