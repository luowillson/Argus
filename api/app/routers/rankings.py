from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.deps import DbSession
from app.services.rankings import author_rankings, paper_citation_rankings

router = APIRouter(prefix="/rankings", tags=["rankings"])


class AuthorRankingOut(BaseModel):
    author: str
    paper_count: int
    average_score: float
    top_paper_id: str | None
    top_paper_title: str | None
    top_score: float | None
    lowest_paper_id: str | None
    lowest_paper_title: str | None
    lowest_score: float | None


class PaperCitationRankingOut(BaseModel):
    paper_id: str
    title: str
    authors: str
    venue: str | None
    year: int | None
    citations: int | None
    pagerank: float
    citation_in_degree: int
    citation_out_degree: int
    computed_at: str


@router.get("/authors", response_model=list[AuthorRankingOut])
def ranked_authors(
    db: DbSession,
    min_papers: int = Query(default=3, ge=1, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    q: str = Query(default="", description="Optional author name filter"),
    order: Literal["best", "worst"] = Query(
        default="best",
        description="best ranks by highest average score; worst ranks by lowest average score",
    ),
) -> list[AuthorRankingOut]:
    """Rank authors by average Veros Score across scored papers."""
    effective_min_papers = 1 if q.strip() else min_papers
    return [
        AuthorRankingOut(**ranking.__dict__)
        for ranking in author_rankings(
            db,
            min_papers=effective_min_papers,
            limit=limit,
            order=order,
            query=q,
        )
    ]


@router.get("/papers/citations", response_model=list[PaperCitationRankingOut])
def ranked_papers_by_citation_graph(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
    q: str = Query(default="", description="Optional title or author filter"),
) -> list[PaperCitationRankingOut]:
    """Rank papers by persisted citation-graph PageRank."""
    return [
        PaperCitationRankingOut(
            **{
                **ranking.__dict__,
                "computed_at": ranking.computed_at.isoformat(),
            }
        )
        for ranking in paper_citation_rankings(db, limit=limit, query=q)
    ]
