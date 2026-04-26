from fastapi import APIRouter, HTTPException, Query

from app.deps import CurrentUserDep, DbSession
from app.schemas.pathway import LearningPathwayOut, TopicPathwayRequest
from app.services.pathways import (
    build_learning_pathway_out,
    generate_pathway_from_paper,
    generate_pathway_from_topic,
)

router = APIRouter(prefix="/pathways", tags=["pathways"])


@router.get("/{pathway_id}", response_model=LearningPathwayOut)
def get_pathway(pathway_id: str, db: DbSession) -> LearningPathwayOut:
    pathway = build_learning_pathway_out(db, pathway_id)
    if pathway is None:
        raise HTTPException(status_code=404, detail=f"pathway {pathway_id!r} not found")
    return pathway


@router.post("/from-paper/{paper_id}", response_model=LearningPathwayOut)
def create_pathway_from_paper(
    paper_id: str,
    db: DbSession,
    user: CurrentUserDep,
    limit: int = Query(default=8, ge=3, le=12),
    force: bool = Query(default=False),
) -> LearningPathwayOut:
    try:
        return generate_pathway_from_paper(
            db,
            paper_id=paper_id,
            user_id=user.id,
            limit=limit,
            force=force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/from-topic", response_model=LearningPathwayOut)
def create_pathway_from_topic(
    req: TopicPathwayRequest,
    db: DbSession,
    user: CurrentUserDep,
    force: bool = Query(default=False),
) -> LearningPathwayOut:
    try:
        return generate_pathway_from_topic(
            db,
            topic=req.topic,
            user_id=user.id,
            limit=req.limit,
            force=force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
