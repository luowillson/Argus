import Link from "next/link";
import { SearchBox } from "./SearchBox";

export function Hero() {
  return (
    <section className="px-6 pt-16 sm:px-10 lg:px-16 xl:max-w-[980px] xl:px-24 xl:pt-30">
      <div className="font-sans text-[11px] font-semibold tracking-[0.22em] uppercase text-burgundy">
        Open peer review, distilled
      </div>
      <h1 className="mt-5 max-w-[880px] text-[50px] leading-[1.02] font-normal tracking-[-0.02em] sm:text-[62px] xl:text-[76px]">
        Read the papers
        <br />
        <em className="font-serif italic text-burgundy">worth reading.</em>
      </h1>
      <p className="mt-6 max-w-[600px] font-serif text-[18px] leading-[1.55] text-prose-soft xl:text-[19px]">
        Veros aggregates every reviewer comment on OpenReview, weights
        consensus, and tells you which sections deserve your hour.
      </p>

      <SearchBox />

      <div className="mt-3.5 font-sans text-[13px] text-muted">
        Try{" "}
        <Link
          href="/papers/F76bwRSLeK"
          className="cursor-pointer text-burgundy underline underline-offset-2"
        >
          openreview:F76bwRSLeK
        </Link>
        ,{" "}
        <Link
          href="/search?q=Diffusion%20Transformers"
          className="cursor-pointer text-burgundy underline underline-offset-2"
        >
          &ldquo;Diffusion Transformers&rdquo;
        </Link>
        , or paste a forum URL.
      </div>
    </section>
  );
}
