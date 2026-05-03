from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import text as sa_text
from sqlmodel import Session

RankingOrder = Literal["best", "worst"]
_CACHE_TTL = timedelta(minutes=10)
_cached_rankings: list[AuthorRanking] | None = None
_cached_at: datetime | None = None


@dataclass(frozen=True)
class AuthorRanking:
    author: str
    paper_count: int
    average_score: float
    top_paper_id: str | None
    top_paper_title: str | None
    top_score: float | None
    lowest_paper_id: str | None
    lowest_paper_title: str | None
    lowest_score: float | None


@dataclass(frozen=True)
class PaperCitationRanking:
    paper_id: str
    title: str
    authors: str
    venue: str | None
    year: int | None
    citations: int | None
    pagerank: float
    citation_in_degree: int
    citation_out_degree: int
    computed_at: datetime


def _build_author_rankings(db: Session) -> list[AuthorRanking]:
    rows = db.execute(
        sa_text(
            """
            WITH authored AS (
              SELECT
                btrim(author_name) AS author,
                p.id AS paper_id,
                p.title AS paper_title,
                s.score::float AS score
              FROM papers p
              JOIN veros_scores s ON s.paper_id = p.id
              CROSS JOIN LATERAL unnest(p.authors) AS author_name
              WHERE btrim(author_name) <> ''
            ),
            stats AS (
              SELECT
                author,
                COUNT(*) AS paper_count,
                AVG(score) AS average_score
              FROM authored
              GROUP BY author
            ),
            top_papers AS (
              SELECT DISTINCT ON (author)
                author,
                paper_id AS top_paper_id,
                paper_title AS top_paper_title,
                score AS top_score
              FROM authored
              ORDER BY author, score DESC, paper_title ASC
            ),
            lowest_papers AS (
              SELECT DISTINCT ON (author)
                author,
                paper_id AS lowest_paper_id,
                paper_title AS lowest_paper_title,
                score AS lowest_score
              FROM authored
              ORDER BY author, score ASC, paper_title ASC
            )
            SELECT
              stats.author,
              stats.paper_count,
              stats.average_score,
              top_papers.top_paper_id,
              top_papers.top_paper_title,
              top_papers.top_score,
              lowest_papers.lowest_paper_id,
              lowest_papers.lowest_paper_title,
              lowest_papers.lowest_score
            FROM stats
            JOIN top_papers ON top_papers.author = stats.author
            JOIN lowest_papers ON lowest_papers.author = stats.author
            """
        )
    ).fetchall()

    return [
            AuthorRanking(
                author=str(row.author),
                paper_count=int(row.paper_count),
                average_score=round(float(row.average_score), 2),
                top_paper_id=str(row.top_paper_id),
                top_paper_title=str(row.top_paper_title),
                top_score=round(float(row.top_score), 1),
                lowest_paper_id=str(row.lowest_paper_id),
                lowest_paper_title=str(row.lowest_paper_title),
                lowest_score=round(float(row.lowest_score), 1),
            )
        for row in rows
    ]


def _all_author_rankings(db: Session) -> list[AuthorRanking]:
    global _cached_at, _cached_rankings

    now = datetime.now(UTC)
    if _cached_rankings is not None and _cached_at is not None and now - _cached_at < _CACHE_TTL:
        return _cached_rankings

    _cached_rankings = _build_author_rankings(db)
    _cached_at = now
    return _cached_rankings


def author_rankings(
    db: Session,
    *,
    min_papers: int = 3,
    limit: int | None = None,
    order: RankingOrder = "best",
    query: str = "",
) -> list[AuthorRanking]:
    normalized_query = query.strip().lower()
    rankings = [
        ranking
        for ranking in _all_author_rankings(db)
        if ranking.paper_count >= min_papers
        and (not normalized_query or normalized_query in ranking.author.lower())
    ]

    if order == "worst":
        rankings.sort(
            key=lambda ranking: (
                ranking.average_score,
                -ranking.paper_count,
                ranking.author.lower(),
            )
        )
    else:
        rankings.sort(
            key=lambda ranking: (
                -ranking.average_score,
                -ranking.paper_count,
                ranking.author.lower(),
            )
        )
    return rankings[:limit] if limit is not None else rankings


def paper_citation_rankings(
    db: Session,
    *,
    limit: int = 100,
    query: str = "",
) -> list[PaperCitationRanking]:
    normalized_query = query.strip()
    like = f"%{normalized_query}%"
    rows = db.execute(
        sa_text(
            """
            SELECT
              p.id AS paper_id,
              p.title,
              p.authors,
              p.venue,
              p.year,
              p.citations,
              m.pagerank::float AS pagerank,
              m.in_degree,
              m.out_degree,
              m.computed_at
            FROM paper_graph_metrics m
            JOIN papers p ON p.id = m.paper_id
            WHERE
              :q = ''
              OR p.title ILIKE :like
              OR EXISTS (
                SELECT 1
                FROM unnest(p.authors) AS author_name
                WHERE author_name ILIKE :like
              )
            ORDER BY
              m.pagerank DESC,
              m.in_degree DESC,
              p.citations DESC NULLS LAST,
              p.title ASC
            LIMIT :limit
            """
        ),
        {"q": normalized_query, "like": like, "limit": limit},
    ).fetchall()

    return [
        PaperCitationRanking(
            paper_id=str(row.paper_id),
            title=str(row.title),
            authors=", ".join(row.authors or []) or "Unknown",
            venue=row.venue,
            year=row.year,
            citations=row.citations,
            pagerank=float(row.pagerank),
            citation_in_degree=int(row.in_degree),
            citation_out_degree=int(row.out_degree),
            computed_at=row.computed_at,
        )
        for row in rows
    ]
