import { TopNav } from "@/components/nav/TopNav";
import { AuthorRankingView } from "@/components/ranking/AuthorRankingView";

export default async function RankingPage({
  searchParams,
}: {
  searchParams: Promise<{ author?: string }>;
}) {
  const query = (await searchParams).author?.trim() ?? "";

  return (
    <div className="min-h-screen bg-paper text-ink">
      <TopNav />
      <main className="mx-auto max-w-[1100px] px-6 py-10 sm:px-10 lg:px-16">
        <AuthorRankingView
          initialRankings={[]}
          initialMode={query ? "search" : "best"}
          initialQuery={query}
        />
      </main>
    </div>
  );
}
