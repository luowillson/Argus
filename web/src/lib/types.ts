export type Verdict =
  | "Strong Accept"
  | "Accept"
  | "Weak Accept"
  | "Borderline"
  | "Reject";

export interface ReviewerVoice {
  handle: string;
  rating: number;
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
  score: number;
  grade: string;
  verdict: Verdict;
  novelty: number;
  technical: number;
  clarity: number;
  impact: number;
  consensus: string;
  consensusStrength: "strong" | "moderate" | "mixed" | "split";
  deep: string[];
  skim: string[];
  reviewers: ReviewerVoice[];
  acceptance?: "oral" | "poster" | "reject" | null;
  reviewerCount: number;
}
