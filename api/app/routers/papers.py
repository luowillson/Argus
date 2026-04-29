from typing import Literal
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.models import Paper
from app.deps import DbSession
from app.schemas.citation import CitationGraph
from app.schemas.paper import PaperDetail, PaperOut, PaperStatus
from app.services.analyze import AnalyzeError, analyze_paper
from app.services.ingest import ingest_paper
from app.services.ingest_failures import get_ingest_failure
from app.services.openreview_client import parse_forum_id
from app.services.paper_view import build_paper_detail
from app.services.search import build_results_for_ids
from app.services.citations import build_citation_graph, enrich_paper_citations

router = APIRouter(prefix="/papers", tags=["papers"])

# Cache-Control for analyzed papers. Edge/CDN can serve repeats nearly free
# while the worker keeps freshness on its own schedule.
_PAPER_CACHE_HEADER = "public, max-age=300, stale-while-revalidate=86400"


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


class PapersBatchRequest(BaseModel):
    ids: list[str]


@router.post("/batch", response_model=list[PaperOut])
def get_papers_batch(req: PapersBatchRequest, db: DbSession) -> list[PaperOut]:
    """Fetch many papers by id in one query. Used by the saved/reading-list page."""
    if not req.ids:
        return []
    if len(req.ids) > 200:
        raise HTTPException(status_code=400, detail="batch size too large (max 200)")
    forum_ids = [parse_forum_id(pid) for pid in req.ids]
    return build_results_for_ids(db, forum_ids)


@router.get("/{paper_id}/citations", response_model=CitationGraph)
def get_citations(
    paper_id: str,
    db: DbSession,
    direction: Literal["references"] = Query(default="references"),
    limit: int = Query(default=60, ge=1, le=200),
) -> CitationGraph:
    resolved_id = parse_forum_id(paper_id)
    try:
        return build_citation_graph(db, resolved_id, direction=direction, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{paper_id}/citations/enrich")
def enrich_citations(
    paper_id: str,
    db: DbSession,
    sync: bool = Query(default=False),
) -> dict[str, object]:
    resolved_id = parse_forum_id(paper_id)
    if db.get(Paper, resolved_id) is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id!r} not found")
    if sync:
        try:
            return enrich_paper_citations(db, resolved_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Citation enrichment failed: {exc}") from exc

    from app.workers.tasks import enrich_citations_task  # noqa: PLC0415

    paper = db.get(Paper, resolved_id)
    assert paper is not None
    metadata = dict(paper.citation_metadata or {})
    metadata.pop("error", None)
    metadata["last_queued_at"] = datetime.now(tz=UTC).isoformat()
    paper.citation_metadata = metadata
    db.add(paper)
    db.commit()
    enrich_citations_task.delay(resolved_id)
    return {"paper_id": resolved_id, "status": "queued"}


@router.get("/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: str, db: DbSession, response: Response) -> PaperDetail | JSONResponse:
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

        from app.workers.tasks import ingest_paper_task  # noqa: PLC0415  late import

        ingest_paper_task.delay(forum_id)
        return JSONResponse(
            status_code=202,
            content={"status": "queued", "paper_id": forum_id},
        )

    detail = build_paper_detail(db, forum_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id!r} not found")

    if detail.status == "ready":
        response.headers["Cache-Control"] = _PAPER_CACHE_HEADER
    else:
        response.headers["Cache-Control"] = "no-store"
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
    from app.workers.tasks import embed_paper_task, enrich_citations_task  # noqa: PLC0415

    embed_paper_task.delay(forum_id)
    enrich_citations_task.delay(forum_id)
    return result
