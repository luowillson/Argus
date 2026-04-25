from __future__ import annotations

import re

from .models import Review, ReviewScore, ScoreFieldStats, ScoreScale


NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
SCORE_VALUE_FIELDS = (
    "rating",
    "recommendation",
    "soundness",
    "presentation",
    "contribution",
    "quality",
    "clarity",
    "significance",
    "originality",
)
PRIMARY_SCORE_FIELDS = ("rating", "recommendation")


def parse_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = NUMBER_PATTERN.search(value)
        if match:
            return float(match.group())

    return None


def normalize_score(value: float, scale: ScoreScale | None) -> float | None:
    if scale is None or scale.max <= scale.min:
        return None

    return (value - scale.min) / (scale.max - scale.min)


def calculate_field_stats(
    reviews: list[Review], field: str, scale: ScoreScale | None
) -> ScoreFieldStats | None:
    scored_reviews: list[tuple[float, float]] = []
    skipped_review_count = 0

    for review in reviews:
        score = parse_number(review.content.get(field))
        confidence = parse_number(review.content.get("confidence"))
        if score is None:
            continue
        if confidence is None or confidence <= 0:
            skipped_review_count += 1
            continue

        scored_reviews.append((score, confidence))

    if not scored_reviews:
        return None

    score_total = sum(score for score, _ in scored_reviews)
    confidence_total = sum(confidence for _, confidence in scored_reviews)
    weighted_total = sum(score * confidence for score, confidence in scored_reviews)
    weighted_score = weighted_total / confidence_total
    average_score = score_total / len(scored_reviews)

    return ScoreFieldStats(
        field=field,
        scale=scale,
        confidence_weighted_score=weighted_score,
        average_score=average_score,
        normalized_confidence_weighted_score=normalize_score(weighted_score, scale),
        normalized_average_score=normalize_score(average_score, scale),
        scored_review_count=len(scored_reviews),
        skipped_review_count=skipped_review_count,
    )


def calculate_review_score(
    reviews: list[Review], scales: dict[str, ScoreScale]
) -> ReviewScore:
    fields: dict[str, ScoreFieldStats] = {}
    for field in SCORE_VALUE_FIELDS:
        stats = calculate_field_stats(reviews, field, scales.get(field))
        if stats:
            fields[field] = stats

    primary_field = next((field for field in PRIMARY_SCORE_FIELDS if field in fields), None)
    if primary_field is None:
        primary_field = next(iter(fields), None)

    primary_stats = fields.get(primary_field) if primary_field else None
    normalized_scores = [
        stats.normalized_confidence_weighted_score
        for stats in fields.values()
        if stats.normalized_confidence_weighted_score is not None
    ]
    unscaled_field_count = sum(
        1
        for stats in fields.values()
        if stats.confidence_weighted_score is not None
        and stats.normalized_confidence_weighted_score is None
    )
    confidence_values = [
        confidence
        for review in reviews
        if (confidence := parse_number(review.content.get("confidence"))) is not None
    ]

    return ReviewScore(
        primary_field=primary_field,
        aggregate_normalized_score=(
            sum(normalized_scores) / len(normalized_scores)
            if normalized_scores
            else None
        ),
        aggregate_field_count=len(normalized_scores),
        unscaled_field_count=unscaled_field_count,
        confidence_weighted_rating=(
            primary_stats.confidence_weighted_score if primary_stats else None
        ),
        normalized_confidence_weighted_rating=(
            primary_stats.normalized_confidence_weighted_score if primary_stats else None
        ),
        average_rating=primary_stats.average_score if primary_stats else None,
        average_confidence=(
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else None
        ),
        fields=fields,
        scored_review_count=primary_stats.scored_review_count if primary_stats else 0,
        skipped_review_count=primary_stats.skipped_review_count if primary_stats else 0,
    )

