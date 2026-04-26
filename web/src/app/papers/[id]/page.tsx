import { PaperPageClient } from "@/components/paper/PaperPageClient";

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PaperPageClient paperId={id} />;
}
