from fastapi import APIRouter
from sqlalchemy import text

from app.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict[str, str]:
    db.exec(text("SELECT 1"))
    return {"status": "ok"}
