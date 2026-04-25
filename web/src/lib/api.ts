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
      label: VerdictSchema,
      quote: z.string(),
    }),
  ),
  consensus: z.string().nullable(),

  score_breakdown: z.record(z.string(), z.unknown()).nullable(),
  status: z.enum(["ready", "score_only", "ingested_no_score", "not_found"]),
});

export type PaperDetailDTO = z.infer<typeof PaperDetailSchema>;

export async function fetchPaper(
  paperId: string,
  init?: RequestInit,
): Promise<PaperDetailDTO | null> {
  const res = await fetch(`${API_BASE_URL}/papers/${paperId}`, {
    cache: "no-store",
    ...init,
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`API error ${res.status} fetching ${paperId}`);
  }
  return PaperDetailSchema.parse(await res.json());
}
