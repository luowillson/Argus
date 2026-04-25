"""Deterministic Veros Score (0..10) computed from reviews + acceptance.

The headline number is fully deterministic; per-dimension scores
(novelty/technical/clarity/impact) come from the LLM in M5.

Formula (all components on a 0..10 scale, then weighted):
    quality      = weighted_mean(ratings, weights = 0.5 + 0.125*confidence)
    consensus    = clamp(10 - 2*sd, 0, 10)
    acceptance   = 5 + 5*accepted_flag         (accepted=1, reject=0, unknown=0.5)
    volume_bonus = min(1.0, 0.25*(N-2))         (caps at N=6)

    score = 0.55*quality + 0.25*consensus + 0.15*acceptance + 0.05*(10*volume_bonus)
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class ReviewSignal:
    rating: float  # 1..10 (rescale older 1..6 venues before passing in)
    confidence: float  # 1..5; defaults to 3.0 if missing


@dataclass(frozen=True)
class ScoreResult:
    score: float | None  # 0..10, None if insufficient
    grade: str
    verdict: str
    consensus_strength: Literal["strong", "moderate", "mixed", "split"]
    breakdown: dict[str, object]
    status: Literal["ok", "insufficient_reviews"]


_GRADE_BUCKETS: list[tuple[float, str]] = [
    (9.0, "A+"),
    (8.3, "A"),
    (7.7, "A-"),
    (7.0, "B+"),
    (6.3, "B"),
    (5.7, "B-"),
    (5.0, "C+"),
    (4.0, "C"),
    (0.0, "D"),
]


def _grade_for(score: float) -> str:
    for threshold, label in _GRADE_BUCKETS:
        if score >= threshold:
            return label
    return "D"


def _verdict_for(score: float) -> str:
    if score >= 8.5:
        return "Strong Accept"
    if score >= 7.0:
        return "Accept"
    if score >= 6.0:
        return "Weak Accept"
    if score >= 5.0:
        return "Borderline"
    return "Reject"


def _consensus_label(sd: float) -> Literal["strong", "moderate", "mixed", "split"]:
    if sd < 0.8:
        return "strong"
    if sd < 1.6:
        return "moderate"
    if sd < 2.5:
        return "mixed"
    return "split"


def _accepted_flag(acceptance: str | None) -> float:
    if acceptance in {"oral", "poster"}:
        return 1.0
    if acceptance == "reject":
        return 0.0
    return 0.5


def _normalize_rating(rating: float, scale_max: int) -> float:
    """Rescale older 1..6 venues to a 1..10 axis. Round to 0.5."""
    if scale_max >= 10:
        return min(10.0, max(0.0, rating))
    if scale_max <= 0:
        return rating
    rescaled = rating * (10.0 / scale_max)
    return round(min(10.0, max(0.0, rescaled)) * 2) / 2


def compute_score(
    signals: list[ReviewSignal],
    *,
    acceptance: str | None,
    rating_scale_max: int = 10,
) -> ScoreResult:
    """Compute the Veros Score from a paper's review signals."""
    valid = [s for s in signals if s.rating is not None]
    n = len(valid)
    if n < 2:
        return ScoreResult(
            score=None,
            grade="—",
            verdict="Insufficient reviews",
            consensus_strength="split",
            breakdown={"n_reviews": n, "reason": "need >=2 valid ratings"},
            status="insufficient_reviews",
        )

    ratings = [_normalize_rating(s.rating, rating_scale_max) for s in valid]
    confidences = [s.confidence if s.confidence is not None else 3.0 for s in valid]
    weights = [0.5 + 0.125 * c for c in confidences]
    weight_sum = sum(weights)

    weighted_mean = sum(r * w for r, w in zip(ratings, weights, strict=True)) / weight_sum
    variance = sum(
        w * (r - weighted_mean) ** 2 for r, w in zip(ratings, weights, strict=True)
    ) / weight_sum
    sd = math.sqrt(variance)

    quality = weighted_mean
    consensus = max(0.0, min(10.0, 10.0 - 2.0 * sd))
    accepted = _accepted_flag(acceptance)
    acceptance_component = 5.0 + 5.0 * accepted
    volume_bonus = min(1.0, 0.25 * (n - 2))

    raw = (
        0.55 * quality
        + 0.25 * consensus
        + 0.15 * acceptance_component
        + 0.05 * (10.0 * volume_bonus)
    )
    score = round(max(0.0, min(10.0, raw)), 1)

    breakdown = {
        "n_reviews": n,
        "weighted_mean": round(weighted_mean, 3),
        "sd": round(sd, 3),
        "quality": round(quality, 3),
        "consensus": round(consensus, 3),
        "acceptance_component": round(acceptance_component, 3),
        "volume_bonus": round(volume_bonus, 3),
        "raw_ratings": ratings,
        "raw_confidences": confidences,
        "acceptance": acceptance,
    }

    return ScoreResult(
        score=score,
        grade=_grade_for(score),
        verdict=_verdict_for(score),
        consensus_strength=_consensus_label(sd),
        breakdown=breakdown,
        status="ok",
    )


def result_to_dict(result: ScoreResult) -> dict[str, object]:
    return asdict(result)
