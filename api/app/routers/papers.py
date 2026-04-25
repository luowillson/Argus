from fastapi import APIRouter, HTTPException

from app.deps import DbSession
from app.schemas.paper import PaperDetail
from app.services.ingest import ingest_paper
from app.services.openreview_client import parse_forum_id
from app.services.paper_view import build_paper_detail

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: str, db: DbSession) -> PaperDetail:
    """Return a fully assembled `PaperDetail`. M4 returns score-but-no-LLM-insights."""
    detail = build_paper_detail(db, parse_forum_id(paper_id))
    if detail is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id!r} not ingested")
    return detail


@router.post("/{paper_id}/ingest")
def ingest(paper_id: str, db: DbSession) -> dict[str, object]:
    """Synchronously fetch a paper + reviews from OpenReview and persist.

    M3 runs this inline; M6 wraps it in a Celery task and returns immediately.
    Accepts either a raw forum id or a forum URL (URL-encoded).
    """
    forum_id = parse_forum_id(paper_id)
    try:
        result = ingest_paper(db, forum_id)
    except Exception as exc:  # openreview-py raises bare Exceptions for 404/auth
        raise HTTPException(
            status_code=502,
            detail=f"OpenReview fetch failed for {forum_id!r}: {exc}",
        ) from exc
    return result
