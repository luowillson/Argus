import { z } from "zod";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const API_READ_TIMEOUT_MS = 3500;
const PAPER_CACHE_TTL_MS = 30 * 60 * 1000;
const SEARCH_CACHE_TTL_MS = 5 * 60 * 1000;
const SAVED_PAPER_IDS_KEY = "veros:saved-paper-ids:v1";

function withReadTimeout(init: RequestInit = {}): RequestInit {
  if (init.signal) return init;
  if (typeof AbortSignal.timeout === "function") {
    return { ...init, signal: AbortSignal.timeout(API_READ_TIMEOUT_MS) };
  }
  const controller = new AbortController();
  setTimeout(() => controller.abort(), API_READ_TIMEOUT_MS);
  return { ...init, signal: controller.signal };
}

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

type CacheEntry<T> = {
  expiresAt: number;
  value: T;
};

function isBrowser() {
  return typeof window !== "undefined";
}

function getSessionValue<T>(key: string, schema: z.ZodType<T>): T | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed = z.object({ expiresAt: z.number(), value: schema }).parse(JSON.parse(raw));
    if (parsed.expiresAt <= Date.now()) {
      window.sessionStorage.removeItem(key);
      return null;
    }
    return parsed.value;
  } catch {
    return null;
  }
}

function setSessionValue<T>(key: string, value: T, ttlMs: number) {
  if (!isBrowser()) return;
  const entry: CacheEntry<T> = { expiresAt: Date.now() + ttlMs, value };
  try {
    window.sessionStorage.setItem(key, JSON.stringify(entry));
  } catch {
    // Ignore quota/security errors; caching is only an optimization.
  }
}

function paperCacheKey(paperId: string) {
  return `veros:paper:${encodeURIComponent(paperId)}:v1`;
}

function searchCacheKey(
  query: string,
  limit: number,
  offset: number,
  mode: "auto" | "topic" | "specific",
  sort: SearchSortKey,
) {
  return `veros:search:${encodeURIComponent(JSON.stringify({ query, limit, offset, mode, sort }))}:v1`;
}

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
  const res = await fetch(`${API_BASE_URL}/papers/${paperId}`, withReadTimeout({
    cache: "no-store",
    ...init,
  }));
  if (res.status === 404) return null;
  if (res.status === 410) return "failed";
  if (res.status === 202) return "queued";
  if (!res.ok) {
    throw new Error(`API error ${res.status} fetching ${paperId}`);
  }
  return PaperDetailSchema.parse(await res.json());
}

export function getCachedPaper(paperId: string): PaperDetailDTO | null {
  return getSessionValue(paperCacheKey(paperId), PaperDetailSchema);
}

export function rememberPaper(paper: PaperDetailDTO) {
  setSessionValue(paperCacheKey(paper.id), paper, PAPER_CACHE_TTL_MS);
}

export async function fetchPaperClient(
  paperId: string,
  opts: { refresh?: boolean; signal?: AbortSignal } = {},
): Promise<PaperDetailDTO | "queued" | "failed" | null> {
  if (!opts.refresh) {
    const cached = getCachedPaper(paperId);
    if (cached) return cached;
  }

  const result = await fetchPaper(paperId, opts.signal ? { signal: opts.signal } : undefined);
  if (result && result !== "queued" && result !== "failed") {
    rememberPaper(result);
  }
  return result;
}

export async function fetchPaperStatus(
  paperId: string,
): Promise<PaperStatusDTO> {
  const res = await fetch(`${API_BASE_URL}/papers/${paperId}/status`, withReadTimeout({
    cache: "no-store",
  }));
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
export type SearchSortKey =
  | "relevance"
  | "score"
  | "novelty"
  | "technical"
  | "clarity"
  | "impact";

const SearchPageSchema = z.object({
  results: z.array(PaperOutSchema),
  total: z.number(),
});

export type SearchPageDTO = z.infer<typeof SearchPageSchema>;

export function rememberSearchPage(
  query: string,
  page: SearchPageDTO,
  limit = 20,
  offset = 0,
  mode: "auto" | "topic" | "specific" = "auto",
  sort: SearchSortKey = "score",
) {
  setSessionValue(
    searchCacheKey(query, limit, offset, mode, sort),
    page,
    SEARCH_CACHE_TTL_MS,
  );
}

export async function fetchSearch(
  query: string,
  limit = 20,
  offset = 0,
  mode: "auto" | "topic" | "specific" = "auto",
  sort: SearchSortKey = "relevance",
): Promise<PaperOutDTO[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset),
    mode,
    sort,
  });
  const res = await fetch(
    `${API_BASE_URL}/search?${params}`,
    withReadTimeout({ cache: "no-store" }),
  );
  if (!res.ok) {
    throw new Error(`Search API error ${res.status}`);
  }
  return z.array(PaperOutSchema).parse(await res.json());
}

