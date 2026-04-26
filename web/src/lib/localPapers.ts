import { z } from "zod";
import {
  API_BASE_URL,
  type AuthorRankingDTO,
  type AuthorRankingOrder,
  type ExplorePathwayDTO,
  type LocalExploreOrderCandidate,
  PaperDetailSchema,
  type PaperDetailDTO,
  type PaperOutDTO,
  type SearchPageDTO,
  type SearchSortKey,
  postLocalExploreOrder,
  rememberPaper,
} from "@/lib/api";
import { adaptPaperDetail } from "@/lib/adapt";
import { VEROS_PAPERS } from "@/lib/mock-papers";

const CorpusSchema = z.union([
  z.array(PaperDetailSchema),
  z.object({
    generated_at: z.string().optional(),
    corpus_version: z.string().optional(),
    corpus_cursor: z.string().nullable().optional(),
    paper_count: z.number().optional(),
    papers: z.array(PaperDetailSchema),
  }),
]);
const CorpusChangesSchema = z.object({
  generated_at: z.string().optional(),
  corpus_version: z.string(),
  corpus_cursor: z.string().nullable().optional(),
  paper_count: z.number(),
  papers: z.array(PaperDetailSchema),
  deleted_ids: z.array(z.string()).optional(),
});
const CorpusVersionSchema = z.object({
  corpus_version: z.string(),
  paper_count: z.number(),
  latest_at: z.string().nullable().optional(),
});
const LOCAL_PAPER_OVERLAY_KEY = "veros:local-paper-overlay:v1";
export const LOCAL_CORPUS_UPDATED_EVENT = "veros:local-corpus-updated";

let corpusPromise: Promise<PaperDetailDTO[]> | null = null;
let corpusCache: PaperDetailDTO[] | null = null;
let corpusById: Map<string, PaperDetailDTO> | null = null;
let corpusVersion: string | null = null;
let corpusCursor: string | null = null;
let authorRankingsCache: {
  source: PaperDetailDTO[];
  rankings: AuthorRankingDTO[];
} | null = null;

function isBrowser() {
  return typeof window !== "undefined";
}

function loadLocalOverlay(): PaperDetailDTO[] {
  if (!isBrowser()) return [];
  try {
    return z.array(PaperDetailSchema).parse(
      JSON.parse(window.localStorage.getItem(LOCAL_PAPER_OVERLAY_KEY) ?? "[]"),
    );
  } catch {
    return [];
  }
}

function saveLocalOverlay(papers: PaperDetailDTO[]) {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(LOCAL_PAPER_OVERLAY_KEY, JSON.stringify(papers));
  } catch {
    // Ignore storage quota/security errors; the in-memory index is still updated.
  }
}

function mergePapers(
  base: PaperDetailDTO[],
  overlay: PaperDetailDTO[],
): PaperDetailDTO[] {
  const byId = new Map(base.map((paper) => [paper.id, paper]));
  overlay.forEach((paper) => byId.set(paper.id, paper));
  return Array.from(byId.values());
}

function notifyCorpusUpdated() {
  if (!isBrowser()) return;
  window.dispatchEvent(new CustomEvent(LOCAL_CORPUS_UPDATED_EVENT));
}

function parseCorpusPayload(payload: unknown): {
  papers: PaperDetailDTO[];
  version: string | null;
  cursor: string | null;
} {
  const parsed = CorpusSchema.parse(payload);
  if (Array.isArray(parsed)) {
    return { papers: parsed, version: null, cursor: null };
  }
  return {
    papers: parsed.papers,
    version: parsed.corpus_version ?? null,
    cursor: parsed.corpus_cursor ?? null,
  };
}

