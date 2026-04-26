from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session

from app.db.models import OpenReviewIngestFailure


def get_ingest_failure(db: Session, paper_id: str) -> OpenReviewIngestFailure | None:
    return db.get(OpenReviewIngestFailure, paper_id)


def mark_ingest_failed(
    db: Session,
    paper_id: str,
    *,
    attempts: int,
    error: str,
) -> OpenReviewIngestFailure:
    failure = OpenReviewIngestFailure(
        paper_id=paper_id,
        attempts=attempts,
        error=error[:4000],
        failed_at=datetime.now(tz=UTC),
    )
    merged = db.merge(failure)
    db.commit()
    return merged


def clear_ingest_failure(db: Session, paper_id: str) -> None:
    failure = db.get(OpenReviewIngestFailure, paper_id)
    if failure is None:
        return
    db.delete(failure)
    db.commit()
