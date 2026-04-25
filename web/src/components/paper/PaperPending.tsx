"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { fetchPaper, fetchPaperStatus, PaperDetailDTO } from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { PaperView } from "./PaperView";

type Phase = "ingesting" | "analyzing" | "loading";

const PHASE_LABELS: Record<Phase, string> = {
  ingesting: "Fetching reviews from OpenReview…",
  analyzing: "Generating AI insights…",
  loading: "Loading paper…",
};

export function PaperPending({ paperId }: { paperId: string }) {
  const [dto, setDto] = useState<PaperDetailDTO | null>(null);
  const [phase, setPhase] = useState<Phase>("ingesting");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      if (cancelled) return;
      try {
        const status = await fetchPaperStatus(paperId);

        if (status.ingest === "ready" && status.analysis === "pending") {
          setPhase("analyzing");
        }

        if (status.analysis === "ready" || status.ingest === "ready") {
          setPhase("loading");
          const result = await fetchPaper(paperId);
          if (!cancelled && result && result !== "queued") {
            toast.success(
              status.analysis === "ready"
                ? "Paper analyzed — AI insights ready"
                : "Paper ingested — score ready",
            );
            setDto(result);
            return;
          }
        }
      } catch {
        // swallow transient poll errors; try again next tick
      }

      timer = setTimeout(poll, 2000);
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [paperId]);

  if (dto) {
    const paper = adaptPaperDetail(dto);
    return <PaperView paper={paper} aiReady={dto.status === "ready"} />;
  }

  return (
    <article className="mx-auto max-w-[1100px] px-24 pt-9 pb-16">
      <div className="animate-pulse space-y-6">
        <div className="space-y-3">
          <div className="h-8 rounded bg-rule-soft w-3/4" />
          <div className="h-5 rounded bg-rule-soft w-1/2" />
          <div className="h-4 rounded bg-rule-soft w-1/3" />
        </div>
        <div className="h-28 rounded bg-rule-soft" />
        <div className="grid grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 rounded bg-rule-soft" />
          ))}
        </div>
        <div className="space-y-2">
          <div className="h-4 rounded bg-rule-soft w-full" />
          <div className="h-4 rounded bg-rule-soft w-5/6" />
          <div className="h-4 rounded bg-rule-soft w-4/6" />
        </div>
      </div>

      <p className="mt-10 text-center font-sans text-sm text-muted">
        {PHASE_LABELS[phase]}
      </p>
    </article>
  );
}
