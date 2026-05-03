from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.db.models import Paper, SavedPaper
from app.deps import CurrentUserDep, DbSession
from app.schemas.paper import PaperOut
from app.services.search import build_results_for_ids

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

    return build_results_for_ids(db, paper_ids)


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
