export type Verdict =
  | "Strong Accept"
  | "Accept"
  | "Weak Accept"
  | "Borderline"
  | "Reject"
  | "Insufficient reviews";

export interface ReviewerVoice {
  handle: string;
  rating: number;
  ratingScaleMax?: number | null;
  label: Verdict;
  quote: string;
}

export interface Paper {
  id: string;
  title: string;
  authors: string;
  tldr: string;
  venue: string;
  citations: number;
  referencesCount: number | null;
  citationGraphStatus: "not_enriched" | "enriched" | "failed";
  openreviewUrl?: string | null;
  score: number | null;
  grade: string;
  verdict: Verdict;
  novelty: number | null;
  technical: number | null;
  clarity: number | null;
  impact: number | null;
  consensus: string;
  consensusStrength: "strong" | "moderate" | "mixed" | "split";
  deep: string[];
  skim: string[];
  reviewers: ReviewerVoice[];
  acceptance?: "oral" | "poster" | "reject" | null;
  reviewerCount: number;
}
