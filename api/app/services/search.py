"""Full-text + semantic search over ingested papers.

Strategy: combine (1) substring ILIKE with escaped wildcards, (2) pg_trgm
``word_similarity`` on title/abstract for fuzzy matching, (3) optional
per-token fuzzy ORs for multi-word queries, and (4) pgvector cosine
nearest-neighbour on query embeddings when available. De-duplicate by
paper_id, fetch scores and AI insights, sort by Veros score descending.
"""

from __future__ import annotations

import logging
import re
from typing import cast

from sqlalchemy import text as sa_text
from sqlmodel import Session, select

from app.db.models import AIInsight, Paper, VerosScore
from app.schemas.paper import ConsensusStrength, PaperOut, Verdict
from app.services.dimensions import standardized_dimensions

logger = logging.getLogger(__name__)

_CANDIDATE_POOL = 50  # max IDs per channel before re-ranking by score
_FUZZY_WORD_SIM_THRESHOLD = 0.16
_MIN_TOKEN_LEN = 3
_MAX_TOKENS = 5


def _escape_ilike(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _fuzzy_text_candidate_ids(db: Session, q: str) -> list[str]:
    """ILIKE substring + word_similarity; extra per-token rows for multi-word queries."""
    qn = q.strip()
    if not qn:
        return []

    like = f"%{_escape_ilike(qn)}%"
    out: list[str] = []
    seen: set[str] = set()

    sql = sa_text(
        """
        SELECT id FROM papers
        WHERE
          title ILIKE :like ESCAPE '\\'
          OR COALESCE(abstract, '') ILIKE :like ESCAPE '\\'
          OR word_similarity(lower(:qn), lower(title)) > :w_th
          OR word_similarity(
            lower(:qn), lower(COALESCE(abstract, ''))
          ) > :w_th
        ORDER BY
          (
            CASE
              WHEN title ILIKE :like ESCAPE '\\'
                OR COALESCE(abstract, '') ILIKE :like ESCAPE '\\'
              THEN 1
              ELSE 0
            END
          ) DESC,
          GREATEST(
            word_similarity(lower(:qn), lower(title)),
            word_similarity(
              lower(:qn), lower(COALESCE(abstract, ''))
            )
          ) DESC
        LIMIT :lim
        """
    )
    rows = db.execute(
        sql,
        {
            "like": like,
            "qn": qn,
            "w_th": _FUZZY_WORD_SIM_THRESHOLD,
            "lim": _CANDIDATE_POOL,
        },
    ).fetchall()
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r[0])

    tokens = [
        t
        for t in re.split(r"\s+", qn)
        if len(t) >= _MIN_TOKEN_LEN
    ][: _MAX_TOKENS]
    if len(tokens) > 1:
        tsql = sa_text(
            """
            SELECT id FROM papers
            WHERE
              word_similarity(lower(:tok), lower(title)) > :w_th
              OR word_similarity(
                lower(:tok), lower(COALESCE(abstract, ''))
              ) > :w_th
            ORDER BY GREATEST(
              word_similarity(lower(:tok), lower(title)),
              word_similarity(
                lower(:tok), lower(COALESCE(abstract, ''))
              )
            ) DESC
            LIMIT :lim
            """
        )
        for tok in tokens:
            if len(out) >= _CANDIDATE_POOL:
                break
            rows2 = db.execute(
                tsql,
                {
                    "tok": tok,
                    "w_th": _FUZZY_WORD_SIM_THRESHOLD,
                    "lim": min(20, _CANDIDATE_POOL),
                },
            ).fetchall()
            for r in rows2:
                if r[0] not in seen:
                    seen.add(r[0])
                    out.append(r[0])
                    if len(out) >= _CANDIDATE_POOL:
                        break

    return out


def _has_embeddings(db: Session) -> bool:
    row = db.execute(sa_text("SELECT EXISTS (SELECT 1 FROM paper_embeddings LIMIT 1)")).first()
    return bool(row and row[0])


def _browse_candidate_ids(db: Session, limit: int, offset: int) -> list[str]:
    """Return browse-page IDs ranked globally by Veros score."""
    sql = sa_text(
        """
        SELECT p.id
        FROM papers p
        LEFT JOIN veros_scores s ON s.paper_id = p.id
        ORDER BY
          s.score DESC NULLS LAST,
          p.ingested_at DESC NULLS LAST,
          p.created_at DESC
        LIMIT :lim OFFSET :off
        """
    )
    rows = db.execute(sql, {"lim": limit, "off": offset}).fetchall()
    return [r[0] for r in rows]


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
    dimensions = standardized_dimensions(score_row, insight)

    return PaperOut(
        id=paper.id,
        title=paper.title,
        authors=", ".join(paper.authors) if paper.authors else "Unknown",
        venue=paper.venue,
        acceptance=paper.acceptance,
        score=float(score_row.score) if score_row else None,
        grade=score_row.grade if score_row else "—",
        verdict=cast(Verdict, score_row.verdict) if score_row else "Insufficient reviews",
        novelty=dimensions["novelty"],
        technical=dimensions["technical"],
        clarity=dimensions["clarity"],
        impact=dimensions["impact"],
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
    candidate_ids_are_page = False

    if not q:
        candidate_ids = _browse_candidate_ids(db, limit, offset)
        candidate_ids_are_page = True
    else:
        candidate_ids.extend(_fuzzy_text_candidate_ids(db, q))

        try:
            if not _has_embeddings(db):
                raise RuntimeError("no paper embeddings indexed")

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

    seen: set[str] = set()
    unique_ids: list[str] = []
    for pid in candidate_ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)

    if not unique_ids:
        return []

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

    results = [
        build_paper_out(papers[pid], scores.get(pid), insights.get(pid))
        for pid in unique_ids
        if pid in papers
    ]
    results.sort(key=lambda x: (x.score or 0.0), reverse=True)

    if candidate_ids_are_page:
        return results

    return results[offset : offset + limit]
