from __future__ import annotations

from typing import Any

from app.db.models import AIInsight, VerosScore


def _dimension_from_breakdown(
    breakdown: dict[str, Any],
    name: str,
) -> int | None:
    dimensions = breakdown.get("standardized_dimensions")
    if not isinstance(dimensions, dict):
        return None
    value = dimensions.get(name)
    if isinstance(value, (int, float)):
        return round(max(0.0, min(100.0, float(value))))
    return None


def standardized_dimensions(
    score_row: VerosScore | None,
    insight: AIInsight | None,
) -> dict[str, int | None]:
    breakdown = dict(score_row.breakdown or {}) if score_row else {}
    novelty = _dimension_from_breakdown(breakdown, "novelty")
    technical = _dimension_from_breakdown(breakdown, "technical")
    clarity = _dimension_from_breakdown(breakdown, "clarity")
    impact = _dimension_from_breakdown(breakdown, "impact")
    return {
        "novelty": novelty if novelty is not None else (insight.novelty if insight else None),
        "technical": technical if technical is not None else (insight.technical if insight else None),
        "clarity": clarity if clarity is not None else (insight.clarity if insight else None),
        "impact": impact if impact is not None else (insight.impact if insight else None),
    }
