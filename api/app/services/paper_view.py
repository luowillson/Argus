"""Assemble a `PaperDetail` for the GET /papers/{id} endpoint.

For M4 the per-dimension scores and the AI insight fields (tldr/deep/skim) come
back as None — M5 fills them in once the LLM step runs. Reviewer voices are
derived directly from raw review rows so the UI can show real reviewer text
even before the LLM has selected the best quotes.
"""

from __future__ import annotations
from typing import cast, get_args

from sqlmodel import Session, select

from app.db.models import AIInsight, Paper, PaperGraphMetric, Review, VerosScore
from app.schemas.paper import PaperDetail, ReviewerVoice, Verdict
from app.services.citations import citation_graph_status
from app.services.dimensions import standardized_dimensions
from app.services.scoring import normalize_rating_to_ten, rating_scale_max_for_paper
from app.utils.ratings import parse_numeric, parse_recommendation

_VERDICT_VALUES = set(get_args(Verdict))


def _short_handle(signatures: list[str]) -> str:
    """Pull a 4-char handle out of a Reviewer signature like
    'ICLR.cc/2024/Conference/Submission6054/Reviewer_apJf' -> 'apJf'."""
    if not signatures:
        return "anon"
    last = signatures[0].rsplit("/", 1)[-1]
    if "_" in last:
        last = last.split("_", 1)[1]
    return last[-4:] or "anon"


def _verdict_from_rating(rating: float) -> Verdict:
    if rating >= 8.5:
        return "Strong Accept"
    if rating >= 7.0:
        return "Accept"
    if rating >= 6.0:
        return "Weak Accept"
    if rating >= 5.0:
        return "Borderline"
    return "Reject"


def _coerce_label(value: str | None, rating: float | None = None) -> Verdict:
    """Map an OpenReview recommendation string to one of our Verdict labels."""
    if not value:
        return _verdict_from_rating(rating) if rating is not None else "Borderline"
    text = value.lower()
    if "strong" in text and "accept" in text:
        return "Strong Accept"
    if "weak" in text and "accept" in text:
        return "Weak Accept"
    if "marginally above" in text or "above the acceptance" in text:
        return "Weak Accept"
    if "marginally below" in text or "below the acceptance" in text:
        return "Borderline"
    if "borderline" in text:
        return "Borderline"
    if "strong" in text and "reject" in text:
        return "Reject"
    if "reject" in text:
        return "Reject"
    if "accept" in text:
        return "Accept"
    if value in _VERDICT_VALUES:
        return cast(Verdict, value)
    return _verdict_from_rating(rating) if rating is not None else "Borderline"


def _quote_from_content(content: dict) -> str:
    """Prefer the review summary field verbatim; fall back only if needed."""
    for key in ("summary", "summary_of_the_review", "review", "strengths", "weaknesses"):
        text = content.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _review_rating(row: Review) -> float | None:
    if row.rating is not None:
        return float(row.rating)
    content = row.content or {}
    return parse_numeric(content.get("rating") or content.get("recommendation"))


def _review_recommendation(row: Review) -> str | None:
    if row.recommendation:
        return row.recommendation
    content = row.content or {}
    return parse_recommendation(content.get("recommendation") or content.get("rating"))


def build_paper_detail(db: Session, paper_id: str) -> PaperDetail | None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return None

    score_row = db.get(VerosScore, paper_id)
    insight = db.get(AIInsight, paper_id)
    graph_metric = db.get(PaperGraphMetric, paper_id)
    review_rows = db.exec(
        select(Review).where(Review.paper_id == paper_id).order_by(Review.created_at)
    ).all()

    consensus_strength = "split"
    breakdown_dict: dict[str, object] | None = None
    if score_row is not None:
        breakdown_dict = dict(score_row.breakdown or {})
        cs = breakdown_dict.get("consensus_strength")
        if cs in {"strong", "moderate", "mixed", "split"}:
            consensus_strength = cs  # type: ignore[assignment]

    reviewers: list[ReviewerVoice] = []
    consensus_labels: list[str] = []
    rating_scale_max = rating_scale_max_for_paper(paper)

    for row in review_rows:
        raw_rating = _review_rating(row)
        if raw_rating is None:
            continue
        handle = _short_handle(row.signatures)
        normalized_rating = normalize_rating_to_ten(raw_rating, rating_scale_max)
        label = _coerce_label(_review_recommendation(row), normalized_rating)
        consensus_labels.append(label)
        reviewers.append(
            ReviewerVoice(
                handle=handle,
                rating=normalized_rating,
                rating_scale_max=10,
                label=label,
                quote=_quote_from_content(row.content or {}),
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
        references_count=paper.references_count,
        citation_graph_status=citation_graph_status(paper),
        pagerank=float(graph_metric.pagerank) if graph_metric else None,
        citation_in_degree=graph_metric.in_degree if graph_metric else None,
        citation_out_degree=graph_metric.out_degree if graph_metric else None,
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
        status=status,
    )
