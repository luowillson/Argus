import { redirect } from "next/navigation";

export default async function AuthorRankingSearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const query = (await searchParams).q?.trim() ?? "";
  redirect(query ? `/ranking?author=${encodeURIComponent(query)}` : "/ranking");
}
