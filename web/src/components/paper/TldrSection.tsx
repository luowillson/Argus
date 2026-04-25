"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { analyzePaper, fetchPaper } from "@/lib/api";

type Props = {
  paperId: string;
  tldr: string;
  aiReady?: boolean;
};

export function TldrSection({ paperId, tldr, aiReady = true }: Props) {
  const router = useRouter();
  const [summary, setSummary] = useState(tldr);
  const [status, setStatus] = useState<"idle" | "generating" | "error">(
    aiReady ? "idle" : "generating",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (aiReady) return;

    let cancelled = false;

    async function generateSummary() {
      try {
        await analyzePaper(paperId);
        const result = await fetchPaper(paperId);
        if (cancelled || !result || result === "queued") return;

        if (result.tldr) {
          setSummary(result.tldr);
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
  }, [aiReady, paperId, router]);

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
        {summary}
      </p>
      {status === "error" && error && (
        <p className="mt-3 max-w-[820px] font-sans text-[12px] leading-[1.6] text-muted">
          {error}
        </p>
      )}
    </section>
  );
}
