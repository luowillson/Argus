from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.db.models import AIInsight, Paper, SavedPaper, VerosScore
from app.deps import CurrentUserDep, DbSession
from app.schemas.paper import PaperOut
from app.services.search import build_paper_out

router = APIRouter(prefix="/saved", tags=["saved"])


class SaveRequest(BaseModel):
    paper_id: str


@router.get("", response_model=list[PaperOut])
def list_saved(db: DbSession, user: CurrentUserDep) -> list[PaperOut]:
    rows = db.exec(
        select(SavedPaper)
        .where(SavedPaper.user_id == user.id)
        .order_by(SavedPaper.saved_at.desc())  # type: ignore[attr-defined]
    ).all()

    paper_ids = [r.paper_id for r in rows]
    if not paper_ids:
        return []

    papers = {
        p.id: p
        for p in db.exec(select(Paper).where(Paper.id.in_(paper_ids))).all()
    }
    scores = {
        s.paper_id: s
        for s in db.exec(
            select(VerosScore).where(VerosScore.paper_id.in_(paper_ids))
        ).all()
    }
    insights = {
        i.paper_id: i
        for i in db.exec(
            select(AIInsight).where(AIInsight.paper_id.in_(paper_ids))
        ).all()
    }

    return [
        build_paper_out(papers[pid], scores.get(pid), insights.get(pid))
        for pid in paper_ids
        if pid in papers
    ]


@router.get("/{paper_id}", response_model=dict)
def get_saved_status(paper_id: str, db: DbSession, user: CurrentUserDep) -> dict:
    row = db.exec(
        select(SavedPaper).where(
            SavedPaper.user_id == user.id, SavedPaper.paper_id == paper_id
        )
    ).first()
    return {"paper_id": paper_id, "saved": row is not None}


@router.post("", response_model=dict)
def save_paper(req: SaveRequest, db: DbSession, user: CurrentUserDep) -> dict:
    if db.get(Paper, req.paper_id) is None:
        raise HTTPException(status_code=404, detail=f"paper {req.paper_id!r} not found")

    existing = db.exec(
        select(SavedPaper).where(
            SavedPaper.user_id == user.id, SavedPaper.paper_id == req.paper_id
        )
    ).first()
    if existing is None:
        db.add(SavedPaper(user_id=user.id, paper_id=req.paper_id))
        db.commit()

    return {"paper_id": req.paper_id, "saved": True}


@router.delete("/{paper_id}", response_model=dict)
def unsave_paper(paper_id: str, db: DbSession, user: CurrentUserDep) -> dict:
    row = db.exec(
        select(SavedPaper).where(
            SavedPaper.user_id == user.id, SavedPaper.paper_id == paper_id
        )
    ).first()
    if row:
        db.delete(row)
        db.commit()
    return {"paper_id": paper_id, "saved": False}
