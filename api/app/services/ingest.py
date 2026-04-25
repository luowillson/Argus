"""Synchronous ingest: fetch from OpenReview, upsert into Postgres.

In M6 this is wrapped by a Celery task so the request can return immediately.
For now the request thread does the fetch + upsert inline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, delete

from app.config import get_settings
from app.db.models import Paper, Review
from app.services.analyze import AnalyzeError, analyze_paper
from app.services.openreview_client import (
    FetchedPaper,
    FetchedReview,
    fetch_paper_and_reviews,
)
from app.services.scoring import compute_and_store_score
from app.utils.ratings import parse_numeric, parse_recommendation

logger = logging.getLogger(__name__)


def _openreview_url(forum_id: str) -> str:
    return f"https://openreview.net/forum?id={forum_id}"


def _upsert_paper(db: Session, paper: FetchedPaper) -> None:
    stmt = insert(Paper).values(
        id=paper.id,
        title=paper.title,
        authors=paper.authors,
        venue=paper.venue,
        year=paper.publication_date.year if paper.publication_date else None,
        citations=None,
        abstract=paper.abstract,
        openreview_url=_openreview_url(paper.id),
        acceptance=paper.acceptance,
        ingested_at=datetime.now(tz=UTC),
        analyzed_at=None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Paper.__table__.c.id],
        set_={
            "title": stmt.excluded.title,
            "authors": stmt.excluded.authors,
            "venue": stmt.excluded.venue,
            "year": stmt.excluded.year,
            "abstract": stmt.excluded.abstract,
            "acceptance": stmt.excluded.acceptance,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db.exec(stmt)


def _upsert_review(db: Session, paper_id: str, review: FetchedReview) -> None:
    rating = parse_numeric(review.content.get("rating"))
    confidence = parse_numeric(review.content.get("confidence"))
    recommendation = parse_recommendation(
        review.content.get("recommendation") or review.content.get("rating")
    )
    stmt = insert(Review).values(
        id=review.id,
        paper_id=paper_id,
        invitation=review.invitation,
        signatures=review.signatures,
        rating=rating,
        confidence=confidence,
        recommendation=recommendation,
        content=review.content,
        created_at=review.created,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Review.__table__.c.id],
        set_={
            "invitation": stmt.excluded.invitation,
            "signatures": stmt.excluded.signatures,
            "rating": stmt.excluded.rating,
            "confidence": stmt.excluded.confidence,
            "recommendation": stmt.excluded.recommendation,
            "content": stmt.excluded.content,
            "created_at": stmt.excluded.created_at,
        },
    )
    db.exec(stmt)


def ingest_paper(db: Session, forum_id: str) -> dict[str, object]:
    """Fetch a paper + reviews from OpenReview and upsert into Postgres.

    Returns a small status dict so the caller can surface counts to the user.
    """
    settings = get_settings()
    paper, reviews = fetch_paper_and_reviews(
        forum_id,
        username=settings.openreview_username or None,
        password=settings.openreview_password or None,
    )

    _upsert_paper(db, paper)
    # Reviews replace-on-rerun: drop any stale rows for this paper, then re-insert.
    db.exec(delete(Review).where(Review.paper_id == paper.id))
    for review in reviews:
        _upsert_review(db, paper.id, review)
    db.commit()

    score_result = compute_and_store_score(db, paper.id)

    analyze_status: str
    analyze_error: str | None = None
    try:
        analyze_paper(db, paper.id)
        analyze_status = "ready"
    except AnalyzeError as exc:
        analyze_status = "skipped"
        analyze_error = str(exc)
        logger.warning("analyze skipped for %s: %s", paper.id, exc)
    except Exception as exc:  # network / auth / parse failure
        analyze_status = "failed"
        analyze_error = f"{type(exc).__name__}: {exc}"
        logger.exception("analyze failed for %s", paper.id)

    logger.info(
        "ingested paper %s: %d reviews, acceptance=%s, score=%s, analyze=%s",
        paper.id,
        len(reviews),
        paper.acceptance,
        score_result.score,
        analyze_status,
    )
    return {
        "paper_id": paper.id,
        "title": paper.title,
        "review_count": len(reviews),
        "acceptance": paper.acceptance,
        "venue": paper.venue,
        "score": score_result.score,
        "grade": score_result.grade,
        "verdict": score_result.verdict,
        "score_status": score_result.status,
        "analyze_status": analyze_status,
        "analyze_error": analyze_error,
    }
