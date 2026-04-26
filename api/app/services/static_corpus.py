from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import text
from sqlmodel import Session, select

from app.db.models import AIInsight, Paper, Review, VerosScore
from app.schemas.paper import PaperDetail, ReviewerVoice, Verdict
from app.services.dimensions import standardized_dimensions
from app.services.paper_view import _coerce_label, _quote_from_content, _short_handle
from app.services.scoring import normalize_rating_to_ten, rating_scale_max_for_paper


def _latest_datetime(*values: datetime | None) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _version_string(
    paper_count: int,
    review_count: int,
    score_count: int,
    insight_count: int,
    latest_at: datetime | None,
) -> str:
    latest = latest_at.isoformat() if latest_at is not None else "empty"
    return f"p{paper_count}:r{review_count}:s{score_count}:i{insight_count}:t{latest}"


def build_detail_from_rows(
    paper: Paper,
    score_row: VerosScore | None,
    insight: AIInsight | None,
    reviews: list[Review],
) -> PaperDetail:
    consensus_strength = "split"
    breakdown_dict: dict[str, object] | None = None
    if score_row is not None:
        breakdown_dict = dict(score_row.breakdown or {})
        cs = breakdown_dict.get("consensus_strength")
        if cs in {"strong", "moderate", "mixed", "split"}:
            consensus_strength = str(cs)

    llm_quotes_by_handle: dict[str, dict] = {}
    if insight and insight.reviewer_voices:
        for voice in insight.reviewer_voices:
            handle = voice.get("handle") if isinstance(voice, dict) else None
            if isinstance(handle, str):
                llm_quotes_by_handle[handle] = voice

    reviewers: list[ReviewerVoice] = []
    consensus_labels: list[str] = []
    rating_scale_max = rating_scale_max_for_paper(paper)
    for review in reviews:
        if review.rating is None:
            continue
        handle = _short_handle(review.signatures)
        normalized_rating = normalize_rating_to_ten(float(review.rating), rating_scale_max)
        label = _coerce_label(review.recommendation, normalized_rating)
        consensus_labels.append(label)
        llm_voice = llm_quotes_by_handle.get(handle)
        quote = (
            str(llm_voice.get("quote", ""))
            if llm_voice
            else _quote_from_content(review.content or {})
        )
        reviewers.append(
            ReviewerVoice(
                handle=handle,
                rating=normalized_rating,
                rating_scale_max=10,
                label=label,
                quote=quote,
            )
        )

    if insight:
        status = "ready"
    elif score_row:
        status = "score_only"
    else:
        status = "ingested_no_score"

    dimensions = standardized_dimensions(score_row, insight)
    return PaperDetail(
        id=paper.id,
        title=paper.title,
        authors=", ".join(paper.authors) if paper.authors else "Unknown",
        venue=paper.venue,
        citations=paper.citations,
        openreview_url=paper.openreview_url,
        acceptance=paper.acceptance,
        score=float(score_row.score) if score_row else None,
        grade=score_row.grade if score_row else "—",
        verdict=cast(Verdict, score_row.verdict) if score_row else "Insufficient reviews",
        consensus_strength=consensus_strength,  # type: ignore[arg-type]
        reviewer_count=len(reviewers),
        novelty=dimensions["novelty"],
        technical=dimensions["technical"],
        clarity=dimensions["clarity"],
        impact=dimensions["impact"],
        tldr=insight.tldr if insight else None,
        deep=list(insight.deep) if insight else [],
        skim=list(insight.skim) if insight else [],
        reviewers=reviewers,
        consensus=" · ".join(consensus_labels) if consensus_labels else None,
        score_breakdown=breakdown_dict,
        status=status,  # type: ignore[arg-type]
    )


def build_static_corpus_payload(db: Session) -> dict[str, object]:
    paper_rows = db.exec(select(Paper).order_by(Paper.created_at.desc())).all()
    scores = {row.paper_id: row for row in db.exec(select(VerosScore)).all()}
    insights = {row.paper_id: row for row in db.exec(select(AIInsight)).all()}
    reviews_by_paper: dict[str, list[Review]] = defaultdict(list)
    review_rows = db.exec(select(Review).order_by(Review.created_at)).all()
    for review in review_rows:
        reviews_by_paper[review.paper_id].append(review)

    papers = [
        build_detail_from_rows(
            paper,
            scores.get(paper.id),
            insights.get(paper.id),
            reviews_by_paper.get(paper.id, []),
        ).model_dump(mode="json")
        for paper in paper_rows
    ]

    latest_at = _latest_datetime(
        *[paper.created_at for paper in paper_rows],
        *[paper.ingested_at for paper in paper_rows],
        *[paper.analyzed_at for paper in paper_rows],
        *[review.created_at for review in review_rows],
        *[score.computed_at for score in scores.values()],
        *[insight.generated_at for insight in insights.values()],
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_version": _version_string(
            paper_count=len(papers),
            review_count=len(review_rows),
            score_count=len(scores),
            insight_count=len(insights),
            latest_at=latest_at,
        ),
        "corpus_cursor": latest_at.isoformat() if latest_at is not None else None,
        "paper_count": len(papers),
        "papers": papers,
    }