function mockDetailCorpus(): PaperDetailDTO[] {
  return VEROS_PAPERS.map((paper) => ({
    id: paper.id,
    title: paper.title,
    authors: paper.authors,
    venue: paper.venue,
    citations: paper.citations,
    openreview_url: `https://openreview.net/forum?id=${encodeURIComponent(paper.id)}`,
    acceptance: paper.acceptance ?? null,
    score: paper.score,
    grade: paper.grade,
    verdict: paper.verdict,
    consensus_strength: paper.consensusStrength,
    reviewer_count: paper.reviewerCount,
    novelty: paper.novelty,
    technical: paper.technical,
    clarity: paper.clarity,
    impact: paper.impact,
    tldr: paper.tldr,
    deep: paper.deep,
    skim: paper.skim,
    reviewers: paper.reviewers.map((reviewer) => ({
      handle: reviewer.handle,
      rating: reviewer.rating,
      rating_scale_max: reviewer.ratingScaleMax ?? null,
      label: reviewer.label,
      quote: reviewer.quote,
    })),
    consensus: paper.consensus,
    score_breakdown: null,
    status: "ready",
  }));
}

async function fetchCorpus(): Promise<PaperDetailDTO[]> {
  try {
    const res = await fetch("/data/papers.json", { cache: "force-cache" });
    if (!res.ok) throw new Error(`Static corpus returned ${res.status}`);
    const parsed = parseCorpusPayload(await res.json());
    corpusVersion = parsed.version;
    corpusCursor = parsed.cursor;
    return parsed.papers;
  } catch {
    try {
      const res = await fetch(`${API_BASE_URL}/corpus/papers`, {
        cache: "force-cache",
      });
      if (!res.ok) throw new Error(`API corpus returned ${res.status}`);
      const parsed = parseCorpusPayload(await res.json());
      corpusVersion = parsed.version;
      corpusCursor = parsed.cursor;
      return parsed.papers;
    } catch {
      return mockDetailCorpus();
    }
  }
}

export async function loadLocalPaperCorpus(): Promise<PaperDetailDTO[]> {
  if (corpusCache) return corpusCache;
  corpusPromise ??= fetchCorpus().then((papers) => {
    corpusCache = mergePapers(papers, loadLocalOverlay());
    corpusById = new Map(papers.map((paper) => [paper.id, paper]));
    corpusCache.forEach((paper) => corpusById?.set(paper.id, paper));
    corpusCache.forEach(rememberPaper);
    return corpusCache;
  });
  return corpusPromise;
}

export function upsertLocalPaper(paper: PaperDetailDTO) {
  const overlay = loadLocalOverlay();
  const nextOverlay = mergePapers(overlay, [paper]);
  saveLocalOverlay(nextOverlay);

  if (corpusCache) {
    corpusCache = mergePapers(corpusCache, [paper]);
  }
  corpusById ??= new Map();
  corpusById.set(paper.id, paper);
  rememberPaper(paper);
  notifyCorpusUpdated();
}

export async function syncLocalCorpusFromRemote(): Promise<boolean> {
  if (corpusCache === null && corpusVersion === null) return false;

  const versionRes = await fetch(`${API_BASE_URL}/corpus/version`, {
    cache: "no-store",
  });
  if (!versionRes.ok) return false;

  const remoteVersion = CorpusVersionSchema.parse(await versionRes.json());
  if (remoteVersion.corpus_version === corpusVersion) return false;

  if (corpusCursor) {
    const changesRes = await fetch(
      `${API_BASE_URL}/corpus/changes?since=${encodeURIComponent(corpusCursor)}`,
      { cache: "no-store" },
    );
    if (changesRes.ok) {
      const changes = CorpusChangesSchema.parse(await changesRes.json());
      const byId = new Map((corpusCache ?? []).map((paper) => [paper.id, paper]));
      changes.deleted_ids?.forEach((id) => byId.delete(id));
      changes.papers.forEach((paper) => byId.set(paper.id, paper));

      const changedIds = new Set(changes.papers.map((paper) => paper.id));
      const deletedIds = new Set(changes.deleted_ids ?? []);
      const overlay = loadLocalOverlay().filter(
        (paper) => !changedIds.has(paper.id) && !deletedIds.has(paper.id),
      );
      saveLocalOverlay(overlay);

      corpusCache = mergePapers(Array.from(byId.values()), overlay);
      corpusById = new Map(corpusCache.map((paper) => [paper.id, paper]));
      corpusVersion = changes.corpus_version;
      corpusCursor = changes.corpus_cursor ?? remoteVersion.latest_at ?? corpusCursor;
      changes.papers.forEach(rememberPaper);
      notifyCorpusUpdated();
      return true;
    }
  }

  const corpusRes = await fetch(
    `${API_BASE_URL}/corpus/papers?version=${encodeURIComponent(remoteVersion.corpus_version)}`,
    { cache: "no-store" },
  );
  if (!corpusRes.ok) return false;

  const parsed = parseCorpusPayload(await corpusRes.json());
  const baseById = new Map(parsed.papers.map((paper) => [paper.id, paper]));
  const overlay = loadLocalOverlay().filter((paper) => !baseById.has(paper.id));
  saveLocalOverlay(overlay);

  corpusCache = mergePapers(parsed.papers, overlay);
  corpusById = new Map(corpusCache.map((paper) => [paper.id, paper]));
  corpusVersion = parsed.version ?? remoteVersion.corpus_version;
  corpusCursor = parsed.cursor ?? remoteVersion.latest_at ?? null;
  corpusCache.forEach(rememberPaper);
  notifyCorpusUpdated();
  return true;
}

