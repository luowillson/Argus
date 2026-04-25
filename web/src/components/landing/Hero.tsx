import Link from "next/link";
import { SearchBox } from "./SearchBox";

export function Hero() {
  return (
    <section className="px-24 pt-30 max-w-[980px]">
      <div className="font-sans text-[11px] font-semibold tracking-[0.22em] uppercase text-burgundy">
        Open peer review, distilled
      </div>
      <h1 className="mt-5 max-w-[880px] text-[76px] leading-[1.02] font-normal tracking-[-0.02em]">
        Read the papers{" "}
        <em className="font-serif italic text-burgundy">worth reading.</em>
      </h1>
      <p className="mt-6 max-w-[600px] font-serif text-[19px] leading-[1.55] text-prose-soft">
        Veros aggregates every reviewer comment on OpenReview, weights
        consensus, and tells you which sections deserve your hour.
      </p>

      <SearchBox />

      <div className="mt-3.5 font-sans text-[13px] text-muted">
        Try{" "}
        <Link
          href="/papers/2402.09876"
          className="text-burgundy underline underline-offset-2"
        >
          arXiv:2402.09876
        </Link>
        ,{" "}
        <Link
          href="/search?q=Sparse%20Autoencoders"
          className="text-burgundy underline underline-offset-2"
        >
          &ldquo;Sparse Autoencoders&rdquo;
        </Link>
        , or paste a forum URL.
      </div>
    </section>
  );
}
