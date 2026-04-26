import { z } from "zod";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const VerdictSchema = z.enum([
  "Strong Accept",
  "Accept",
  "Weak Accept",
  "Borderline",
  "Reject",
  "Insufficient reviews",
]);

const ConsensusStrengthSchema = z.enum([
  "strong",
  "moderate",
  "mixed",
  "split",
]);

export const PaperDetailSchema = z.object({
  id: z.string(),
  title: z.string(),
  authors: z.string(),
  venue: z.string().nullable(),
  citations: z.number().nullable(),
  openreview_url: z.string(),
  acceptance: z.string().nullable(),

  score: z.number().nullable(),
  grade: z.string(),
  verdict: VerdictSchema,
  consensus_strength: ConsensusStrengthSchema,
  reviewer_count: z.number(),

  novelty: z.number().nullable(),
  technical: z.number().nullable(),
  clarity: z.number().nullable(),
  impact: z.number().nullable(),

  tldr: z.string().nullable(),
  deep: z.array(z.string()),
  skim: z.array(z.string()),
  reviewers: z.array(
    z.object({
      handle: z.string(),
      rating: z.number(),
      rating_scale_max: z.number().nullable().optional(),
      label: VerdictSchema,
      quote: z.string(),
    }),
  ),
  consensus: z.string().nullable(),

  score_breakdown: z.record(z.string(), z.unknown()).nullable(),
  status: z.enum(["ready", "score_only", "ingested_no_score", "not_found"]),
});

export type PaperDetailDTO = z.infer<typeof PaperDetailSchema>;

export const PaperStatusSchema = z.object({
  paper_id: z.string(),
  ingest: z.enum(["queued", "ready", "failed"]),
  analysis: z.enum(["pending", "ready", "failed"]),
});

export type PaperStatusDTO = z.infer<typeof PaperStatusSchema>;

/** Returns the full paper detail, a transient/permanent ingest state, or null on 404. */
export async function fetchPaper(
  paperId: string,
  init?: RequestInit,
): Promise<PaperDetailDTO | "queued" | "failed" | null> {
  const res = await fetch(`${API_BASE_URL}/papers/${paperId}`, {
    cache: "no-store",
    ...init,
  });
  if (res.status === 404) return null;
  if (res.status === 410) return "failed";
  if (res.status === 202) return "queued";
  if (!res.ok) {
    throw new Error(`API error ${res.status} fetching ${paperId}`);
  }
  return PaperDetailSchema.parse(await res.json());
}

export async function fetchPaperStatus(
  paperId: string,
): Promise<PaperStatusDTO> {
  const res = await fetch(`${API_BASE_URL}/papers/${paperId}/status`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status} fetching status for ${paperId}`);
  }
  return PaperStatusSchema.parse(await res.json());
}

export async function analyzePaper(paperId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/papers/${encodeURIComponent(paperId)}/analyze`, {
    method: "POST",
  });
  if (res.ok) return;

  let detail = `AI summary failed ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string" && body.detail.trim()) {
      detail = body.detail;
    }
  } catch {
    // Ignore non-JSON error bodies and keep the generic fallback.
  }
  throw new Error(detail);
}

export const PaperOutSchema = z.object({
  id: z.string(),
  title: z.string(),
  authors: z.string(),
  venue: z.string().nullable(),
  acceptance: z.string().nullable(),
  score: z.number().nullable(),
  grade: z.string(),
  verdict: VerdictSchema,
  novelty: z.number().nullable(),
  technical: z.number().nullable(),
  clarity: z.number().nullable(),
  impact: z.number().nullable(),
  tldr: z.string().nullable(),
  consensus: z.string().nullable(),
  consensus_strength: ConsensusStrengthSchema,
  reviewer_count: z.number(),
});

export type PaperOutDTO = z.infer<typeof PaperOutSchema>;
export type SearchSortKey = "score" | "novelty" | "technical" | "clarity" | "impact";

export async function fetchSearch(
  query: string,
  limit = 20,
  offset = 0,
  mode: "auto" | "topic" | "specific" = "auto",
  sort: SearchSortKey = "score",
): Promise<PaperOutDTO[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset),
    mode,
    sort,
  });
  const res = await fetch(`${API_BASE_URL}/search?${params}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Search API error ${res.status}`);
  }
  return z.array(PaperOutSchema).parse(await res.json());
}

/** Live (debounced) topic-mode fuzzy search; pass an AbortSignal to cancel in-flight calls. */
export async function fetchSearchLive(
  query: string,
  sort: SearchSortKey = "score",
  signal?: AbortSignal,
): Promise<PaperOutDTO[]> {
  const params = new URLSearchParams({ q: query, mode: "topic", sort });
  const res = await fetch(`${API_BASE_URL}/search?${params}`, {
    cache: "no-store",
    signal,
  });
  if (!res.ok) {
    throw new Error(`Search API error ${res.status}`);
  }
  return z.array(PaperOutSchema).parse(await res.json());
}

const LookupCandidateSchema = z.object({
  id: z.string(),
  title: z.string(),
  venue: z.string().nullable().optional(),
});

export const SearchLookupResponseSchema = z.object({
  intent: z.enum(["topic", "specific"]),
  top_sim: z.number(),
  paper_id: z.string().nullable(),
  ingest_started: z.boolean(),
  openreview_found: z.boolean(),
  openreview_candidate: LookupCandidateSchema.nullable(),
  results: z.array(PaperOutSchema),
});

export type SearchLookupResponse = z.infer<typeof SearchLookupResponseSchema>;

/** Submit-time classifier: returns intent, optional matched paper id, and a result list. */
export async function lookupSearch(query: string): Promise<SearchLookupResponse> {
  const res = await fetch(`${API_BASE_URL}/search/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: query }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Search lookup API error ${res.status}`);
  }
  return SearchLookupResponseSchema.parse(await res.json());
}

export async function fetchSearchCount(query: string): Promise<number> {
  const params = new URLSearchParams({ q: query });
  const res = await fetch(`${API_BASE_URL}/search/count?${params}`, { cache: "no-store" });
  if (!res.ok) return 0;
  const data = z.object({ total: z.number() }).parse(await res.json());
  return data.total;
}

export async function fetchSaved(init?: RequestInit): Promise<PaperOutDTO[]> {
  const res = await fetch(`${API_BASE_URL}/saved`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`Saved API error ${res.status}`);
  return z.array(PaperOutSchema).parse(await res.json());
}

export async function savePaper(paperId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/saved`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paper_id: paperId }),
  });
  if (!res.ok) throw new Error(`Save failed ${res.status}`);
}

export async function unsavePaper(paperId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/saved/${encodeURIComponent(paperId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Unsave failed ${res.status}`);
}