export async function findLocalPaper(paperId: string): Promise<PaperDetailDTO | null> {
  await loadLocalPaperCorpus();
  return corpusById?.get(paperId) ?? null;
}

export function paperDetailToOut(paper: PaperDetailDTO): PaperOutDTO {
  return {
    id: paper.id,
    title: paper.title,
    authors: paper.authors,
    venue: paper.venue,
    acceptance: paper.acceptance,
    score: paper.score,
    grade: paper.grade,
    verdict: paper.verdict,
    novelty: paper.novelty,
    technical: paper.technical,
    clarity: paper.clarity,
    impact: paper.impact,
    tldr: paper.tldr,
    consensus: paper.consensus,
    consensus_strength: paper.consensus_strength,
    reviewer_count: paper.reviewer_count,
  };
}

function normalize(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "");
}

function splitAuthors(authors: string): string[] {
  return authors
    .split(",")
    .map((author) => author.trim())
    .filter((author) => author && normalize(author) !== "unknown");
}

function roundTo(value: number, places: number): number {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

function buildLocalAuthorRankings(papers: PaperDetailDTO[]): AuthorRankingDTO[] {
  type AuthorStats = {
    author: string;
    scores: number[];
    topPaper: PaperDetailDTO;
    lowestPaper: PaperDetailDTO;
  };

  const byAuthor = new Map<string, AuthorStats>();

  for (const paper of papers) {
    if (paper.score === null) continue;

    for (const author of splitAuthors(paper.authors)) {
      const key = normalize(author);
      const existing = byAuthor.get(key);

      if (!existing) {
        byAuthor.set(key, {
          author,
          scores: [paper.score],
          topPaper: paper,
          lowestPaper: paper,
        });
        continue;
      }

      existing.scores.push(paper.score);
      if (
        paper.score > (existing.topPaper.score ?? 0) ||
        (paper.score === existing.topPaper.score && paper.title < existing.topPaper.title)
      ) {
        existing.topPaper = paper;
      }
      if (
        paper.score < (existing.lowestPaper.score ?? 0) ||
        (paper.score === existing.lowestPaper.score && paper.title < existing.lowestPaper.title)
      ) {
        existing.lowestPaper = paper;
      }
    }
  }

  return Array.from(byAuthor.values()).map((stats) => {
    const total = stats.scores.reduce((sum, score) => sum + score, 0);
    const average = total / stats.scores.length;

    return {
      author: stats.author,
      paper_count: stats.scores.length,
      average_score: roundTo(average, 2),
      top_paper_id: stats.topPaper.id,
      top_paper_title: stats.topPaper.title,
      top_score: roundTo(stats.topPaper.score ?? 0, 1),
      lowest_paper_id: stats.lowestPaper.id,
      lowest_paper_title: stats.lowestPaper.title,
      lowest_score: roundTo(stats.lowestPaper.score ?? 0, 1),
    };
  });
}

async function loadLocalAuthorRankings(): Promise<AuthorRankingDTO[]> {
  const papers = await loadLocalPaperCorpus();
  if (authorRankingsCache?.source === papers) return authorRankingsCache.rankings;

  const rankings = buildLocalAuthorRankings(papers);
  authorRankingsCache = { source: papers, rankings };
  return rankings;
}

export async function searchLocalAuthorRankings(
  limit = 100,
  minPapers = 3,
  order: AuthorRankingOrder = "best",
  query = "",
): Promise<AuthorRankingDTO[]> {
  const normalizedQuery = normalize(query.trim());
  const effectiveMinPapers = normalizedQuery ? 1 : minPapers;
  const rankings = (await loadLocalAuthorRankings()).filter(
    (ranking) =>
      ranking.paper_count >= effectiveMinPapers &&
      (!normalizedQuery || normalize(ranking.author).includes(normalizedQuery)),
  );

  rankings.sort((left, right) => {
    const scoreDelta =
      order === "worst"
        ? left.average_score - right.average_score
        : right.average_score - left.average_score;

    return (
      scoreDelta ||
      right.paper_count - left.paper_count ||
      left.author.localeCompare(right.author)
    );
  });

  return rankings.slice(0, limit);
}

function tokens(value: string): string[] {
  return normalize(value)
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 2);
}

