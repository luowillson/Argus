from fastapi import APIRouter, HTTPException, Query

from app.deps import CurrentUserDep, DbSession
from app.schemas.pathway import (
    LearningPathwayOut,
    LocalExploreOrderRequest,
    LocalExploreOrderResponse,
    TopicPathwayRequest,
)
from app.services.pathways import (
    build_learning_pathway_out,
    generate_explore_path,
    generate_pathway_from_paper,
    generate_pathway_from_topic,
    order_local_explore_candidates,
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


@router.post("/explore", response_model=LearningPathwayOut)
def create_explore_path(
    req: TopicPathwayRequest,
    db: DbSession,
    user: CurrentUserDep,
    force: bool = Query(default=False),
) -> LearningPathwayOut:
    try:
        return generate_explore_path(
            db,
            topic=req.topic,
            user_id=user.id,
            force=force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/explore/order", response_model=LocalExploreOrderResponse)
def order_local_explore_path(req: LocalExploreOrderRequest) -> LocalExploreOrderResponse:
    try:
        ordered, model = order_local_explore_candidates(
            topic=req.topic,
            candidates=[
                {
                    "paper_id": candidate.paper_id,
                    "title": candidate.title,
                    "stage": candidate.stage,
                    "year": candidate.year,
                    "veros_score": candidate.veros_score,
                    "tldr": candidate.tldr,
                    "anchor_concepts": candidate.anchor_concepts,
                }
                for candidate in req.candidates
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Gemini ordering unavailable") from exc

    return LocalExploreOrderResponse(
        rationale=ordered.rationale,
        items=[
            {
                "paper_id": item.paper_id,
                "learning_step": item.learning_step,
                "why_now": item.why_now,
            }
            for item in ordered.items
        ],
        model=model,
    )
