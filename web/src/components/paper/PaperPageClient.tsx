"use client";

import { useEffect, useState } from "react";
import { TopNav } from "@/components/nav/TopNav";
import { PaperPending } from "@/components/paper/PaperPending";
import { PaperToaster } from "@/components/paper/PaperToaster";
import { PaperView } from "@/components/paper/PaperView";
import { adaptPaperDetail } from "@/lib/adapt";
import { fetchPaperClient, fetchSavedStatusClient, type PaperDetailDTO } from "@/lib/api";
import { findLocalPaper, upsertLocalPaper } from "@/lib/localPapers";
import { VEROS_PAPERS } from "@/lib/mock-papers";

type LoadState =
  | { kind: "loading" }
  | { kind: "pending" }
  | { kind: "ready"; paper: PaperDetailDTO; saved: boolean }
  | { kind: "not-found" };

export function PaperPageClient({ paperId }: { paperId: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    async function loadPaper() {
      try {
        const localPaper = await findLocalPaper(paperId);
        const isSaved = await fetchSavedStatusClient(paperId);
        if (controller.signal.aborted) return;

        if (localPaper) {
          setState({ kind: "ready", paper: localPaper, saved: isSaved });
          return;
        }

        const [paperResult, fallbackSaved] = await Promise.all([
          fetchPaperClient(paperId, { signal: controller.signal }),
          fetchSavedStatusClient(paperId),
        ]);

        if (controller.signal.aborted) return;

        if (paperResult === "queued" || paperResult === "failed") {
          setState({ kind: "pending" });
          return;
        }

        if (paperResult) {
          upsertLocalPaper(paperResult);
          setState({ kind: "ready", paper: paperResult, saved: fallbackSaved });
          return;
        }
      } catch {
        // Fall through to bundled demo data below.
      }

      const mock = VEROS_PAPERS.find((p) => p.id === paperId);
      if (mock) {
        setState({
          kind: "ready",
          paper: {
            id: mock.id,
            title: mock.title,
            authors: mock.authors,
            venue: mock.venue,
            citations: mock.citations,
            openreview_url: `https://openreview.net/forum?id=${encodeURIComponent(mock.id)}`,
            acceptance: mock.acceptance ?? null,
            score: mock.score,
            grade: mock.grade,
            verdict: mock.verdict,
            consensus_strength: mock.consensusStrength,
            reviewer_count: mock.reviewerCount,
            novelty: mock.novelty,
            technical: mock.technical,
            clarity: mock.clarity,
            impact: mock.impact,
            tldr: mock.tldr,
            deep: mock.deep,
            skim: mock.skim,
            reviewers: mock.reviewers.map((r) => ({
              handle: r.handle,
              rating: r.rating,
              rating_scale_max: r.ratingScaleMax,
              label: r.label,
              quote: r.quote,
            })),
            consensus: mock.consensus,
            score_breakdown: null,
            status: "ready",
          },
          saved: false,
        });
        return;
      }

      setState({ kind: "not-found" });
    }

    loadPaper();
    return () => controller.abort();
  }, [paperId]);

  return (
    <div className="min-h-screen bg-paper text-ink">
      <TopNav />
      {state.kind === "loading" && (
        <article className="mx-auto max-w-[1100px] px-24 pt-9 pb-16">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-3/4 rounded bg-rule-soft" />
            <div className="h-5 w-1/2 rounded bg-rule-soft" />
            <div className="h-28 rounded bg-rule-soft" />
          </div>
        </article>
      )}
      {state.kind === "pending" && <PaperPending paperId={paperId} />}
      {state.kind === "ready" && (
        <PaperView
          paper={adaptPaperDetail(state.paper)}
          aiReady={state.paper.status === "ready"}
          initialSaved={state.saved}
        />
      )}
      {state.kind === "not-found" && (
        <article className="mx-auto max-w-[760px] px-24 pt-16 pb-16 text-center">
          <h1 className="font-serif text-[28px] font-medium text-burgundy">
            Paper not found
          </h1>
          <p className="mt-4 font-sans text-[14px] leading-[1.6] text-muted">
            We could not find an ingested paper for{" "}
            <code className="font-mono text-[12px]">{paperId}</code>.
          </p>
        </article>
      )}
      <PaperToaster />
    </div>
  );
}