export async function fetchSearchPage(
  query: string,
  limit = 20,
  offset = 0,
  mode: "auto" | "topic" | "specific" = "auto",
  sort: SearchSortKey = "relevance",
  init?: RequestInit,
): Promise<SearchPageDTO> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    offset: String(offset),
    mode,
    sort,
  });
  const res = await fetch(
    `${API_BASE_URL}/search/page?${params}`,
    withReadTimeout({ cache: "no-store", ...init }),
  );
  if (!res.ok) {
    throw new Error(`Search API error ${res.status}`);
  }
  return SearchPageSchema.parse(await res.json());
}

export async function fetchSearchPageClient(
  query: string,
  limit = 20,
  offset = 0,
  mode: "auto" | "topic" | "specific" = "auto",
  sort: SearchSortKey = "relevance",
  signal?: AbortSignal,
): Promise<SearchPageDTO> {
  const key = searchCacheKey(query, limit, offset, mode, sort);
  const cached = getSessionValue(key, SearchPageSchema);
  if (cached) return cached;

  const page = await fetchSearchPage(query, limit, offset, mode, sort, signal ? { signal } : undefined);
  setSessionValue(key, page, SEARCH_CACHE_TTL_MS);
  return page;
}

/** Live (debounced) topic-mode fuzzy search; pass an AbortSignal to cancel in-flight calls. */
export async function fetchSearchLive(
  query: string,
  sort: SearchSortKey = "relevance",
  signal?: AbortSignal,
): Promise<PaperOutDTO[]> {
  const params = new URLSearchParams({ q: query, mode: "topic", sort });
  const res = await fetch(`${API_BASE_URL}/search?${params}`, withReadTimeout({
    cache: "no-store",
    signal,
  }));
  if (!res.ok) {
    throw new Error(`Search API error ${res.status}`);
  }
  return z.array(PaperOutSchema).parse(await res.json());
}

export async function fetchSearchLiveClient(
  query: string,
  sort: SearchSortKey = "relevance",
  signal?: AbortSignal,
): Promise<PaperOutDTO[]> {
  const page = await fetchSearchPageClient(query, 20, 0, "topic", sort, signal);
  return page.results;
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
  const response = SearchLookupResponseSchema.parse(await res.json());
  rememberSearchPage(
    query,
    { results: response.results, total: response.results.length },
    20,
    0,
    response.intent === "specific" ? "specific" : "topic",
    "relevance",
  );
  return response;
}

export async function fetchSearchCount(query: string): Promise<number> {
  const params = new URLSearchParams({ q: query });
  const res = await fetch(
    `${API_BASE_URL}/search/count?${params}`,
    withReadTimeout({ cache: "no-store" }),
  );
  if (!res.ok) return 0;
  const data = z.object({ total: z.number() }).parse(await res.json());
  return data.total;
}

export async function fetchSaved(init?: RequestInit): Promise<PaperOutDTO[]> {
  const res = await fetch(
    `${API_BASE_URL}/saved`,
    withReadTimeout({ cache: "no-store", ...init }),
  );
  if (!res.ok) throw new Error(`Saved API error ${res.status}`);
  return z.array(PaperOutSchema).parse(await res.json());
}

