from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Review:
    id: str
    invitation: str | None
    signatures: list[str]
    created: str | None
    modified: str | None
    content: dict[str, Any]


@dataclass(frozen=True)
class ScoreScale:
    min: float
    max: float
    source: str


@dataclass(frozen=True)
class ScoreFieldStats:
    field: str
    scale: ScoreScale | None
    confidence_weighted_score: float | None
    average_score: float | None
    normalized_confidence_weighted_score: float | None
    normalized_average_score: float | None
    scored_review_count: int
    skipped_review_count: int


@dataclass(frozen=True)
class ReviewScore:
    primary_field: str | None
    aggregate_normalized_score: float | None
    aggregate_field_count: int
    unscaled_field_count: int
    confidence_weighted_rating: float | None
    normalized_confidence_weighted_rating: float | None
    average_rating: float | None
    average_confidence: float | None
    fields: dict[str, ScoreFieldStats]
    scored_review_count: int
    skipped_review_count: int


@dataclass(frozen=True)
class PaperCandidate:
    id: str
    title: str
    venue: str | None
    domain: str | None
    invitations: list[str]
    created: str | None


@dataclass(frozen=True)
class ParsedReviewDocument:
    id: str
    title: str
    reviews: list[Review]

