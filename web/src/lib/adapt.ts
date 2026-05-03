import type { PaperDetailDTO, PaperOutDTO } from "./api";
import type { Paper, ReviewerVoice, Verdict } from "./types";

const FALLBACK_VERDICT: Verdict = "Borderline";

function asVerdict(v: string): Verdict {
  // PaperDetail.verdict can be "Insufficient reviews" — coerce to a valid pill label.
  switch (v) {
    case "Strong Accept":
    case "Accept":
    case "Weak Accept":
    case "Borderline":
    case "Reject":
    case "Insufficient reviews":
      return v;
    default:
      return FALLBACK_VERDICT;
  }
}

export function adaptPaperOut(dto: PaperOutDTO): Paper {
  return {
    id: dto.id,
    title: dto.title,
    authors: dto.authors,
    tldr:
      dto.tldr ??
      "Analysis in progress — score computed from reviewer ratings.",
    venue: dto.venue ?? "Unknown venue",
    citations: dto.citations ?? 0,
    referencesCount: dto.references_count,
    citationGraphStatus: dto.citation_graph_status,
    pagerank: dto.pagerank ?? null,
    citationInDegree: dto.citation_in_degree ?? null,
    citationOutDegree: dto.citation_out_degree ?? null,
    openreviewUrl: dto.openreview_url,
    score: dto.score,
    grade: dto.grade,
    verdict: asVerdict(dto.verdict),
    novelty: dto.novelty,
    technical: dto.technical,
    clarity: dto.clarity,
    impact: dto.impact,
    consensus: dto.consensus ?? "—",
    consensusStrength: dto.consensus_strength,
    deep: [],
    skim: [],
    reviewers: [],
    acceptance:
      dto.acceptance === "oral" ||
      dto.acceptance === "poster" ||
      dto.acceptance === "reject"
        ? dto.acceptance
        : null,
    reviewerCount: dto.reviewer_count,
  };
}

export function adaptPaperDetail(dto: PaperDetailDTO): Paper {
  const reviewers: ReviewerVoice[] = dto.reviewers.map((r) => ({
    handle: r.handle,
    rating: Math.round(r.rating),
    ratingScaleMax: r.rating_scale_max ?? null,
    label: asVerdict(r.label),
    quote: r.quote,
  }));

  return {
    id: dto.id,
    title: dto.title,
    authors: dto.authors,
    tldr:
      dto.tldr ??
      "AI summary in progress — score and reviewer voices below come from real OpenReview data.",
    venue: dto.venue ?? "Unknown venue",
    citations: dto.citations ?? 0,
    referencesCount: dto.references_count,
    citationGraphStatus: dto.citation_graph_status,
    pagerank: dto.pagerank ?? null,
    citationInDegree: dto.citation_in_degree ?? null,
    citationOutDegree: dto.citation_out_degree ?? null,
    openreviewUrl: dto.openreview_url,
    score: dto.score,
    grade: dto.grade,
    verdict: asVerdict(dto.verdict),
    novelty: dto.novelty,
    technical: dto.technical,
    clarity: dto.clarity,
    impact: dto.impact,
    consensus: dto.consensus ?? reviewers.map((r) => r.label).join(" · "),
    consensusStrength: dto.consensus_strength,
    deep: dto.deep,
    skim: dto.skim,
    reviewers,
    acceptance:
      dto.acceptance === "oral" || dto.acceptance === "poster" || dto.acceptance === "reject"
        ? dto.acceptance
        : null,
    reviewerCount: dto.reviewer_count,
  };
}
