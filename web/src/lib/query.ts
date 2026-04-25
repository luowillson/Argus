type SearchDestination =
  | { kind: "paper"; href: string }
  | { kind: "search"; href: string };

const OPENREVIEW_ID_RE = /^[A-Za-z0-9_-]{6,64}$/;

function extractOpenReviewForumId(query: string): string | null {
  const candidates = [query, `https://${query}`];
  for (const candidate of candidates) {
    try {
      const url = new URL(candidate);
      if (url.hostname.endsWith("openreview.net")) {
        return url.searchParams.get("id");
      }
    } catch {
      // Try the next candidate; users often paste URLs without a scheme.
    }
  }
  return null;
}

function looksLikeOpenReviewId(query: string): boolean {
  return (
    OPENREVIEW_ID_RE.test(query) &&
    /[A-Za-z]/.test(query) &&
    /\d/.test(query) &&
    !query.includes(".")
  );
}

export function getSearchDestination(rawQuery: string): SearchDestination | null {
  const query = rawQuery.trim();
  if (!query) return null;

  const forumId = extractOpenReviewForumId(query);
  if (forumId) {
    return { kind: "paper", href: `/papers/${encodeURIComponent(forumId)}` };
  }

  if (looksLikeOpenReviewId(query)) {
    return { kind: "paper", href: `/papers/${encodeURIComponent(query)}` };
  }

  return { kind: "search", href: `/search?q=${encodeURIComponent(query)}` };
}
