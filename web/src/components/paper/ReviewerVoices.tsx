import type { Paper } from "@/lib/types";

export function ReviewerVoices({ paper }: { paper: Paper }) {
  return (
    <section className="mt-9 border-t-[1.5px] border-ink pt-5">
      <div className="mb-4 font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
        What reviewers said · {paper.consensus}
      </div>
      <ul>
        {paper.reviewers.map((rv) => (
          <li
            key={rv.handle}
            className="border-b border-rule-soft py-3.5"
          >
            <div className="flex items-center justify-between font-sans text-[12px] text-muted-2">
              <span>Reviewer {rv.handle}</span>
              <span className="font-semibold text-burgundy">
                {rv.label} · {rv.rating}/10
              </span>
            </div>
            <p className="mt-1.5 font-serif text-[15px] italic leading-[1.6]">
              &ldquo;{rv.quote}&rdquo;
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