def get_static_corpus_version(db: Session) -> dict[str, object]:
    row = db.execute(
        text(
            """
            WITH
              p AS (
                SELECT
                  COUNT(*) AS count,
                  MAX(GREATEST(
                    COALESCE(created_at, TIMESTAMPTZ 'epoch'),
                    COALESCE(ingested_at, TIMESTAMPTZ 'epoch'),
                    COALESCE(analyzed_at, TIMESTAMPTZ 'epoch')
                  )) AS latest_at
                FROM papers
              ),
              r AS (
                SELECT COUNT(*) AS count, MAX(created_at) AS latest_at FROM reviews
              ),
              s AS (
                SELECT COUNT(*) AS count, MAX(computed_at) AS latest_at FROM veros_scores
              ),
              i AS (
                SELECT COUNT(*) AS count, MAX(generated_at) AS latest_at FROM ai_insights
              )
            SELECT
              p.count AS paper_count,
              r.count AS review_count,
              s.count AS score_count,
              i.count AS insight_count,
              GREATEST(
                COALESCE(p.latest_at, TIMESTAMPTZ 'epoch'),
                COALESCE(r.latest_at, TIMESTAMPTZ 'epoch'),
                COALESCE(s.latest_at, TIMESTAMPTZ 'epoch'),
                COALESCE(i.latest_at, TIMESTAMPTZ 'epoch')
              ) AS latest_at
            FROM p, r, s, i
            """
        )
    ).first()

    if row is None:
        return {
            "corpus_version": _version_string(0, 0, 0, 0, None),
            "paper_count": 0,
            "latest_at": None,
        }

    latest_at = row.latest_at if row.latest_at and row.latest_at.timestamp() > 0 else None
    return {
        "corpus_version": _version_string(
            paper_count=int(row.paper_count or 0),
            review_count=int(row.review_count or 0),
            score_count=int(row.score_count or 0),
            insight_count=int(row.insight_count or 0),
            latest_at=latest_at,
        ),
        "paper_count": int(row.paper_count or 0),
        "latest_at": latest_at.isoformat() if latest_at is not None else None,
    }


def build_static_corpus_changes_payload(
    db: Session,
    since: datetime,
) -> dict[str, object]:
    version = get_static_corpus_version(db)
    rows = db.execute(
        text(
            """
            SELECT id FROM papers
            WHERE GREATEST(
              COALESCE(created_at, TIMESTAMPTZ 'epoch'),
              COALESCE(ingested_at, TIMESTAMPTZ 'epoch'),
              COALESCE(analyzed_at, TIMESTAMPTZ 'epoch')
            ) > :since
            UNION
            SELECT paper_id FROM reviews WHERE created_at > :since
            UNION
            SELECT paper_id FROM veros_scores WHERE computed_at > :since
            UNION
            SELECT paper_id FROM ai_insights WHERE generated_at > :since
            """
        ),
        {"since": since},
    ).fetchall()
    paper_ids = [str(row[0]) for row in rows]

    if not paper_ids:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "corpus_version": version["corpus_version"],
            "corpus_cursor": version["latest_at"],
            "paper_count": version["paper_count"],
            "papers": [],
            "deleted_ids": [],
        }

    paper_rows = db.exec(
        select(Paper).where(Paper.id.in_(paper_ids)).order_by(Paper.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    scores = {
        row.paper_id: row
        for row in db.exec(select(VerosScore).where(VerosScore.paper_id.in_(paper_ids))).all()  # type: ignore[attr-defined]
    }
    insights = {
        row.paper_id: row
        for row in db.exec(select(AIInsight).where(AIInsight.paper_id.in_(paper_ids))).all()  # type: ignore[attr-defined]
    }
    reviews_by_paper: dict[str, list[Review]] = defaultdict(list)
    for review in db.exec(
        select(Review)
        .where(Review.paper_id.in_(paper_ids))  # type: ignore[attr-defined]
        .order_by(Review.created_at)
    ).all():
        reviews_by_paper[review.paper_id].append(review)

    papers = [
        build_detail_from_rows(
            paper,
            scores.get(paper.id),
            insights.get(paper.id),
            reviews_by_paper.get(paper.id, []),
        ).model_dump(mode="json")
        for paper in paper_rows
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "corpus_version": version["corpus_version"],
        "corpus_cursor": version["latest_at"],
        "paper_count": version["paper_count"],
        "papers": papers,
        "deleted_ids": [],
    }
