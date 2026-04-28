"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LatexText } from "@/components/ui/LatexText";
import { analyzePaper, fetchPaper } from "@/lib/api";

type Props = {
  paperId: string;
  tldr: string;
  aiReady?: boolean;
  reviewerCount?: number;
};

const MIN_REVIEWS_FOR_INSIGHT = 2;

export function TldrSection({
  paperId,
  tldr,
  aiReady = true,
  reviewerCount = 0,
}: Props) {
  const router = useRouter();
  const insightImpossible =
    !aiReady && reviewerCount < MIN_REVIEWS_FOR_INSIGHT;

  const [summary, setSummary] = useState(tldr);
  const [status, setStatus] = useState<"idle" | "generating" | "error">(() => {
    if (aiReady) return "idle";
    if (insightImpossible) return "error";
    return "generating";
  });
  const [error, setError] = useState<string | null>(
    insightImpossible
      ? `AI summary unavailable — this paper has ${reviewerCount} review${reviewerCount === 1 ? "" : "s"} on OpenReview (need at least ${MIN_REVIEWS_FOR_INSIGHT}).`
      : null,
  );

  // React strict mode (next dev) re-mounts effects, which would otherwise fire
  // analyze twice. Guard with a ref so we only ever issue one request per mount.
  const startedRef = useRef(false);

  useEffect(() => {
    if (aiReady || insightImpossible) return;
    if (startedRef.current) return;
    startedRef.current = true;

    let cancelled = false;

    async function generateSummary() {
      try {
        await analyzePaper(paperId);
        const result = await fetchPaper(paperId);
        if (cancelled || result.kind !== "ready") return;

        if (result.paper.tldr) {
          setSummary(result.paper.tldr);
          setStatus("idle");
          setError(null);
          router.refresh();
          return;
        }

        setStatus("error");
        setError("Summary generation finished, but no summary text was returned.");
      } catch (err) {
        if (cancelled) return;
        setStatus("error");
        setError(err instanceof Error ? err.message : "Unable to generate summary.");
      }
    }

    generateSummary();
    return () => {
      cancelled = true;
    };
  }, [aiReady, insightImpossible, paperId, router]);

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between">
        <div className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
          AI-distilled summary
        </div>
        {status === "generating" && (
          <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-borderline">
            generating summary
          </div>
        )}
        {status === "error" && (
          <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
            summary unavailable
          </div>
        )}
      </div>
      <p className="mt-2 max-w-[820px] font-serif text-[19px] leading-[1.6]">
        <LatexText>{summary}</LatexText>
      </p>
      {status === "error" && error && (
        <p className="mt-3 max-w-[820px] font-sans text-[12px] leading-[1.6] text-muted">
          {error}
        </p>
      )}
    </section>
  );
}
