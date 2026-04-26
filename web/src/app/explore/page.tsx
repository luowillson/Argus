import { TopNav } from "@/components/nav/TopNav";
import { ExploreView } from "@/components/explore/ExploreView";

export default async function ExplorePage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const initialTopic = q.trim();
  return (
    <div className="min-h-screen bg-paper text-ink">
      <TopNav variant="compact" />
      <ExploreView initialTopic={initialTopic} />
    </div>
  );
}
