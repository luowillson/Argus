from fastapi import APIRouter, Query

from app.deps import DbSession
from app.schemas.paper import PaperOut
from app.services.search import search_papers

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[PaperOut])
def search(
    db: DbSession,
    q: str = Query(default="", description="Search query — title keywords or semantic text"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PaperOut]:
    """Search ingested papers by title/abstract text and semantic similarity."""
    return search_papers(db, q, limit=limit, offset=offset)
