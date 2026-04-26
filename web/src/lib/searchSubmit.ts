import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import { getLocalSearchDestination } from "./localPapers";
import { getSearchDestination } from "./query";

/**
 * Shared submit logic for the landing search box and the browse search bar.
 *
 * 1. If the query is an OpenReview forum URL or raw forum id, route directly
 *    to the paper page (existing fast-path).
 * 2. Otherwise classify against the static browser corpus and route to
 *    /search with params describing the result.
 *
 * Returns the destination href that was navigated to (useful for tests).
 */
export async function submitSearch(
  rawQuery: string,
  router: Pick<AppRouterInstance, "push" | "replace">,
  opts: { replace?: boolean } = {},
): Promise<string | null> {
  const trimmed = rawQuery.trim();
  if (!trimmed) return null;

  const dest = getSearchDestination(trimmed);
  if (dest && dest.kind === "paper") {
    (opts.replace ? router.replace : router.push)(dest.href);
    return dest.href;
  }

  const href = await getLocalSearchDestination(trimmed);
  (opts.replace ? router.replace : router.push)(href);
  return href;
}