function searchableText(paper: PaperDetailDTO): string {
  return [
    paper.title,
    paper.authors,
    paper.venue,
    paper.tldr,
    paper.consensus,
    paper.deep.join(" "),
    paper.skim.join(" "),
    paper.reviewers.map((reviewer) => reviewer.quote).join(" "),
  ].join(" ");
}

function relevanceScore(paper: PaperDetailDTO, query: string): number {
  const q = normalize(query.trim());
  if (!q) return 1;

  const title = normalize(paper.title);
  const authors = normalize(paper.authors);
  const haystack = normalize(searchableText(paper));
  const parts = tokens(query);
  let score = 0;

  if (title === q) score += 200;
  if (title.includes(q)) score += 80;
  if (authors.includes(q)) score += 24;
  if (haystack.includes(q)) score += 18;

  for (const token of parts) {
    if (title.includes(token)) score += 10;
    if (authors.includes(token)) score += 4;
    if (haystack.includes(token)) score += 2;
  }

  return score;
}

function sortValue(paper: PaperDetailDTO, sort: SearchSortKey): number {
  if (sort === "relevance") return 0;
  if (sort === "score") return paper.score ?? 0;
  return paper[sort] ?? 0;
}

export async function searchLocalPapers(
  query: string,
  limit = 20,
  offset = 0,
  _mode: "auto" | "topic" | "specific" = "auto",
  sort: SearchSortKey = "relevance",
): Promise<SearchPageDTO> {
  void _mode;
  const q = query.trim();
  const papers = await loadLocalPaperCorpus();
  const ranked = papers
    .map((paper) => ({ paper, relevance: relevanceScore(paper, q) }))
    .filter(({ relevance }) => !q || relevance > 0);

  ranked.sort((left, right) => {
    if (q && sort === "relevance") {
      return right.relevance - left.relevance || (right.paper.score ?? 0) - (left.paper.score ?? 0);
    }
    return (
      sortValue(right.paper, sort) - sortValue(left.paper, sort) ||
      right.relevance - left.relevance ||
      (right.paper.score ?? 0) - (left.paper.score ?? 0)
    );
  });

  return {
    results: ranked.slice(offset, offset + limit).map(({ paper }) => paperDetailToOut(paper)),
    total: ranked.length,
  };
}

type ExploreStage = {
  name: string;
  purpose: string;
  terms: string[];
};

type RankedExplorePaper = {
  paper: PaperDetailDTO;
  relevance: number;
  quality: number;
};

const EXPLORE_STAGE_COUNT = 4;
const EXPLORE_PER_STAGE = 3;
const EXPLORE_MAX_ITEMS = 10;

