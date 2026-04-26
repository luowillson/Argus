from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.db.models import Paper
from app.deps import DbSession
from app.schemas.paper import PaperDetail, PaperStatus
from app.services.analyze import AnalyzeError, analyze_paper
from app.services.ingest import ingest_paper
from app.services.ingest_failures import get_ingest_failure
from app.services.openreview_client import parse_forum_id
from app.services.paper_view import build_paper_detail

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/{paper_id}/status", response_model=PaperStatus)
def get_status(paper_id: str, db: DbSession) -> PaperStatus:
    """Return ingest + analysis status without the full paper payload."""
    forum_id = parse_forum_id(paper_id)
    paper = db.get(Paper, forum_id)
    if paper is None:
        if get_ingest_failure(db, forum_id) is not None:
            return PaperStatus(paper_id=forum_id, ingest="failed", analysis="failed")
        return PaperStatus(paper_id=forum_id, ingest="queued", analysis="pending")
    analysis: str = "ready" if paper.analyzed_at is not None else "pending"
    return PaperStatus(paper_id=forum_id, ingest="ready", analysis=analysis)  # type: ignore[arg-type]


@router.get("/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: str, db: DbSession) -> PaperDetail | JSONResponse:
    """Return a fully assembled PaperDetail.

    If the paper is not yet in the DB, enqueue a background ingest and return
    202 so the client can poll /status every 2 s.
    """
    forum_id = parse_forum_id(paper_id)

    paper = db.get(Paper, forum_id)
    if paper is None:
        if get_ingest_failure(db, forum_id) is not None:
            return JSONResponse(
                status_code=410,
                content={"status": "failed", "paper_id": forum_id},
            )

        from app.workers.tasks import ingest_paper_task  # late import

        ingest_paper_task.delay(forum_id)
        return JSONResponse(
            status_code=202,
            content={"status": "queued", "paper_id": forum_id},
        )

    detail = build_paper_detail(db, forum_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id!r} not found")
    return detail


@router.post("/{paper_id}/analyze")
def analyze(paper_id: str, db: DbSession) -> dict[str, object]:
    """Re-run the LLM analysis for an already-ingested paper."""
    forum_id = parse_forum_id(paper_id)
    try:
        insight = analyze_paper(db, forum_id, force=True)
    except AnalyzeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM call failed: {exc}"
        ) from exc
    return {
        "paper_id": forum_id,
        "model": insight.model,
        "tldr_chars": len(insight.tldr),
        "deep_count": len(insight.deep),
        "skim_count": len(insight.skim),
        "dimensions": {
            "novelty": insight.novelty,
            "technical": insight.technical,
            "clarity": insight.clarity,
            "impact": insight.impact,
        },
    }


@router.post("/{paper_id}/ingest")
def ingest(paper_id: str, db: DbSession) -> dict[str, object]:
    """Synchronously fetch a paper + reviews from OpenReview and persist.

    Accepts either a raw forum id or a forum URL (URL-encoded).
    """
    forum_id = parse_forum_id(paper_id)
    failure = get_ingest_failure(db, forum_id)
    if failure is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"OpenReview ingest already failed for {forum_id!r} after "
                f"{failure.attempts} attempts: {failure.error}"
            ),
        )
    try:
        result = ingest_paper(db, forum_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenReview fetch failed for {forum_id!r}: {exc}",
        ) from exc
    return result
