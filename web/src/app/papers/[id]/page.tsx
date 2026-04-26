import { notFound } from "next/navigation";
import { TopNav } from "@/components/nav/TopNav";
import { PaperView } from "@/components/paper/PaperView";
import { PaperPending } from "@/components/paper/PaperPending";
import { fetchPaper, fetchSaved } from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let result: Awaited<ReturnType<typeof fetchPaper>> = null;
  let initialSaved = false;

  try {
    const [paperResult, savedList] = await Promise.all([
      fetchPaper(id),
      fetchSaved().catch(() => []),
    ]);
    result = paperResult;
    initialSaved = savedList.some((dto) => dto.id === id);
  } catch {
    // API unreachable — fall through to mock data so the page still renders.
  }

  if (result === "queued") {
    return (
      <div className="min-h-screen bg-paper text-ink">
        <TopNav />
        <PaperPending paperId={id} />
      </div>
    );
  }

  if (result) {
    const paper = adaptPaperDetail(result);
    return (
      <div className="min-h-screen bg-paper text-ink">
        <TopNav />
        <PaperView paper={paper} aiReady={result.status === "ready"} initialSaved={initialSaved} />
      </div>
    );
  }

  const mock = VEROS_PAPERS.find((p) => p.id === id) ?? null;
  if (!mock) notFound();

  return (
    <div className="min-h-screen bg-paper text-ink">
      <TopNav />
      <PaperView paper={mock} aiReady={true} initialSaved={false} />
    </div>
  );
}
