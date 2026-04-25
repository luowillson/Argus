from fastapi import APIRouter
from sqlalchemy import func, text

from app.db.models import Paper, Review
from app.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict[str, str]:
    db.exec(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/stats")
def stats(db: DbSession) -> dict[str, int]:
    """Counts of ingested papers and reviews for the landing page."""
    from sqlmodel import select

    paper_count: int = db.exec(select(func.count()).select_from(Paper)).one()  # type: ignore[arg-type]
    review_count: int = db.exec(select(func.count()).select_from(Review)).one()  # type: ignore[arg-type]
    return {"paper_count": paper_count, "review_count": review_count}
