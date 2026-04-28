"use client";

import { useEffect, useState } from "react";
import { TopNav } from "@/components/nav/TopNav";
import { PaperPending } from "@/components/paper/PaperPending";
import { PaperToaster } from "@/components/paper/PaperToaster";
import { PaperView } from "@/components/paper/PaperView";
import { adaptPaperDetail } from "@/lib/adapt";
import { fetchPaper, fetchSavedStatus, type PaperDetailDTO } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "pending" }
  | { kind: "ready"; paper: PaperDetailDTO; saved: boolean }
  | { kind: "not-found" }
  | { kind: "error"; message: string };

export function PaperPageClient({ paperId }: { paperId: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    async function loadPaper() {
      try {
        const [paperResult, isSaved] = await Promise.all([
          fetchPaper(paperId, { signal: controller.signal }),
          fetchSavedStatus(paperId, { signal: controller.signal }).catch(() => false),
        ]);

        if (controller.signal.aborted) return;

        switch (paperResult.kind) {
          case "ready":
            setState({ kind: "ready", paper: paperResult.paper, saved: isSaved });
            return;
          case "queued":
            setState({ kind: "pending" });
            return;
          case "failed":
            setState({ kind: "pending" });
            return;
          case "not_found":
            setState({ kind: "not-found" });
            return;
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "Unable to load paper",
        });
      }
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
      {state.kind === "error" && (
        <article className="mx-auto max-w-[760px] px-24 pt-16 pb-16 text-center">
          <h1 className="font-serif text-[28px] font-medium text-burgundy">
            Couldn&rsquo;t load this paper
          </h1>
          <p className="mt-4 font-sans text-[14px] leading-[1.6] text-muted">
            {state.message}
          </p>
        </article>
      )}
      <PaperToaster />
    </div>
  );
}
