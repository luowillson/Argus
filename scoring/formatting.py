from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .models import Review, ScoreScale
from .openreview_client import paper_title
from .scoring import calculate_review_score


def format_score_value(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "unknown"


def format_percent(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "unknown"


def format_scale(scale: ScoreScale | None) -> str:
    if scale is None:
        return "unknown"

    return f"{scale.min:g}-{scale.max:g} ({scale.source})"


def build_score_summary_payload(
    paper_id: str,
    title: str,
    reviews: list[Review],
    scales: dict[str, ScoreScale],
) -> dict[str, Any]:
    score = calculate_review_score(reviews, scales)
    fields = {
        field: {
            "confidence_weighted_score": stats.confidence_weighted_score,
            "normalized_score": stats.normalized_confidence_weighted_score,
            "average_score": stats.average_score,
            "normalized_average_score": stats.normalized_average_score,
            "scale": asdict(stats.scale) if stats.scale else None,
            "scored_reviews": stats.scored_review_count,
            "skipped_reviews": stats.skipped_review_count,
        }
        for field, stats in score.fields.items()
    }

    return {
        "paper": {
            "id": paper_id,
            "title": title,
            "url": f"https://openreview.net/forum?id={paper_id}",
        },
        "aggregate_normalized_score": score.aggregate_normalized_score,
        "aggregate_normalized_percent": (
            score.aggregate_normalized_score * 100
            if score.aggregate_normalized_score is not None
            else None
        ),
        "aggregate_field_count": score.aggregate_field_count,
        "unscaled_field_count": score.unscaled_field_count,
        "primary_field": score.primary_field,
        "average_confidence": score.average_confidence,
        "review_count": len(reviews),
        "fields": fields,
    }


def score_summary_payload(
    paper: Any, reviews: list[Review], scales: dict[str, ScoreScale]
) -> dict[str, Any]:
    return build_score_summary_payload(paper.id, paper_title(paper), reviews, scales)


def format_scores_text_payload(payload: dict[str, Any]) -> str:
    paper = payload["paper"]
    fields = payload["fields"]
    lines = [
        f"Paper: {paper['title']}",
        f"URL: {paper['url']}",
        "",
        f"Aggregate normalized score: {format_percent(payload['aggregate_normalized_score'])}",
        f"Scoring sections included: {payload['aggregate_field_count']}",
        f"Scoring sections missing scale: {payload['unscaled_field_count']}",
        f"Average confidence: {format_score_value(payload['average_confidence'])}",
        f"Review count: {payload['review_count']}",
        "",
        "Scoring sections:",
    ]

    if not fields:
        lines.append("- No numeric scoring fields were found.")
        return "\n".join(lines)

    for field, stats in fields.items():
        scale = stats["scale"]
        if scale:
            scale_text = f"{scale['min']:g}-{scale['max']:g}"
        else:
            scale_text = "unknown"
        lines.append(
            "- "
            f"{field}: "
            f"weighted={format_score_value(stats['confidence_weighted_score'])}, "
            f"normalized={format_percent(stats['normalized_score'])}, "
            f"average={format_score_value(stats['average_score'])}, "
            f"scale={scale_text}, "
            f"reviews={stats['scored_reviews']}"
        )

    return "\n".join(lines)


def format_scores_text(
    paper: Any, reviews: list[Review], scales: dict[str, ScoreScale]
) -> str:
    return format_scores_text_payload(score_summary_payload(paper, reviews, scales))


def format_json(paper: Any, reviews: list[Review], scales: dict[str, ScoreScale]) -> str:
    score = calculate_review_score(reviews, scales)
    payload = {
        "paper": {
            "id": paper.id,
            "title": paper_title(paper),
            "url": f"https://openreview.net/forum?id={paper.id}",
        },
        "score": asdict(score),
        "reviews": [review.__dict__ for review in reviews],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def format_markdown(
    paper: Any, reviews: list[Review], scales: dict[str, ScoreScale]
) -> str:
    score = calculate_review_score(reviews, scales)
    lines = [
        f"# Reviews for {paper_title(paper)}",
        "",
        f"Paper: https://openreview.net/forum?id={paper.id}",
        "",
        "## Score",
        "",
    ]

    if score.confidence_weighted_rating is None:
        lines.extend(
            [
                "No confidence-weighted numeric score could be computed from visible reviews.",
                "",
            ]
        )
    else:
        primary_stats = score.fields[score.primary_field] if score.primary_field else None
        lines.extend(
            [
                f"- aggregate normalized score: {format_percent(score.aggregate_normalized_score)}",
                f"- aggregate scoring sections: {score.aggregate_field_count}",
                f"- unscaled scoring sections: {score.unscaled_field_count}",
                f"- primary score field: `{score.primary_field}`",
                f"- detected scale: {format_scale(primary_stats.scale if primary_stats else None)}",
                f"- confidence-weighted score: {format_score_value(score.confidence_weighted_rating)}",
                f"- normalized confidence-weighted score: {format_percent(score.normalized_confidence_weighted_rating)}",
                f"- simple average score: {format_score_value(score.average_rating)}",
                f"- average confidence: {format_score_value(score.average_confidence)}",
                f"- scored reviews: {score.scored_review_count}",
                f"- skipped reviews: {score.skipped_review_count}",
                "",
            ]
        )
        if len(score.fields) > 1:
            lines.extend(["### Scoring Sections", ""])
            for field, stats in score.fields.items():
                lines.extend(
                    [
                        f"#### {field}",
                        "",
                        f"- confidence-weighted score: {format_score_value(stats.confidence_weighted_score)}",
                        f"- normalized score: {format_percent(stats.normalized_confidence_weighted_score)}",
                        f"- simple average score: {format_score_value(stats.average_score)}",
                        f"- normalized average score: {format_percent(stats.normalized_average_score)}",
                        f"- scale: {format_scale(stats.scale)}",
                        f"- scored reviews: {stats.scored_review_count}",
                        f"- skipped reviews: {stats.skipped_review_count}",
                        "",
                    ]
                )

    if not reviews:
        lines.append("No official reviews were found or visible to this account.")
        return "\n".join(lines)

    for index, review in enumerate(reviews, start=1):
        lines.extend(
            [
                f"## Review {index}",
                "",
                f"- id: `{review.id}`",
                f"- invitation: `{review.invitation or 'unknown'}`",
                f"- signatures: {', '.join(f'`{sig}`' for sig in review.signatures) or '`unknown`'}",
                f"- created: {review.created or 'unknown'}",
                "",
            ]
        )
        for key, value in review.content.items():
            lines.extend([f"### {key}", "", str(value), ""])

    return "\n".join(lines).rstrip()

