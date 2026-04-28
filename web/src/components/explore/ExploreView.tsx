"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  type ExplorePathwayDTO,
  type ExplorePathwayItemDTO,
  postExplorePath,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  initialTopic: string;
};

const LOADING_STEPS = [
  "Drafting sub-topics…",
  "Searching the paper corpus…",
  "Ranking each topic by Veros score…",
  "Ordering the sequence for learning…",
];

export function ExploreView({ initialTopic }: Props) {
  const router = useRouter();
  const [topic, setTopic] = useState(initialTopic);
  const [submitted, setSubmitted] = useState(initialTopic);
  const [pathway, setPathway] = useState<ExplorePathwayDTO | null>(null);
  const [loading, setLoading] = useState(() => Boolean(initialTopic.trim()));
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    if (!loading) return;
    const id = window.setInterval(() => {
      setStepIndex((i) => (i + 1) % LOADING_STEPS.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, [loading]);

  useEffect(() => {
    const target = submitted.trim();
    if (!target) return;

    const controller = new AbortController();

    postExplorePath(target, false, controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setPathway(data);
        setError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Failed to build learning path");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [requestKey, submitted]);

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = topic.trim();
    if (!next) return;
    const params = new URLSearchParams({ q: next });
    setStepIndex(0);
    setLoading(true);
    setError(null);
    setPathway(null);
    router.push(`/explore?${params.toString()}`);
    setSubmitted(next);
    setRequestKey((value) => value + 1);
  }

  return (
    <div className="mx-auto max-w-[1100px] px-6 py-10 font-serif sm:px-10 lg:px-16">
      <div className="mb-10">
        <h1 className="font-sans text-[28px] font-semibold tracking-tight text-burgundy">
          Explore a topic
        </h1>
        <p className="mt-2 text-[15px] text-prose-soft">
          Enter a concept and Veros will draft sub-topics, search each one in the
          corpus, rank by Veros score, and order the result for learning —
          foundations first, frontier last.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. mixture of experts"
          className="flex-1 border border-rule bg-surface px-4 py-3 font-sans text-[15px] text-ink placeholder:text-muted focus:border-burgundy focus:outline-none"
          autoFocus
        />
        <button
          type="submit"
          disabled={!topic.trim() || loading}
          className="bg-burgundy px-5 py-3 font-sans text-[14px] font-medium text-cream tracking-wide uppercase disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Building…" : "Explore"}
        </button>
      </form>

      <div className="mt-10">
        {loading ? <LoadingState message={LOADING_STEPS[stepIndex]} /> : null}
        {error ? <ErrorState message={error} /> : null}
        {pathway && !loading && !error ? (
          <PathwayResult pathway={pathway} />
        ) : null}
        {!loading && !error && !pathway && !submitted ? (
          <EmptyHint />
        ) : null}
      </div>
    </div>
  );
}

function LoadingState({ message }: { message: string }) {
  return (
    <div className="border border-rule-soft bg-bg-warm px-5 py-6 font-sans text-[14px] text-muted-2">
      <div className="flex items-center gap-3">
        <span className="inline-block size-2 animate-pulse rounded-full bg-burgundy" />
        <span>{message}</span>
      </div>
      <p className="mt-2 text-[12px] text-muted">
        Searching the paper corpus, then ranking matches into a learning sequence.
      </p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="border border-burgundy/30 bg-burgundy/5 px-5 py-4 font-sans text-[14px] text-burgundy">
      {message}
    </div>
  );
}

function EmptyHint() {
  return (
    <p className="font-sans text-[13px] text-muted">
      Try a focused concept like <em>mixture of experts</em>,{" "}
      <em>diffusion models</em>, or <em>contrastive learning</em>.
    </p>
  );
}

function PathwayResult({ pathway }: { pathway: ExplorePathwayDTO }) {
  return (
    <div>
      <header className="border-b border-rule pb-5">
        <h2 className="font-serif text-[22px] leading-snug text-ink">
          {pathway.title}
        </h2>
      </header>

      <ol className="mt-6 space-y-6">
        {pathway.items.map((item, index) => {
          const previousStage = index > 0 ? pathway.items[index - 1].stage : null;
          const newStage = item.stage !== previousStage;
          return (
            <li key={`${item.position}-${item.paper?.id ?? "missing"}`}>
              {newStage ? <StageDivider stage={item.stage} /> : null}
              <ItemCard item={item} />
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StageDivider({ stage }: { stage: string }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <span className="font-sans text-[11px] font-semibold uppercase tracking-[0.12em] text-burgundy">
        {stage}
      </span>
      <span className="h-px flex-1 bg-rule" />
    </div>
  );
}

function ItemCard({ item }: { item: ExplorePathwayItemDTO }) {
  const paper = item.paper;
  return (
    <div className="flex gap-4 border border-border-c bg-surface px-5 py-4">
      <div className="flex size-9 shrink-0 items-center justify-center border border-burgundy/30 bg-burgundy/5 font-sans text-[14px] font-semibold text-burgundy">
        {item.position}
      </div>
      <div className="flex-1">
        {paper ? (
          <Link
            href={`/papers/${encodeURIComponent(paper.id)}`}
            className="block font-serif text-[17px] leading-snug text-ink hover:text-burgundy"
          >
            {paper.title}
          </Link>
        ) : (
          <div className="font-serif text-[17px] text-muted">
            (paper not available)
          </div>
        )}
        {paper ? (
          <div className="mt-1 flex items-center gap-3 font-sans text-[12px] text-muted">
            <span className={cn("text-muted-2", paper.score == null && "italic")}>
              Veros {paper.score != null ? paper.score.toFixed(1) : "—"}
            </span>
            <span>·</span>
            <span className="line-clamp-1">{paper.authors}</span>
            {paper.venue ? (
              <>
                <span>·</span>
                <span className="line-clamp-1">{paper.venue}</span>
              </>
            ) : null}
          </div>
        ) : null}
        <p className="mt-3 font-sans text-[13px] leading-relaxed text-prose-soft">
          {item.read_focus}
        </p>
      </div>
    </div>
  );
}
