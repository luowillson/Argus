from typing import Literal

from pydantic import BaseModel

Verdict = Literal[
    "Strong Accept",
    "Accept",
    "Weak Accept",
    "Borderline",
    "Reject",
    "Insufficient reviews",
]
ConsensusStrength = Literal["strong", "moderate", "mixed", "split"]


class ReviewerVoice(BaseModel):
    handle: str
    rating: int
    rating_scale_max: int | None = None
    label: Verdict
    quote: str


class PaperDetail(BaseModel):
    id: str
    title: str
    authors: str  # joined for display; the array lives on Paper.authors
    venue: str | None
    citations: int | None
    openreview_url: str
    acceptance: str | None

    # Score
    score: float | None
    grade: str
    verdict: Verdict
    consensus_strength: ConsensusStrength
    reviewer_count: int

    # Per-dimension (LLM-driven, M5). Placeholder values until then.
    novelty: int | None
    technical: int | None
    clarity: int | None
    impact: int | None

    # AI insights (M5). All optional until the analyze step has run.
    tldr: str | None
    deep: list[str]
    skim: list[str]
    reviewers: list[ReviewerVoice]
    consensus: str | None  # human-readable, e.g. "Accept · Accept · Weak Accept"

    score_breakdown: dict[str, object] | None
    status: Literal[
        "ready",
        "score_only",
        "ingested_no_score",
        "not_found",
    ]


class PaperStatus(BaseModel):
    paper_id: str
    ingest: Literal["queued", "ready", "failed"]
    analysis: Literal["pending", "ready", "failed"]


class PaperOut(BaseModel):
    """Lightweight shape returned by GET /search — no reviewers/deep/skim."""

    id: str
    title: str
    authors: str
    venue: str | None
    acceptance: str | None
    score: float | None
    grade: str
    verdict: Verdict
    novelty: int | None
    technical: int | None
    clarity: int | None
    impact: int | None
    tldr: str | None
    consensus: str | None
    consensus_strength: ConsensusStrength
    reviewer_count: int