export async function fetchSavedStatus(
  paperId: string,
  init?: RequestInit,
): Promise<boolean> {
  if (isBrowser()) return getLocalSavedPaperIds().includes(paperId);

  const res = await fetch(
    `${API_BASE_URL}/saved/${encodeURIComponent(paperId)}`,
    withReadTimeout({ cache: "no-store", ...init }),
  );
  if (!res.ok) return false;
  const data = z.object({ saved: z.boolean() }).parse(await res.json());
  return data.saved;
}

export function getLocalSavedPaperIds(): string[] {
  if (!isBrowser()) return [];
  try {
    const parsed = z.array(z.string()).parse(
      JSON.parse(window.localStorage.getItem(SAVED_PAPER_IDS_KEY) ?? "[]"),
    );
    return [...new Set(parsed)];
  } catch {
    return [];
  }
}

function setLocalSavedPaperIds(ids: string[]) {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(SAVED_PAPER_IDS_KEY, JSON.stringify([...new Set(ids)]));
  } catch {
    // Ignore localStorage write failures.
  }
}

export async function fetchSavedStatusClient(paperId: string): Promise<boolean> {
  return getLocalSavedPaperIds().includes(paperId);
}

export async function savePaper(paperId: string): Promise<void> {
  if (isBrowser()) {
    setLocalSavedPaperIds([paperId, ...getLocalSavedPaperIds()]);
    return;
  }

  const res = await fetch(`${API_BASE_URL}/saved`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paper_id: paperId }),
  });
  if (!res.ok) throw new Error(`Save failed ${res.status}`);
}

export async function unsavePaper(paperId: string): Promise<void> {
  if (isBrowser()) {
    setLocalSavedPaperIds(getLocalSavedPaperIds().filter((id) => id !== paperId));
    return;
  }

  const res = await fetch(`${API_BASE_URL}/saved/${encodeURIComponent(paperId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Unsave failed ${res.status}`);
}

const ExplorePathwayItemSchema = z.object({
  position: z.number(),
  stage: z.string(),
  why_this_paper: z.string(),
  read_focus: z.string(),
  match_quality: z.string(),
  search_query: z.string().nullable(),
  anchor_concepts: z.array(z.string()),
  paper: PaperOutSchema.nullable(),
});

export const ExplorePathwaySchema = z.object({
  id: z.string(),
  title: z.string(),
  rationale: z.string(),
  status: z.string(),
  enrichment_notes: z.record(z.string(), z.unknown()),
  seed_paper_id: z.string().nullable(),
  query_text: z.string().nullable(),
  items: z.array(ExplorePathwayItemSchema),
});

export type ExplorePathwayDTO = z.infer<typeof ExplorePathwaySchema>;
export type ExplorePathwayItemDTO = z.infer<typeof ExplorePathwayItemSchema>;

const EXPLORE_TIMEOUT_MS = 60_000;

function timeoutSignal(ms: number): AbortSignal | undefined {
  if (typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(ms);
  }
  if (typeof AbortController === "undefined") return undefined;
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

function combineAbortSignals(signals: (AbortSignal | undefined)[]): AbortSignal | undefined {
  const present = signals.filter((item): item is AbortSignal => item !== undefined);
  if (present.length === 0) return undefined;
  if (present.length === 1) return present[0];
  if (typeof AbortSignal.any === "function") {
    return AbortSignal.any(present);
  }

  const controller = new AbortController();
  const abort = () => controller.abort();
  for (const item of present) {
    if (item.aborted) {
      controller.abort();
      return controller.signal;
    }
    item.addEventListener("abort", abort, { once: true });
  }
  return controller.signal;
}

export async function postExplorePath(
  topic: string,
  force = false,
  signal?: AbortSignal,
): Promise<ExplorePathwayDTO> {
  const params = new URLSearchParams();
  if (force) params.set("force", "true");
  const url = `${API_BASE_URL}/pathways/explore${params.toString() ? `?${params}` : ""}`;
  const init: RequestInit = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, limit: 8 }),
    cache: "no-store",
  };
  init.signal = combineAbortSignals([signal, timeoutSignal(EXPLORE_TIMEOUT_MS)]);
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = `Explore API error ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string" && body.detail.trim()) {
        detail = body.detail;
      }
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(detail);
  }
  return ExplorePathwaySchema.parse(await res.json());
}
