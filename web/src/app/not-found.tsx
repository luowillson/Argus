import Link from "next/link";
import { TopNav } from "@/components/nav/TopNav";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      <TopNav />
      <div className="flex flex-col items-center justify-center px-6 pt-32 text-center">
        <div className="font-mono text-[64px] font-medium leading-none text-rule">
          404
        </div>
        <h1 className="mt-4 text-[28px] font-medium tracking-[-0.01em]">
          Paper not found
        </h1>
        <p className="mt-3 max-w-[380px] font-sans text-[14px] leading-relaxed text-muted-2">
          This forum ID isn&apos;t in our index yet. You can paste the
          OpenReview URL directly into the search box to trigger ingestion.
        </p>
        <Link
          href="/search"
          className="mt-8 border border-ink px-6 py-2.5 font-sans text-[13px] font-medium hover:bg-ink hover:text-paper transition"
        >
          Go to search
        </Link>
      </div>
    </div>
  );
}