function dimensionAverage(paper: PaperDetailDTO): number {
  const values = [paper.novelty, paper.technical, paper.clarity, paper.impact]
    .filter((value): value is number => typeof value === "number");
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function paperQualityScore(paper: PaperDetailDTO): number {
  return (paper.score ?? 0) * 10 + dimensionAverage(paper);
}

function exploreStages(query: string): ExploreStage[] {
  return [
    {
      name: "Foundations",
      purpose: `Start with accessible papers that establish the background for ${query}.`,
      terms: ["foundation", "survey", "introduction", "benchmark", "representation"],
    },
    {
      name: "Core methods",
      purpose: `Move into the main technical methods and architectures behind ${query}.`,
      terms: ["method", "architecture", "training", "algorithm", "model"],
    },
    {
      name: "Evaluation and analysis",
      purpose: `Read work that tests, compares, or interprets how ${query} behaves in practice.`,
      terms: ["evaluation", "analysis", "benchmark", "ablation", "interpretability"],
    },
    {
      name: "Frontier and applications",
      purpose: `Finish with higher-scoring recent papers that connect ${query} to active research directions.`,
      terms: ["application", "scaling", "efficient", "frontier", "state of the art"],
    },
  ];
}

function stageQuery(query: string, stage: ExploreStage): string {
  return `${query} ${stage.terms.join(" ")}`;
}

function readFocusForPaper(
  paper: PaperDetailDTO,
  stage: ExploreStage,
  query: string,
): string {
  if (paper.deep.length > 0) {
    return `Read ${paper.deep[0]} to connect this paper to ${query}.`;
  }
  if (paper.tldr) {
    return paper.tldr;
  }
  return stage.purpose;
}

function rankExplorePapers(
  papers: PaperDetailDTO[],
  query: string,
): RankedExplorePaper[] {
  return papers
    .map((paper) => {
      const relevance = relevanceScore(paper, query);
      return {
        paper,
        relevance,
        quality: paperQualityScore(paper),
      };
    })
    .filter(({ relevance }) => relevance > 0)
    .sort((left, right) => {
      return (
        right.relevance - left.relevance ||
        right.quality - left.quality ||
        (right.paper.score ?? 0) - (left.paper.score ?? 0)
      );
    });
}

function candidateForGemini(item: ExplorePathwayDTO["items"][number]): LocalExploreOrderCandidate | null {
  if (!item.paper) return null;
  return {
    paper_id: item.paper.id,
    title: item.paper.title,
    stage: item.stage,
    year: null,
    veros_score: item.paper.score,
    tldr: item.paper.tldr,
    anchor_concepts: item.anchor_concepts,
  };
}

async function applyGeminiOrdering(
  topic: string,
  items: ExplorePathwayDTO["items"],
): Promise<{ items: ExplorePathwayDTO["items"]; rationale: string; model: string | null } | null> {
  const candidates = items
    .map(candidateForGemini)
    .filter((candidate): candidate is LocalExploreOrderCandidate => candidate !== null);
  if (candidates.length === 0) return null;

  const ordered = await postLocalExploreOrder(topic, candidates);
  const byId = new Map(
    items
      .filter((item) => item.paper !== null)
      .map((item) => [item.paper?.id, item] as const),
  );
  const usedIds = new Set<string>();
  const nextItems: ExplorePathwayDTO["items"] = [];

  for (const orderedItem of ordered.items) {
    const item = byId.get(orderedItem.paper_id);
    if (!item || usedIds.has(orderedItem.paper_id)) continue;
    usedIds.add(orderedItem.paper_id);
    nextItems.push({
      ...item,
      position: nextItems.length + 1,
      read_focus: orderedItem.why_now,
    });
  }

  for (const item of items) {
    const paperId = item.paper?.id;
    if (paperId && usedIds.has(paperId)) continue;
    nextItems.push({
      ...item,
      position: nextItems.length + 1,
    });
  }

  return {
    items: nextItems,
    rationale: ordered.rationale,
    model: ordered.model,
  };
}

export async function buildLocalExplorePath(topic: string): Promise<ExplorePathwayDTO> {
  const query = topic.trim();
  if (!query) {
    throw new Error("Enter a topic to explore.");
  }

  const papers = await loadLocalPaperCorpus();
  const ranked = rankExplorePapers(papers, query);
  if (ranked.length === 0) {
    throw new Error(`No local papers matched "${query}". Try a broader topic.`);
  }

  const stages = exploreStages(query);
  const usedIds = new Set<string>();
  const items: ExplorePathwayDTO["items"] = [];

  for (const stage of stages) {
    const rankedForStage = ranked
      .map(({ paper, relevance, quality }) => ({
        paper,
        relevance,
        quality,
        stageRelevance: relevanceScore(paper, stageQuery(query, stage)),
      }))
      .filter(({ paper, stageRelevance }) => !usedIds.has(paper.id) && stageRelevance > 0)
      .sort((left, right) => {
        return (
          right.stageRelevance - left.stageRelevance ||
          right.quality - left.quality ||
          right.relevance - left.relevance
        );
      });

    for (const candidate of rankedForStage.slice(0, EXPLORE_PER_STAGE)) {
      usedIds.add(candidate.paper.id);
      items.push({
        position: items.length + 1,
        stage: stage.name,
        why_this_paper: stage.purpose,
        read_focus: readFocusForPaper(candidate.paper, stage, query),
        match_quality: candidate.relevance >= 18 ? "strong" : "weak",
        search_query: stageQuery(query, stage),
        anchor_concepts: tokens(query).slice(0, 6),
        paper: paperDetailToOut(candidate.paper),
      });
      if (items.length >= EXPLORE_MAX_ITEMS) break;
    }
    if (items.length >= EXPLORE_MAX_ITEMS) break;
  }

  if (items.length < EXPLORE_STAGE_COUNT) {
    for (const candidate of ranked) {
      if (usedIds.has(candidate.paper.id)) continue;
      const stage = stages[Math.min(items.length, stages.length - 1)];
      usedIds.add(candidate.paper.id);
      items.push({
        position: items.length + 1,
        stage: stage.name,
        why_this_paper: stage.purpose,
        read_focus: readFocusForPaper(candidate.paper, stage, query),
        match_quality: candidate.relevance >= 18 ? "strong" : "weak",
        search_query: query,
        anchor_concepts: tokens(query).slice(0, 6),
        paper: paperDetailToOut(candidate.paper),
      });
      if (items.length >= Math.min(EXPLORE_MAX_ITEMS, ranked.length)) break;
    }
  }

  items.forEach((item, index) => {
    item.position = index + 1;
  });

  let finalItems = items;
  let orderingSource = "local_json";
  let orderingRationale = "";
  let orderingModel: string | null = null;
  try {
    const ordered = await applyGeminiOrdering(query, items);
    if (ordered !== null) {
      finalItems = ordered.items;
      orderingRationale = ordered.rationale;
      orderingModel = ordered.model;
      orderingSource = "gemini";
    }
  } catch {
    // Gemini ordering is best-effort; the local JSON ordering keeps Explore usable.
  }

  const strongCount = finalItems.filter((item) => item.match_quality === "strong").length;
  const rationale = [
    "Built from the local paper JSON corpus. Papers are matched by topic text, ranked by relevance plus Veros/dimension scores, and grouped from foundations to frontier.",
    orderingRationale,
  ].filter(Boolean).join("\n\n");

  return {
    id: `local-json:${encodeURIComponent(query)}:${Date.now()}`,
    title: `Learning pathway for ${query}`,
    rationale,
    status: "ready",
    enrichment_notes: {
      ordering_source: orderingSource,
      ordering_model: orderingModel,
      topic_count: stages.length,
      paper_count: finalItems.length,
      strong_stage_count: strongCount,
      weak_or_missing_stage_count: finalItems.length - strongCount,
      needs_enrichment: false,
    },
    seed_paper_id: null,
    query_text: query,
    items: finalItems,
  };
}

function looksLikeSpecificTitle(query: string): boolean {
  const parts = query.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 5) return true;
  if (parts.length <= 2) return false;
  return parts.filter((part) => /^[A-Z0-9]/.test(part)).length >= parts.length - 1;
}

export async function getLocalSearchDestination(query: string): Promise<string> {
  const q = query.trim();
  const papers = await loadLocalPaperCorpus();
  let best: { id: string; score: number } | null = null;

  for (const paper of papers) {
    const score = relevanceScore(paper, q);
    if (!best || score > best.score) best = { id: paper.id, score };
  }

  const params = new URLSearchParams({ q });
  if (best && best.score >= 80 && looksLikeSpecificTitle(q)) {
    params.set("focus", best.id);
  }
  return `/search?${params}`;
}

export async function localSavedPapers(ids: string[]) {
  const papers = await loadLocalPaperCorpus();
  const byId = new Map(papers.map((paper) => [paper.id, adaptPaperDetail(paper)]));
  return ids.map((id) => byId.get(id)).filter((paper) => paper !== undefined);
}
