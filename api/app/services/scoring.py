"""Glue between DB rows and the deterministic scoring formula."""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.db.models import Paper, Review, VerosScore
from app.services.veros_score import ReviewSignal, ScoreResult, compute_score


# Modern OpenReview venues (ICLR, NeurIPS, COLM…) use a 1..10 rating scale.
# Older 1..6 venues exist but cannot be reliably distinguished from a 1..10
# venue where reviewers happen to all rate ≤6. We default to 10 and let the
# caller pass an override when a venue is known to use a smaller scale.
_DEFAULT_RATING_SCALE_MAX = 10


def compute_and_store_score(db: Session, paper_id: str) -> ScoreResult:
    """Recompute the Veros score for a paper from its current review rows."""
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise ValueError(f"paper {paper_id!r} not found")

    rows = db.exec(
        select(Review.rating, Review.confidence).where(Review.paper_id == paper_id)
    ).all()

    signals = [
        ReviewSignal(
            rating=float(rating),
            confidence=float(confidence) if confidence is not None else 3.0,
        )
        for rating, confidence in rows
        if rating is not None
    ]
    result = compute_score(
        signals,
        acceptance=paper.acceptance,
        rating_scale_max=_DEFAULT_RATING_SCALE_MAX,
    )

    if result.status == "ok" and result.score is not None:
        stmt = insert(VerosScore).values(
            paper_id=paper_id,
            score=result.score,
            grade=result.grade,
            verdict=result.verdict,
            breakdown={**result.breakdown, "consensus_strength": result.consensus_strength},
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[VerosScore.__table__.c.paper_id],
            set_={
                "score": stmt.excluded.score,
                "grade": stmt.excluded.grade,
                "verdict": stmt.excluded.verdict,
                "breakdown": stmt.excluded.breakdown,
                "computed_at": stmt.excluded.computed_at,
            },
        )
        db.exec(stmt)
        db.commit()

    return result
