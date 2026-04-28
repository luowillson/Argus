import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import { lookupSearch } from "./api";
import { getSearchDestination } from "./query";

/**
 * Shared submit logic for the landing search box and the browse search bar.
 *
 * 1. If the query is an OpenReview forum URL or raw forum id, route directly
 *    to the paper page.
 * 2. Otherwise call /search/lookup which classifies the query, optionally
 *    enqueues an OpenReview ingest, and returns either a focused paper id or
 *    the topic results. We pick the destination from that response.
 *
 * Returns the destination href that was navigated to.
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

  let href = `/search?q=${encodeURIComponent(trimmed)}`;
  try {
    const lookup = await lookupSearch(trimmed);
    if (lookup.intent === "specific" && lookup.paper_id) {
      const params = new URLSearchParams({ q: trimmed, focus: lookup.paper_id });
      if (lookup.openreview_candidate?.title) {
        params.set("pending", lookup.openreview_candidate.title);
      }
      href = `/search?${params}`;
    }
  } catch {
    // Lookup failure shouldn't block navigation — fall through to the topic page.
  }

  (opts.replace ? router.replace : router.push)(href);
  return href;
}
