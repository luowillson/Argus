"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { fetchPaperClient, fetchPaperStatus, PaperDetailDTO } from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { upsertLocalPaper } from "@/lib/localPapers";
import { PaperView } from "./PaperView";

type Phase = "ingesting" | "analyzing" | "loading";

const PHASE_LABELS: Record<Phase, string> = {
  ingesting: "Fetching reviews from OpenReview…",
  analyzing: "Generating AI insights…",
  loading: "Loading paper…",
};

const POLL_INTERVAL_MS = 5000;
// 90s is enough for an OpenReview fetch + scoring + LLM analyze under normal
// load. If we're still stuck after that, the worker has almost certainly
// failed (id not found on either v1/v2, auth-gated venue, LLM down, etc.).
const POLL_TIMEOUT_MS = 90_000;

export function PaperPending({ paperId }: { paperId: string }) {
  const [dto, setDto] = useState<PaperDetailDTO | null>(null);
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
          const result = await fetchPaperClient(paperId, { refresh: true });
          if (!cancelled && result && result !== "queued" && result !== "failed") {
            toast.success(
              status.analysis === "ready"
                ? "Paper analyzed — AI insights ready"
                : "Paper ingested — score ready",
            );
            upsertLocalPaper(result);
            setDto(result);
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

  if (dto) {
    const paper = adaptPaperDetail(dto);
    return <PaperView paper={paper} aiReady={dto.status === "ready"} />;
  }

  if (failed) {
    return (
      <article className="mx-auto max-w-[1100px] px-24 pt-16 pb-16 text-center">
        <h1 className="font-serif text-[28px] font-medium text-burgundy">
          Couldn&rsquo;t import this paper
        </h1>
        <p className="mt-4 max-w-[640px] mx-auto font-sans text-[14px] leading-[1.6] text-prose">
          We tried to fetch{" "}
          <code className="font-mono text-[12px] text-muted">{paperId}</code>{" "}
          from OpenReview but the ingest job failed. Most
          common causes:
        </p>
        <ul className="mt-3 max-w-[640px] mx-auto space-y-1 text-left font-sans text-[13px] leading-[1.6] text-muted">
          <li>• The forum id doesn&rsquo;t exist on OpenReview.</li>
          <li>• The paper is on a venue that requires login (set OpenReview credentials in <code>api/.env</code>).</li>
          <li>• The Celery worker isn&rsquo;t running or crashed mid-job.</li>
        </ul>
        <p className="mt-6 font-sans text-[12px] text-muted">
          Check the worker terminal for the underlying error.
        </p>
      </article>
    );
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
