import type { AppRouterInstance } from "next/dist/shared/lib/app-router-context.shared-runtime";
import { lookupSearch } from "./api";
import { getSearchDestination } from "./query";

/**
 * Shared submit logic for the landing search box and the browse search bar.
 *
 * 1. If the query is an OpenReview forum URL or raw forum id, route directly
 *    to the paper page (existing fast-path).
 * 2. Otherwise call POST /search/lookup, which classifies intent and may
 *    enqueue an OpenReview ingest. Route to /search with params describing
 *    the result so the search page can render the right state on initial paint.
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

  let href: string;
  try {
    const resp = await lookupSearch(trimmed);
    if (resp.intent === "topic" || !resp.paper_id) {
      const params = new URLSearchParams({ q: trimmed });
      if (resp.intent === "specific" && !resp.paper_id) {
        params.set("notFound", "1");
      }
      href = `/search?${params}`;
    } else {
      const params = new URLSearchParams({ q: trimmed, focus: resp.paper_id });
      if (resp.openreview_found && resp.openreview_candidate?.title) {
        params.set("pending", resp.openreview_candidate.title);
      }
      href = `/search?${params}`;
    }
  } catch {
    href = `/search?q=${encodeURIComponent(trimmed)}`;
  }

  (opts.replace ? router.replace : router.push)(href);
  return href;
}
