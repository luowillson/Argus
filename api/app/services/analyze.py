"""Analyze pipeline: load paper + reviews → call LLM → upsert ai_insights.

The deterministic Veros Score (M4) does not depend on this step. If the LLM
call fails or its output cannot be parsed, the paper still has a valid score —
the AI insight fields just stay null until a successful re-run.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import AIInsight, Paper, Review
from app.services.llm.factory import make_llm_provider
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from app.services.paper_view import _short_handle

logger = logging.getLogger(__name__)


VerdictLabel = Literal[
    "Strong Accept", "Accept", "Weak Accept", "Borderline", "Reject"
]


class _Dimensions(BaseModel):
    novelty: int = Field(ge=0, le=100)
    technical: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    impact: int = Field(ge=0, le=100)


class _Voice(BaseModel):
    handle: str
    rating: int = Field(ge=0, le=10)
    label: VerdictLabel
    quote: str  # length-trimmed below; LLMs routinely overshoot the 220-char ask


class LLMInsightOut(BaseModel):
    """Strict shape we require from the LLM. Anything else is a parse failure."""

    tldr: str = Field(min_length=10, max_length=1500)
    deep: list[str] = Field(min_length=1, max_length=8)
    skim: list[str] = Field(default_factory=list, max_length=8)
    dimensions: _Dimensions
    reviewer_voices: list[_Voice] = Field(default_factory=list)
    consensus_note: str = Field(default="", max_length=280)


def _clean_llm_json(text: str) -> str:
    """Robustly extract a JSON object from messy LLM output.

    Handles: code fences (```json / ``` / ~~~), leading prose, trailing prose,
    trailing commas before } or ], and JS-style // line comments.
    """
    import re

    text = text.strip()

    # Strip outer code fences: ```json ... ``` or ~~~ ... ~~~
    fence_re = re.compile(r"^(?:```[a-zA-Z]*|~~~[a-zA-Z]*)\s*\n(.*?)(?:```|~~~)\s*$", re.DOTALL)
    m = fence_re.match(text)
    if m:
        text = m.group(1).strip()

    # Find the first { and extract to its matching closing }
    start = text.find("{")
    if start != -1:
        depth = 0
        in_str = False
        esc = False
        for i, ch in enumerate(text[start:], start=start):
            if esc:
                esc = False
                continue
            if ch == "\\" and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    text = text[start : i + 1]
                    break
        else:
            text = text[start:]  # truncated — pass through and let json.loads error

    # Remove JS-style // line comments (outside strings — best-effort regex)
    text = re.sub(r"//[^\n\"]*\n", "\n", text)

    # Remove trailing commas before ] or } (common Gemma artifact)
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text.strip()


def _build_review_inputs(reviews: list[Review]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in reviews:
        items.append(
            {
                "handle": _short_handle(row.signatures),
                "rating": float(row.rating) if row.rating is not None else None,
                "confidence": float(row.confidence) if row.confidence is not None else None,
                "content": row.content or {},
            }
        )
    return items


class AnalyzeError(RuntimeError):
    """Raised when the paper has too little content to ground an LLM analysis."""


def analyze_paper(db: Session, paper_id: str, *, force: bool = False) -> AIInsight:
    """Run the LLM step and persist `ai_insights` for this paper.

    When ``force`` is False, if a row already exists in ``ai_insights`` for
    this paper, it is returned and the LLM is not called. Use
    ``force=True`` (e.g. ``POST /papers/{id}/analyze``) to re-run inference.
    """
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise AnalyzeError(f"paper {paper_id!r} not in DB; ingest first")

    rows = db.exec(
        select(Review).where(Review.paper_id == paper_id).order_by(Review.created_at)
    ).all()
    if len(rows) < 2:
        raise AnalyzeError(
            f"paper {paper_id!r} has only {len(rows)} reviews; need >= 2 to analyze"
        )

    if not force:
        existing = db.get(AIInsight, paper_id)
        if existing is not None:
            logger.info(
                "analyze_paper: skipping LLM, using existing ai_insights for %s",
                paper_id,
            )
            return existing

    reviews_for_prompt = _build_review_inputs(rows)
    user_prompt = build_user_prompt(
        title=paper.title,
        authors=paper.authors,
        venue=paper.venue,
        abstract=paper.abstract,
        reviews=reviews_for_prompt,
    )

    provider = make_llm_provider()
    response = provider.complete_json(
        system=SYSTEM_PROMPT, user=user_prompt, max_output_tokens=4000
    )

    raw_text = _clean_llm_json(response.text)
    try:
        parsed_json = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error(
            "LLM returned non-JSON for %s: %s\n--- raw (first 800 chars) ---\n%s",
            paper_id,
            exc,
            response.text[:800],
        )
        raise AnalyzeError(f"LLM returned invalid JSON: {exc}") from exc

    try:
        insight = LLMInsightOut.model_validate(parsed_json)
    except ValidationError as exc:
        logger.error(
            "LLM JSON failed schema for %s: %s\nparsed keys: %s",
            paper_id,
            exc,
            list(parsed_json.keys()) if isinstance(parsed_json, dict) else type(parsed_json),
        )
        raise AnalyzeError(f"LLM JSON failed schema: {exc}") from exc

    consensus_text = " · ".join(v.label for v in insight.reviewer_voices) or insight.consensus_note

    voices_jsonable = []
    for v in insight.reviewer_voices:
        dumped = v.model_dump()
        quote = dumped["quote"]
        if len(quote) > 240:
            dumped["quote"] = quote[:237].rstrip() + "…"
        voices_jsonable.append(dumped)

    stmt = insert(AIInsight).values(
        paper_id=paper_id,
        tldr=insight.tldr,
        deep=insight.deep,
        skim=insight.skim,
        reviewer_voices=voices_jsonable,
        novelty=insight.dimensions.novelty,
        technical=insight.dimensions.technical,
        clarity=insight.dimensions.clarity,
        impact=insight.dimensions.impact,
        consensus=consensus_text,
        model=response.model,
        prompt_version=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AIInsight.__table__.c.paper_id],
        set_={
            "tldr": stmt.excluded.tldr,
            "deep": stmt.excluded.deep,
            "skim": stmt.excluded.skim,
            "reviewer_voices": stmt.excluded.reviewer_voices,
            "novelty": stmt.excluded.novelty,
            "technical": stmt.excluded.technical,
            "clarity": stmt.excluded.clarity,
            "impact": stmt.excluded.impact,
            "consensus": stmt.excluded.consensus,
            "model": stmt.excluded.model,
            "prompt_version": stmt.excluded.prompt_version,
            "generated_at": stmt.excluded.generated_at,
        },
    )
    db.exec(stmt)

    paper.analyzed_at = datetime.now(tz=UTC)
    db.add(paper)
    db.commit()

    settings = get_settings()
    logger.info(
        "analyzed paper %s with %s (in=%s out=%s); provider=%s",
        paper_id,
        response.model,
        response.input_tokens,
        response.output_tokens,
        settings.llm_provider,
    )

    refreshed = db.get(AIInsight, paper_id)
    assert refreshed is not None
    return refreshed
