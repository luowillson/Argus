"""Full-text + semantic search over ingested papers.

Strategy: run a pg_trgm ILIKE text match on title/abstract in parallel with
a pgvector cosine nearest-neighbour lookup on paper_embeddings (when the
embedding provider is available). De-duplicate by paper_id, fetch scores
and AI insights for the candidate set, sort by Veros score descending.
"""

from __future__ import annotations

import logging
from typing import cast

from sqlalchemy import text as sa_text
from sqlmodel import Session, select

from app.db.models import AIInsight, Paper, VerosScore
from app.schemas.paper import ConsensusStrength, PaperOut, Verdict

logger = logging.getLogger(__name__)

_CANDIDATE_POOL = 40  # max IDs to collect before re-ranking by score


def build_paper_out(
    paper: Paper,
    score_row: VerosScore | None,
    insight: AIInsight | None,
) -> PaperOut:
    breakdown = dict(score_row.breakdown) if score_row else {}
    cs_raw = breakdown.get("consensus_strength", "split")
    cs: ConsensusStrength = (
        cast(ConsensusStrength, cs_raw)
        if cs_raw in {"strong", "moderate", "mixed", "split"}
        else "split"
    )
    reviewer_count = int(breakdown.get("n_reviews", 0))

    return PaperOut(
        id=paper.id,
        title=paper.title,
        authors=", ".join(paper.authors) if paper.authors else "Unknown",
        venue=paper.venue,
        acceptance=paper.acceptance,
        score=float(score_row.score) if score_row else None,
        grade=score_row.grade if score_row else "—",
        verdict=cast(Verdict, score_row.verdict) if score_row else "Insufficient reviews",
        novelty=insight.novelty if insight else None,
        technical=insight.technical if insight else None,
        clarity=insight.clarity if insight else None,
        impact=insight.impact if insight else None,
        tldr=insight.tldr if insight else None,
        consensus=insight.consensus if insight else None,
        consensus_strength=cs,
        reviewer_count=reviewer_count,
    )


def search_papers(
    db: Session,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> list[PaperOut]:
    q = query.strip()
    candidate_ids: list[str] = []

    if not q:
        # Empty query → most-recently ingested papers.
        rows = db.exec(
            select(Paper.id).order_by(Paper.ingested_at.desc()).limit(_CANDIDATE_POOL)  # type: ignore[attr-defined]
        ).all()
        candidate_ids = list(rows)
    else:
        # 1. Trigram text match on title and abstract.
        like = f"%{q}%"
        text_rows = db.exec(
            select(Paper.id)
            .where(
                Paper.title.ilike(like)  # type: ignore[attr-defined]
                | Paper.abstract.ilike(like)  # type: ignore[attr-defined]
            )
            .limit(_CANDIDATE_POOL)
        ).all()
        candidate_ids.extend(text_rows)

        # 2. Semantic vector search (best-effort — skip if provider unavailable).
        try:
            from app.services.embeddings.factory import get_embedding_provider

            provider = get_embedding_provider()
            embedding = provider.encode([q])[0]
            vec_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
            sql = sa_text(
                "SELECT paper_id FROM paper_embeddings "
                "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :n"
            )
            rows = db.execute(sql, {"vec": vec_str, "n": _CANDIDATE_POOL}).fetchall()
            candidate_ids.extend(r[0] for r in rows)
        except Exception:
            logger.debug("Vector search skipped (provider unavailable or no embeddings).")

    # 3. Deduplicate, preserving order (text matches first).
    seen: set[str] = set()
    unique_ids: list[str] = []
    for pid in candidate_ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)

    if not unique_ids:
        return []

    # 4. Bulk-fetch papers + scores + insights in three queries.
    papers = {
        p.id: p
        for p in db.exec(select(Paper).where(Paper.id.in_(unique_ids))).all()
    }
    scores = {
        s.paper_id: s
        for s in db.exec(
            select(VerosScore).where(VerosScore.paper_id.in_(unique_ids))
        ).all()
    }
    insights = {
        i.paper_id: i
        for i in db.exec(
            select(AIInsight).where(AIInsight.paper_id.in_(unique_ids))
        ).all()
    }

    # 5. Build results and sort by Veros score descending.
    results = [
        build_paper_out(papers[pid], scores.get(pid), insights.get(pid))
        for pid in unique_ids
        if pid in papers
    ]
    results.sort(key=lambda x: (x.score or 0.0), reverse=True)

    return results[offset : offset + limit]
