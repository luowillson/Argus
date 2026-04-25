"""Assemble a `PaperDetail` for the GET /papers/{id} endpoint.

For M4 the per-dimension scores and the AI insight fields (tldr/deep/skim) come
back as None — M5 fills them in once the LLM step runs. Reviewer voices are
derived directly from raw review rows so the UI can show real reviewer text
even before the LLM has selected the best quotes.
"""

from __future__ import annotations

from typing import cast, get_args

from sqlmodel import Session, select

from app.db.models import AIInsight, Paper, Review, VerosScore
from app.schemas.paper import PaperDetail, ReviewerVoice, Verdict
from app.services.dimensions import standardized_dimensions

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


def _coerce_label(value: str | None) -> Verdict:
    """Map an OpenReview recommendation string to one of our Verdict labels."""
    if not value:
        return "Borderline"
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
    return "Borderline"


def _quote_from_content(content: dict) -> str:
    """Pick a short, useful sentence from raw review content for display."""
    for key in ("strengths", "summary", "review", "weaknesses"):
        text = content.get(key)
        if isinstance(text, str) and text.strip():
            sentence = text.strip().split(". ")[0]
            return (sentence[:240] + "…") if len(sentence) > 240 else sentence
    return ""


def build_paper_detail(db: Session, paper_id: str) -> PaperDetail | None:
    paper = db.get(Paper, paper_id)
    if paper is None:
        return None

    score_row = db.get(VerosScore, paper_id)
    insight = db.get(AIInsight, paper_id)
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

    # Prefer LLM-picked verbatim quotes when ai_insights is ready; fall back to
    # the raw-content heuristic so the page still has voices pre-LLM.
    llm_quotes_by_handle: dict[str, dict] = {}
    if insight and insight.reviewer_voices:
        for v in insight.reviewer_voices:
            handle = v.get("handle") if isinstance(v, dict) else None
            if isinstance(handle, str):
                llm_quotes_by_handle[handle] = v

    for row in review_rows:
        if row.rating is None:
            continue
        handle = _short_handle(row.signatures)
        label = _coerce_label(row.recommendation)
        consensus_labels.append(label)
        llm_voice = llm_quotes_by_handle.get(handle)
        quote = (
            llm_voice.get("quote", "")
            if llm_voice
            else _quote_from_content(row.content or {})
        )
        reviewers.append(
            ReviewerVoice(
                handle=handle,
                rating=int(round(float(row.rating))),
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
        status=status,
    )
