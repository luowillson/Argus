from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import delete, text as sa_text
from sqlmodel import Session, select

from app.db.models import (
    AIInsight,
    LearningPathway,
    LearningPathwayItem,
    Paper,
    PaperConcept,
    PaperEdge,
    PaperEmbedding,
    VerosScore,
)
from app.schemas.paper import PaperOut
from app.schemas.pathway import LearningPathwayOut, PathwayItem
from app.services.llm.factory import make_llm_provider
from app.services.openreview_client import build_client
from app.services.search import build_paper_out, search_papers

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "about",
    "above",
    "across",
    "after",
    "again",
    "against",
    "among",
    "approach",
    "based",
    "because",
    "before",
    "between",
    "beyond",
    "could",
    "dataset",
    "different",
    "during",
    "each",
    "find",
    "for",
    "from",
    "have",
    "into",
    "matters",
    "method",
    "methods",
    "model",
    "models",
    "paper",
    "results",
    "show",
    "shows",
    "study",
    "their",
    "there",
    "these",
    "this",
    "through",
    "using",
    "via",
    "with",
    "without",
}
_GENERIC_TOPIC_TERMS = {
    "analysis",
    "approach",
    "architectures",
    "architecture",
    "benchmark",
    "benchmarks",
    "framework",
    "frameworks",
    "language",
    "languages",
    "learn",
    "learning",
    "llm",
    "llms",
    "method",
    "methods",
    "model",
    "models",
    "paper",
    "reasoning",
    "results",
    "study",
    "system",
    "systems",
    "technique",
    "techniques",
    "training",
    "transformer",
    "transformers",
}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-]{2,}")
_MAX_CANDIDATES = 12
_MIN_PATHWAY_CANDIDATES = 4
_WEAK_STAGE_SCORE = 0.5
_MIN_WEAK_OR_MISSING_FOR_ENRICHMENT = 2
_MIN_STRONG_STAGES_WITHOUT_ENRICHMENT = 2
_OPENREVIEW_VENUE_HINTS = (
    "ICLR.cc/2024/Conference",
    "ICLR.cc/2025/Conference",
    "NeurIPS.cc/2024/Conference",
    "NeurIPS.cc/2025/Conference",
)

_SYSTEM_PROMPT = """You are Veros Pathways, an academic learning-path planner.

You are given a seed paper or topic. Infer the conceptual stages someone should
study before they can productively read the seed.

Hard rules:
- Return 4 to 7 stages.
- Order stages pedagogically from foundations to frontier.
- Each stage needs a short title, a search query, a one-sentence purpose, and a
  few anchor concepts.
- Anchor concepts should be specific technical phrases or terms, not generic
  words like 'models' or 'learning'.
- Output ONLY JSON.
"""


class _StageSpec(BaseModel):
    # Some Gemini models return numeric stage indices instead of labels; coerce.
    model_config = {"coerce_numbers_to_str": True}

    stage: str = Field(min_length=1, max_length=50)
    purpose: str = Field(min_length=12, max_length=220)
    search_query: str = Field(min_length=4, max_length=120)
    anchor_concepts: list[str] = Field(min_length=1, max_length=6)


class _StagePlanOut(BaseModel):
    title: str = Field(min_length=5, max_length=120)
    rationale: str = Field(min_length=20, max_length=500)
    stages: list[_StageSpec] = Field(min_length=4, max_length=7)


@dataclass(frozen=True)
class _Candidate:
    paper: Paper
    score_row: VerosScore | None
    insight: AIInsight | None
    relevance: float
    concept_overlap: float
    anchor_overlap: float
    accessibility: float
    prerequisite_signal: float
    pathway_score: float


@dataclass(frozen=True)
class _StagePick:
    stage: _StageSpec
    candidate: _Candidate | None
    match_quality: str  # strong | weak | missing


def _tokenize(text: str) -> list[str]:
    tokens = [m.group(0) for m in _TOKEN_RE.finditer(text.lower())]
    return [t for t in tokens if t not in _STOPWORDS]


def _extract_concepts(text: str, limit: int = 12) -> list[tuple[str, float]]:
    counts: dict[str, int] = {}
    for token in _tokenize(text):
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    total = max(1, sum(c for _, c in ranked))
    return [(concept, round(count / total, 3)) for concept, count in ranked]


def _concept_map(text: str) -> dict[str, float]:
    return {concept: weight for concept, weight in _extract_concepts(text)}


def _weighted_overlap(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a).intersection(b)
    if not shared:
        return 0.0
    numer = sum(min(a[key], b[key]) for key in shared)
    denom = sum(a.values()) + sum(b.values()) - numer
    return numer / denom if denom > 0 else 0.0


def _anchor_terms(concepts: dict[str, float], limit: int = 6) -> list[str]:
    anchors = [
        concept
        for concept, _ in sorted(concepts.items(), key=lambda kv: (-kv[1], kv[0]))
        if concept not in _GENERIC_TOPIC_TERMS and concept not in _STOPWORDS
    ]
    return anchors[:limit]


def _clean_anchor_list(values: list[str], limit: int = 6) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = value.strip().lower()
        if not token or token in _GENERIC_TOPIC_TERMS or token in _STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return cleaned[:limit]


def _anchor_overlap(seed_anchors: list[str], paper_concepts: dict[str, float]) -> float:
    if not seed_anchors or not paper_concepts:
        return 0.0
    shared = [anchor for anchor in seed_anchors if anchor in paper_concepts]
    if not shared:
        return 0.0
    return sum(paper_concepts[anchor] for anchor in shared)


def _text_anchor_hits(anchors: list[str], paper: Paper, insight: AIInsight | None) -> int:
    if not anchors:
        return 0
    hay = _paper_text(paper, insight).lower()
    return sum(1 for anchor in anchors if anchor in hay)


def _paper_text(paper: Paper, insight: AIInsight | None) -> str:
    parts = [paper.title]
    if paper.abstract:
        parts.append(paper.abstract)
    if insight and insight.tldr:
        parts.append(insight.tldr)
    return "\n".join(parts)


def _seed_text_for_paper(paper: Paper, insight: AIInsight | None) -> str:
    return _paper_text(paper, insight)


def _load_cached_concepts(db: Session, paper_ids: list[str]) -> dict[str, dict[str, float]]:
    if not paper_ids:
        return {}
    rows = db.exec(select(PaperConcept).where(PaperConcept.paper_id.in_(paper_ids))).all()
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        result.setdefault(row.paper_id, {})[row.concept] = float(row.weight)
    return result


def _store_concepts(db: Session, paper_id: str, concepts: dict[str, float], source: str) -> None:
    db.exec(delete(PaperConcept).where(PaperConcept.paper_id == paper_id))
    for concept, weight in concepts.items():
        db.add(PaperConcept(paper_id=paper_id, concept=concept, weight=weight, source=source))


def _load_similarities_from_embedding(
    db: Session,
    seed_embedding: list[float] | None,
    exclude_paper_id: str | None,
    limit: int,
) -> dict[str, float]:
    if seed_embedding is None:
        return {}
    vec_str = "[" + ",".join(f"{v:.8f}" for v in seed_embedding) + "]"
    sql = (
        "SELECT paper_id, 1 - (embedding <=> CAST(:vec AS vector)) AS similarity "
        "FROM paper_embeddings "
    )
    params: dict[str, Any] = {"vec": vec_str, "n": limit}
    if exclude_paper_id:
        sql += "WHERE paper_id != :exclude_paper_id "
        params["exclude_paper_id"] = exclude_paper_id
    sql += "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :n"
    rows = db.execute(sa_text(sql), params).fetchall()
    return {row[0]: max(0.0, float(row[1])) for row in rows}


def _try_query_embedding(text: str) -> list[float] | None:
    try:
        from app.services.embeddings.factory import get_embedding_provider

        return get_embedding_provider().encode([text])[0]
    except Exception:
        logger.debug("Pathway embedding lookup skipped", exc_info=True)
        return None


def _normalize_score(score: float | None) -> float:
    return max(0.0, min(1.0, (score or 0.0) / 10.0))


def _accessibility(insight: AIInsight | None) -> float:
    if insight and insight.clarity is not None:
        return max(0.0, min(1.0, float(insight.clarity) / 100.0))
    return 0.5


def _prerequisite_signal(candidate: Paper, seed_year: int | None) -> float:
    if seed_year is None or candidate.year is None:
        return 0.5
    if candidate.year < seed_year:
        return 1.0
    if candidate.year == seed_year:
        return 0.7
    return 0.3


def _fallback_stage(position: int, total: int) -> str:
    if position <= max(1, total // 3):
        return "Foundations"
    if position <= max(2, (2 * total) // 3):
        return "Core methods"
    return "Frontier and context"


def _fallback_stage_plan(seed_label: str, anchors: list[str]) -> _StagePlanOut:
    meaningful = [anchor for anchor in anchors if anchor not in _GENERIC_TOPIC_TERMS][:6]
    primary = meaningful[:3] or ["foundations", "core methods", "applications"]
    stages = [
        _StageSpec(
            stage="Foundations",
            purpose=f"Build the baseline background needed to understand {seed_label}.",
            search_query=" ".join(primary[:2]),
            anchor_concepts=primary[:2] or primary,
        ),
        _StageSpec(
            stage="Core methods",
            purpose=f"Study the main techniques and representations that underpin {seed_label}.",
            search_query=" ".join(primary),
            anchor_concepts=primary,
        ),
        _StageSpec(
            stage="Interpretation and analysis",
            purpose=f"Focus on how the core methods are analyzed, interpreted, or evaluated in {seed_label}.",
            search_query=f"{' '.join(primary[:2])} interpretability analysis",
            anchor_concepts=(primary[:2] + ["interpretability"])[:4],
        ),
        _StageSpec(
            stage="Frontier and context",
            purpose=f"End with papers that connect the core ideas back to the frontier around {seed_label}.",
            search_query=f"{' '.join(primary)} frontier",
            anchor_concepts=primary[:2] or primary,
        ),
    ]
    return _StagePlanOut(
        title=f"Learning pathway for {seed_label}",
        rationale="Structured into conceptual stages first, then matched against the local corpus to find papers for each stage.",
        stages=stages,
    )


def _fallback_read_focus(paper: Paper, insight: AIInsight | None) -> str:
    if insight and insight.deep:
        return insight.deep[0]
    if paper.abstract:
        sentence = paper.abstract.split(". ")[0].strip()
        return sentence[:120] + ("…" if len(sentence) > 120 else "")
    return "Read the abstract and core method section."


def _stage_prompt(seed_label: str, seed_text: str, anchors: list[str]) -> str:
    payload = {
        "seed_label": seed_label,
        "seed_text": seed_text[:3000],
        "anchor_terms": anchors,
    }
    return "\n".join(
        [
            "Infer a staged learning pathway.",
            "Return JSON with keys: title, rationale, stages.",
            "Each stage must have: stage, purpose, search_query, anchor_concepts.",
            json.dumps(payload, indent=2),
        ]
    )


def _strip_reasoning_tags(text: str) -> str:
    """Strip <thought>/<think>/<reasoning>/<scratchpad> blocks emitted by Gemma,
    DeepSeek-R1, Qwen, etc. so the JSON extractor sees only the model's answer."""
    for tag in ("thought", "think", "reasoning", "scratchpad"):
        text = re.sub(
            rf"<{tag}>.*?</{tag}>",
            "",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # Some models leave an unterminated opening tag if they ran out of tokens
        # mid-thought; drop everything up to the last closing tag we can find,
        # otherwise drop the dangling open tag.
        text = re.sub(rf"<{tag}>", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"</{tag}>", "", text, flags=re.IGNORECASE)
    return text


def _strip_code_fence(text: str) -> str:
    cleaned = _strip_reasoning_tags(text).strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text.strip()

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1].strip()

    return text[start:].strip()


def _parse_stage_plan_json(raw_text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(raw_text)
    if not cleaned:
        raise ValueError("empty LLM response")

    parse_errors: list[str] = []
    for candidate in (cleaned, _extract_first_json_object(cleaned)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            parse_errors.append(str(exc))

    raise ValueError("; ".join(parse_errors) or "LLM returned invalid JSON")


def _stage_repair_prompt(raw_text: str) -> str:
    return "\n".join(
        [
            "Repair the following into valid JSON only.",
            "Return exactly one JSON object with keys: title, rationale, stages.",
            "Each stage must have: stage, purpose, search_query, anchor_concepts.",
            "Do not include markdown fences or explanatory text.",
            raw_text[:6000],
        ]
    )


def _infer_stage_plan(seed_label: str, seed_text: str, anchors: list[str]) -> tuple[_StagePlanOut, str | None]:
    provider = make_llm_provider()
    response = provider.complete_json(
        system=_SYSTEM_PROMPT,
        user=_stage_prompt(seed_label, seed_text, anchors),
        max_output_tokens=2200,
    )
    model = response.model
    try:
        parsed_json = _parse_stage_plan_json(response.text)
    except ValueError as exc:
        logger.warning("stage planner returned non-JSON; requesting repair: %s", exc)
        repair = provider.complete_json(
            system="You repair malformed model output into valid JSON.",
            user=_stage_repair_prompt(response.text),
            max_output_tokens=2200,
            temperature=0.0,
        )
        model = repair.model or model
        parsed_json = _parse_stage_plan_json(repair.text)

    parsed = _StagePlanOut.model_validate(parsed_json)
    cleaned_stages = []
    for stage in parsed.stages:
        cleaned_anchors = _clean_anchor_list(stage.anchor_concepts)
        search_query_tokens = _clean_anchor_list(_tokenize(stage.search_query), limit=8)
        if not cleaned_anchors:
            continue
        search_query = " ".join(search_query_tokens[:4]) or " ".join(cleaned_anchors[:3])
        cleaned_stages.append(
            stage.model_copy(
                update={
                    "anchor_concepts": cleaned_anchors,
                    "search_query": search_query,
                }
            )
        )
    if len(cleaned_stages) < 4:
        raise ValueError("LLM returned too few valid stages")
    return parsed.model_copy(update={"stages": cleaned_stages}), model


def _build_candidate_pool(
    db: Session,
    *,
    query_text: str,
    reference_year: int | None,
    required_anchors: list[str] | None = None,
    exclude_paper_ids: set[str] | None = None,
    limit: int,
) -> list[_Candidate]:
    paper_ids = list(db.exec(select(Paper.id)).all())
    if not paper_ids:
        return []

    papers = {p.id: p for p in db.exec(select(Paper).where(Paper.id.in_(paper_ids))).all()}
    scores = {
        s.paper_id: s for s in db.exec(select(VerosScore).where(VerosScore.paper_id.in_(paper_ids))).all()
    }
    insights = {
        i.paper_id: i for i in db.exec(select(AIInsight).where(AIInsight.paper_id.in_(paper_ids))).all()
    }
    cached_concepts = _load_cached_concepts(db, paper_ids)

    seed_concepts = _concept_map(query_text)
    seed_anchors = required_anchors or _anchor_terms(seed_concepts)
    seed_embedding = _try_query_embedding(query_text)

    similarities = _load_similarities_from_embedding(
        db,
        seed_embedding=seed_embedding,
        exclude_paper_id=None,
        limit=max(limit * 3, _MAX_CANDIDATES),
    )

    candidates: list[_Candidate] = []
    q_lower = query_text.lower()
    for paper_id, paper in papers.items():
        if exclude_paper_ids and paper_id in exclude_paper_ids:
            continue
        insight = insights.get(paper_id)
        paper_concepts = cached_concepts.get(paper_id)
        if paper_concepts is None:
            paper_concepts = _concept_map(_paper_text(paper, insight))
            if paper_concepts:
                _store_concepts(db, paper_id, paper_concepts, source="pathway_heuristic")
        overlap = _weighted_overlap(seed_concepts, paper_concepts)
        anchor_overlap = _anchor_overlap(seed_anchors, paper_concepts)
        anchor_hits = _text_anchor_hits(seed_anchors, paper, insight)
        relevance = max(similarities.get(paper_id, 0.0), overlap)
        text_match = q_lower in paper.title.lower() or q_lower in (paper.abstract or "").lower()
        if relevance <= 0.0 and not text_match:
            continue
        if seed_anchors:
            if anchor_overlap <= 0.0 and anchor_hits == 0:
                continue
            if len(seed_anchors) >= 2 and anchor_overlap < 0.12 and anchor_hits < 2:
                continue
        score_row = scores.get(paper_id)
        accessibility = _accessibility(insight)
        prereq = _prerequisite_signal(paper, reference_year)
        pathway_score = (
            0.30 * relevance
            + 0.25 * overlap
            + 0.20 * min(1.0, anchor_overlap + 0.15 * anchor_hits)
            + 0.15 * _normalize_score(float(score_row.score) if score_row else None)
            + 0.05 * accessibility
            + 0.05 * prereq
        )
        candidates.append(
            _Candidate(
                paper=paper,
                score_row=score_row,
                insight=insight,
                relevance=relevance,
                concept_overlap=overlap,
                anchor_overlap=anchor_overlap,
                accessibility=accessibility,
                prerequisite_signal=prereq,
                pathway_score=pathway_score,
            )
        )

    candidates.sort(
        key=lambda c: (
            c.pathway_score,
            float(c.score_row.score) if c.score_row else 0.0,
            c.paper.year or 0,
        ),
        reverse=True,
    )
    return candidates[:limit]


def _pick_stage_candidates(
    db: Session,
    *,
    stages: list[_StageSpec],
    seed_label: str,
    global_anchors: list[str],
    reference_year: int | None,
    include_seed_paper_id: str | None = None,
) -> list[_StagePick]:
    picks: list[_StagePick] = []
    used_ids: set[str] = set()
    if include_seed_paper_id is not None:
        used_ids.add(include_seed_paper_id)

    for stage in stages:
        stage_anchors = _clean_anchor_list(stage.anchor_concepts)
        required_anchors = _clean_anchor_list(global_anchors[:3] + stage_anchors, limit=6)
        stage_candidates = _build_candidate_pool(
            db,
            query_text=stage.search_query,
            reference_year=reference_year,
            required_anchors=required_anchors,
            exclude_paper_ids=used_ids,
            limit=4,
        )
        if not stage_candidates:
            picks.append(_StagePick(stage=stage, candidate=None, match_quality="missing"))
            continue
        best = stage_candidates[0]
        quality = "strong"
        if best.pathway_score < _WEAK_STAGE_SCORE:
            quality = "weak"
        elif best.anchor_overlap < 0.18 and _text_anchor_hits(required_anchors, best.paper, best.insight) < 2:
            quality = "weak"
        # Reserve any selected paper so one weak local match cannot fill multiple stages.
        used_ids.add(best.paper.id)
        picks.append(_StagePick(stage=stage, candidate=best, match_quality=quality))
    return picks


def _pathway_status_from_picks(picks: list[_StagePick]) -> tuple[str, dict[str, Any]]:
    weak = sum(1 for pick in picks if pick.match_quality == "weak")
    missing = sum(1 for pick in picks if pick.match_quality == "missing")
    total = len(picks)
    weak_or_missing = weak + missing
    strong = total - weak_or_missing
    needs_enrichment = (
        weak_or_missing >= _MIN_WEAK_OR_MISSING_FOR_ENRICHMENT
        or strong < _MIN_STRONG_STAGES_WITHOUT_ENRICHMENT
    )
    if needs_enrichment:
        return (
            "pending_enrichment",
            {
                "strong_stage_count": strong,
                "weak_stage_count": weak,
                "missing_stage_count": missing,
                "weak_or_missing_stage_count": weak_or_missing,
                "needs_enrichment": True,
                "enrichment_thresholds": {
                    "min_weak_or_missing_stages": _MIN_WEAK_OR_MISSING_FOR_ENRICHMENT,
                    "min_strong_stages_without_enrichment": _MIN_STRONG_STAGES_WITHOUT_ENRICHMENT,
                },
            },
        )
    return (
        "ready",
        {
            "strong_stage_count": strong,
            "weak_stage_count": weak,
            "missing_stage_count": missing,
            "weak_or_missing_stage_count": weak_or_missing,
            "needs_enrichment": False,
            "enrichment_thresholds": {
                "min_weak_or_missing_stages": _MIN_WEAK_OR_MISSING_FOR_ENRICHMENT,
                "min_strong_stages_without_enrichment": _MIN_STRONG_STAGES_WITHOUT_ENRICHMENT,
            },
        },
    )


def _query_text_for_stage_search(stage: _StageSpec, seed_label: str) -> str:
    parts = [stage.search_query, seed_label, " ".join(stage.anchor_concepts[:3])]
    return " ".join(part.strip() for part in parts if part.strip())


def find_openreview_candidates_for_stage(
    *,
    stage: _StageSpec,
    seed_label: str,
    exclude_ids: set[str] | None = None,
    limit: int = 5,
) -> list[str]:
    exclude_ids = exclude_ids or set()
    client = build_client(
        api_version="v2",
        username=None,
        password=None,
    )
    query_text = _query_text_for_stage_search(stage, seed_label).lower()
    query_tokens = set(_tokenize(query_text))
    anchor_tokens = {token.lower() for token in stage.anchor_concepts}
    hits: list[tuple[float, str]] = []
    seen: set[str] = set()

    for conference in _OPENREVIEW_VENUE_HINTS:
        search_attempts = [
            {"invitation": f"{conference}/-/Submission"},
            {"invitation": f"{conference}/-/Post_Submission"},
            {"content": {"venueid": conference}},
        ]
        notes: list[Any] = []
        for params in search_attempts:
            try:
                if hasattr(client, "get_all_notes"):
                    notes.extend(client.get_all_notes(**params))
                else:
                    notes.extend(client.get_notes(limit=1000, **params))
            except Exception:
                continue

        for note in notes:
            note_id = getattr(note, "id", None)
            if not note_id or note_id in exclude_ids or note_id in seen:
                continue
            content = getattr(note, "content", {}) or {}
            if isinstance(content, dict):
                title = content.get("title")
                abstract = content.get("abstract")
                venue = content.get("venueid") or content.get("venue")
                if isinstance(title, dict):
                    title = title.get("value")
                if isinstance(abstract, dict):
                    abstract = abstract.get("value")
                if isinstance(venue, dict):
                    venue = venue.get("value")
            else:
                title = None
                abstract = None
                venue = None

            text = " ".join(
                part.strip()
                for part in [
                    title if isinstance(title, str) else "",
                    abstract if isinstance(abstract, str) else "",
                    venue if isinstance(venue, str) else "",
                ]
                if part
            ).lower()
            if not text:
                continue

            text_tokens = set(_tokenize(text))
            anchor_hits = len(anchor_tokens.intersection(text_tokens))
            query_hits = len(query_tokens.intersection(text_tokens))
            if anchor_hits == 0 or query_hits < 2:
                continue

            score = 2.0 * anchor_hits + query_hits
            seen.add(note_id)
            hits.append((score, note_id))

    hits.sort(key=lambda item: item[0], reverse=True)
    return [forum_id for _, forum_id in hits[:limit]]


def _build_plan_from_stages(
    seed_label: str,
    stage_plan: _StagePlanOut,
    picks: list[_StagePick],
) -> tuple[str, str, list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    weak_or_missing = 0
    for pick in picks:
        stage = pick.stage
        candidate = pick.candidate
        if pick.match_quality != "strong":
            weak_or_missing += 1
        items.append(
            {
                "paper_id": candidate.paper.id if candidate else None,
                "stage": stage.stage,
                "why_this_paper": stage.purpose,
                "read_focus": (
                    _fallback_read_focus(candidate.paper, candidate.insight)
                    if candidate
                    else "No strong local paper yet; searching for one in the background."
                ),
                "match_quality": pick.match_quality,
                "search_query": stage.search_query,
                "anchor_concepts": stage.anchor_concepts,
            }
        )
    notes = {
        "strong_stage_count": len(picks) - weak_or_missing,
        "weak_or_missing_stage_count": weak_or_missing,
        "needs_enrichment": (
            weak_or_missing >= _MIN_WEAK_OR_MISSING_FOR_ENRICHMENT
            or (len(picks) - weak_or_missing) < _MIN_STRONG_STAGES_WITHOUT_ENRICHMENT
        ),
    }
    return stage_plan.title, stage_plan.rationale, items, notes


def _persist_pathway(
    db: Session,
    *,
    pathway_id: str,
    user_id: str | None,
    seed_paper_id: str | None,
    query_text: str | None,
    title: str,
    rationale: str,
    items: list[dict[str, Any]],
    model: str | None,
    status: str,
    enrichment_notes: dict[str, Any],
    candidate_lookup: dict[str, _Candidate],
) -> LearningPathway:
    pathway = LearningPathway(
        id=pathway_id,
        user_id=user_id,
        seed_paper_id=seed_paper_id,
        query_text=query_text,
        title=title,
        rationale=rationale,
        status=status,
        model=model,
        enrichment_notes=enrichment_notes,
    )
    db.add(pathway)
    db.flush()

    for position, item in enumerate(items, start=1):
        paper_id = item["paper_id"]
        candidate = candidate_lookup.get(paper_id) if paper_id else None
        db.add(
            LearningPathwayItem(
                pathway_id=pathway.id,
                position=position,
                paper_id=paper_id,
                stage=item["stage"],
                why_this_paper=item["why_this_paper"],
                read_focus=item["read_focus"],
                match_quality=item["match_quality"],
                search_query=item["search_query"],
                anchor_concepts=item["anchor_concepts"],
                score=round(candidate.pathway_score, 3) if candidate else None,
            )
        )
        if candidate is None:
            continue
        for concept, weight in _extract_concepts(
            f"{candidate.paper.title}\n{candidate.paper.abstract or ''}",
            limit=8,
        ):
            db.merge(
                PaperConcept(
                    paper_id=candidate.paper.id,
                    concept=concept,
                    weight=weight,
                    source="pathway_heuristic",
                )
            )
        if seed_paper_id:
            db.merge(
                PaperEdge(
                    src_paper_id=seed_paper_id,
                    dst_paper_id=item["paper_id"],
                    edge_type="pathway_support",
                    weight=round(candidate.pathway_score, 3),
                    edge_metadata={"pathway_id": pathway.id, "position": position},
                )
            )

    db.commit()
    return pathway


def get_cached_pathway(
    db: Session,
    *,
    seed_paper_id: str | None,
    query_text: str | None,
    user_id: str | None,
) -> LearningPathway | None:
    stmt = select(LearningPathway).where(LearningPathway.user_id == user_id)
    if seed_paper_id is not None:
        stmt = stmt.where(LearningPathway.seed_paper_id == seed_paper_id)
    if query_text is not None:
        stmt = stmt.where(LearningPathway.query_text == query_text)
    stmt = stmt.order_by(LearningPathway.generated_at.desc())  # type: ignore[attr-defined]
    return db.exec(stmt).first()


def build_learning_pathway_out(db: Session, pathway_id: str) -> LearningPathwayOut | None:
    pathway = db.get(LearningPathway, pathway_id)
    if pathway is None:
        return None

    rows = db.exec(
        select(LearningPathwayItem)
        .where(LearningPathwayItem.pathway_id == pathway_id)
        .order_by(LearningPathwayItem.position)
    ).all()
    paper_ids = [row.paper_id for row in rows if row.paper_id is not None]
    papers = {
        p.id: p for p in db.exec(select(Paper).where(Paper.id.in_(paper_ids))).all()
    }
    scores = {
        s.paper_id: s
        for s in db.exec(select(VerosScore).where(VerosScore.paper_id.in_(paper_ids))).all()
    }
    insights = {
        i.paper_id: i
        for i in db.exec(select(AIInsight).where(AIInsight.paper_id.in_(paper_ids))).all()
    }

    items: list[PathwayItem] = []
    for row in rows:
        paper_out: PaperOut | None = None
        if row.paper_id is not None:
            paper = papers.get(row.paper_id)
            if paper is not None:
                paper_out = build_paper_out(paper, scores.get(row.paper_id), insights.get(row.paper_id))
        items.append(
            PathwayItem(
                position=row.position,
                stage=row.stage,
                why_this_paper=row.why_this_paper,
                read_focus=row.read_focus,
                match_quality=row.match_quality,
                search_query=row.search_query,
                anchor_concepts=list(row.anchor_concepts or []),
                paper=paper_out,
            )
        )

    return LearningPathwayOut(
        id=pathway.id,
        title=pathway.title,
        rationale=pathway.rationale,
        status=pathway.status,
        enrichment_notes=dict(pathway.enrichment_notes or {}),
        seed_paper_id=pathway.seed_paper_id,
        query_text=pathway.query_text,
        items=items,
    )


def get_stage_items_for_enrichment(db: Session, pathway_id: str) -> list[LearningPathwayItem]:
    return db.exec(
        select(LearningPathwayItem)
        .where(LearningPathwayItem.pathway_id == pathway_id)
        .order_by(LearningPathwayItem.position)
    ).all()


def generate_pathway_from_paper(
    db: Session,
    *,
    paper_id: str,
    user_id: str | None,
    limit: int = 8,
    force: bool = False,
    enqueue_enrichment: bool = True,
) -> LearningPathwayOut:
    cached = get_cached_pathway(db, seed_paper_id=paper_id, query_text=None, user_id=user_id)
    if cached is not None and not force:
        out = build_learning_pathway_out(db, cached.id)
        assert out is not None
        return out

    seed_paper = db.get(Paper, paper_id)
    if seed_paper is None:
        raise ValueError(f"paper {paper_id!r} not found")

    seed_label = seed_paper.title
    seed_text = _seed_text_for_paper(seed_paper, db.get(AIInsight, paper_id))
    global_anchors = _anchor_terms(_concept_map(seed_text))
    model: str | None = None
    try:
        stage_plan, model = _infer_stage_plan(seed_label, seed_text, global_anchors)
    except Exception:
        logger.exception("stage planning fell back to deterministic stages for %s", paper_id)
        stage_plan = _fallback_stage_plan(seed_label, global_anchors)

    picks = _pick_stage_candidates(
        db,
        stages=stage_plan.stages,
        seed_label=seed_label,
        global_anchors=global_anchors,
        reference_year=seed_paper.year,
        include_seed_paper_id=paper_id,
    )
    if len([pick for pick in picks if pick.candidate is not None]) < _MIN_PATHWAY_CANDIDATES:
        raise ValueError(
            "local corpus is too sparse to build a trustworthy pathway for this paper yet"
        )
    title, rationale, items, notes = _build_plan_from_stages(seed_label, stage_plan, picks)
    status, quality_notes = _pathway_status_from_picks(picks)
    notes.update(quality_notes)

    pathway = _persist_pathway(
        db,
        pathway_id=str(uuid4()),
        user_id=user_id,
        seed_paper_id=paper_id,
        query_text=None,
        title=title,
        rationale=rationale,
        items=items,
        model=model,
        status=status,
        enrichment_notes=notes,
        candidate_lookup={pick.candidate.paper.id: pick.candidate for pick in picks if pick.candidate is not None},
    )
    if enqueue_enrichment and status == "pending_enrichment":
        from app.workers.tasks import enrich_learning_pathway_task  # noqa: PLC0415

        enrich_learning_pathway_task.delay(pathway.id)
    out = build_learning_pathway_out(db, pathway.id)
    assert out is not None
    return out


def generate_pathway_from_topic(
    db: Session,
    *,
    topic: str,
    user_id: str | None,
    limit: int = 8,
    force: bool = False,
    enqueue_enrichment: bool = True,
) -> LearningPathwayOut:
    query = topic.strip()
    if not query:
        raise ValueError("topic must not be empty")

    cached = get_cached_pathway(db, seed_paper_id=None, query_text=query, user_id=user_id)
    if cached is not None and not force:
        out = build_learning_pathway_out(db, cached.id)
        assert out is not None
        return out

    quick_hits = search_papers(db, query, limit=max(limit, 6), offset=0)
    if not quick_hits:
        raise ValueError("no local papers match this topic yet")

    model: str | None = None
    global_anchors = _anchor_terms(_concept_map(query))
    try:
        stage_plan, model = _infer_stage_plan(query, query, global_anchors)
    except Exception:
        logger.exception("topic stage planning fell back to deterministic stages for %s", query)
        stage_plan = _fallback_stage_plan(query, global_anchors)

    picks = _pick_stage_candidates(
        db,
        stages=stage_plan.stages,
        seed_label=query,
        global_anchors=global_anchors,
        reference_year=None,
    )
    if len([pick for pick in picks if pick.candidate is not None]) < _MIN_PATHWAY_CANDIDATES:
        raise ValueError(
            "local corpus is too sparse to build a trustworthy pathway for this topic yet"
        )
    title, rationale, items, notes = _build_plan_from_stages(query, stage_plan, picks)
    status, quality_notes = _pathway_status_from_picks(picks)
    notes.update(quality_notes)

    pathway = _persist_pathway(
        db,
        pathway_id=str(uuid4()),
        user_id=user_id,
        seed_paper_id=None,
        query_text=query,
        title=title,
        rationale=rationale,
        items=items,
        model=model,
        status=status,
        enrichment_notes=notes,
        candidate_lookup={pick.candidate.paper.id: pick.candidate for pick in picks if pick.candidate is not None},
    )
    if enqueue_enrichment and status == "pending_enrichment":
        from app.workers.tasks import enrich_learning_pathway_task  # noqa: PLC0415

        enrich_learning_pathway_task.delay(pathway.id)
    out = build_learning_pathway_out(db, pathway.id)
    assert out is not None
    return out


# --------------------------------------------------------------------------- #
# Explore: topic-driven, Veros-ranked, LLM-ordered learning sequence.
# --------------------------------------------------------------------------- #

_EXPLORE_PER_TOPIC = 3
_EXPLORE_POOL_LIMIT = 10
_EXPLORE_MIN_PAPERS = 6


_ORDER_SYSTEM_PROMPT = """You are Veros Explore, a pedagogical sequencer.

Given a learning goal and a set of candidate papers grouped by sub-topic, you
output the optimal reading order so the reader builds understanding from
foundations to frontier (e.g. for "mixture of experts": transformer basics →
conditional computation → modern MoE architectures).

Hard rules:
- Keep at least 6 papers; you may drop redundant or off-topic ones.
- Only use paper_id values that appear in the input.
- learning_step values must be 1..N and contiguous, no duplicates.
- why_now: one short sentence on why this paper comes at this point.
- Output ONLY JSON.
"""

_LOCAL_ORDER_SYSTEM_PROMPT = """You are Veros Explore, a pedagogical sequencer.

The app has already searched a local JSON paper corpus and selected candidate
papers. Your only job is to order these papers so a reader learns the topic as
smoothly as possible, from foundations to frontier.

Hard rules:
- Only use paper_id values from the input.
- Keep at least 6 papers unless fewer were provided.
- learning_step values must be 1..N and contiguous, no duplicates.
- why_now: one short sentence on why this paper comes at this point.
- Output ONLY JSON.
"""


@dataclass(frozen=True)
class _TopicBucket:
    stage: _StageSpec
    candidates: list[_Candidate]
    match_quality: str  # strong | weak | missing


class _OrderedItem(BaseModel):
    paper_id: str = Field(min_length=1)
    learning_step: int = Field(ge=1, le=64)
    why_now: str = Field(min_length=4, max_length=400)


class _OrderedPlanOut(BaseModel):
    rationale: str = Field(default="", max_length=800)
    items: list[_OrderedItem] = Field(min_length=1, max_length=32)


def _local_order_prompt(topic: str, candidates: list[dict[str, Any]]) -> str:
    payload = {
        "seed_label": topic,
        "papers": candidates[:16],
    }
    return "\n".join(
        [
            f"Learning goal: {topic}",
            "Order the candidate papers below for optimal learning.",
            "Return JSON: { rationale, items: [{ paper_id, learning_step, why_now }] }.",
            "Use only the paper_id values from the input.",
            json.dumps(payload, indent=2),
        ]
    )


def order_local_explore_candidates(
    *,
    topic: str,
    candidates: list[dict[str, Any]],
) -> tuple[_OrderedPlanOut, str | None]:
    query = topic.strip()
    valid_ids = {
        str(candidate.get("paper_id"))
        for candidate in candidates
        if str(candidate.get("paper_id") or "").strip()
    }
    if not query:
        raise ValueError("topic must not be empty")
    if not valid_ids:
        raise ValueError("no candidate papers to order")

    provider = make_llm_provider()
    response = provider.complete_json(
        system=_LOCAL_ORDER_SYSTEM_PROMPT,
        user=_local_order_prompt(query, candidates),
        max_output_tokens=1200,
        temperature=0.15,
    )
    model = response.model
    parsed_json = _parse_stage_plan_json(response.text)
    parsed = _OrderedPlanOut.model_validate(parsed_json)
    seen_ids: set[str] = set()
    cleaned: list[_OrderedItem] = []
    for item in parsed.items:
        if item.paper_id not in valid_ids or item.paper_id in seen_ids:
            continue
        seen_ids.add(item.paper_id)
        cleaned.append(item)

    min_items = min(_EXPLORE_MIN_PAPERS, len(valid_ids))
    if len(cleaned) < min_items:
        raise ValueError(f"LLM returned too few valid items ({len(cleaned)})")

    cleaned.sort(key=lambda item: item.learning_step)
    contiguous = [
        item.model_copy(update={"learning_step": position})
        for position, item in enumerate(cleaned, start=1)
    ]
    return parsed.model_copy(update={"items": contiguous}), model


def _bucket_quality(candidates: list[_Candidate], required_anchors: list[str]) -> str:
    if not candidates:
        return "missing"
    best = candidates[0]
    if best.pathway_score < _WEAK_STAGE_SCORE:
        return "weak"
    if best.anchor_overlap < 0.18 and _text_anchor_hits(required_anchors, best.paper, best.insight) < 2:
        return "weak"
    return "strong"


def _pick_topic_buckets(
    db: Session,
    *,
    stages: list[_StageSpec],
    seed_label: str,  # noqa: ARG001 — kept for symmetry with _pick_stage_candidates
    global_anchors: list[str],
    reference_year: int | None,
    per_topic: int = _EXPLORE_PER_TOPIC,
) -> list[_TopicBucket]:
    buckets: list[_TopicBucket] = []
    used_ids: set[str] = set()

    for stage in stages:
        stage_anchors = _clean_anchor_list(stage.anchor_concepts)
        required_anchors = _clean_anchor_list(global_anchors[:3] + stage_anchors, limit=6)
        pool = _build_candidate_pool(
            db,
            query_text=stage.search_query,
            reference_year=reference_year,
            required_anchors=required_anchors,
            exclude_paper_ids=used_ids,
            limit=_EXPLORE_POOL_LIMIT,
        )
        # Within the embedding+anchor matched pool, rank by Veros score so the
        # user's "rank by Veros score within the topic" requirement holds.
        ranked = sorted(
            pool,
            key=lambda c: (
                float(c.score_row.score) if c.score_row else 0.0,
                c.pathway_score,
                c.paper.year or 0,
            ),
            reverse=True,
        )
        picked: list[_Candidate] = []
        for cand in ranked:
            if cand.paper.id in used_ids:
                continue
            picked.append(cand)
            used_ids.add(cand.paper.id)
            if len(picked) >= per_topic:
                break
        buckets.append(
            _TopicBucket(
                stage=stage,
                candidates=picked,
                match_quality=_bucket_quality(picked, required_anchors),
            )
        )
    return buckets


def _order_payload(seed_label: str, buckets: list[_TopicBucket]) -> dict[str, Any]:
    topics: list[dict[str, Any]] = []
    papers: list[dict[str, Any]] = []
    for bucket in buckets:
        topics.append(
            {
                "stage": bucket.stage.stage,
                "purpose": bucket.stage.purpose,
                "anchor_concepts": list(bucket.stage.anchor_concepts),
            }
        )
        for cand in bucket.candidates:
            tldr = (
                cand.insight.tldr
                if cand.insight and cand.insight.tldr
                else (cand.paper.abstract or "")
            )[:320]
            papers.append(
                {
                    "paper_id": cand.paper.id,
                    "title": cand.paper.title,
                    "year": cand.paper.year,
                    "stage": bucket.stage.stage,
                    "anchor_concepts": list(bucket.stage.anchor_concepts)[:4],
                    "veros_score": float(cand.score_row.score) if cand.score_row else None,
                    "tldr": tldr,
                }
            )
    return {"seed_label": seed_label, "topics": topics, "papers": papers}


def _order_prompt(seed_label: str, buckets: list[_TopicBucket]) -> str:
    payload = _order_payload(seed_label, buckets)
    return "\n".join(
        [
            f"Learning goal: {seed_label}",
            "Order the candidate papers below for optimal learning.",
            "Return JSON: { rationale, items: [{ paper_id, learning_step, why_now }] }.",
            "Use only the paper_id values from the input. Keep at least 6 papers.",
            json.dumps(payload, indent=2),
        ]
    )


def _order_repair_prompt(raw_text: str) -> str:
    return "\n".join(
        [
            "Repair the following into valid JSON only.",
            "Return exactly one JSON object with keys: rationale, items.",
            "Each item must have: paper_id, learning_step, why_now.",
            "Do not include markdown fences or explanatory text.",
            raw_text[:6000],
        ]
    )


def _order_papers_for_learning(
    seed_label: str,
    buckets: list[_TopicBucket],
) -> tuple[_OrderedPlanOut, str | None]:
    valid_ids: set[str] = {
        cand.paper.id for bucket in buckets for cand in bucket.candidates
    }
    if not valid_ids:
        raise ValueError("no candidates to order")

    provider = make_llm_provider()
    response = provider.complete_json(
        system=_ORDER_SYSTEM_PROMPT,
        user=_order_prompt(seed_label, buckets),
        max_output_tokens=4000,
    )
    model = response.model
    try:
        parsed_json = _parse_stage_plan_json(response.text)
    except ValueError as exc:
        logger.warning("explore ordering returned non-JSON; requesting repair: %s", exc)
        repair = provider.complete_json(
            system="You repair malformed model output into valid JSON.",
            user=_order_repair_prompt(response.text),
            max_output_tokens=4000,
            temperature=0.0,
        )
        model = repair.model or model
        parsed_json = _parse_stage_plan_json(repair.text)

    parsed = _OrderedPlanOut.model_validate(parsed_json)

    seen_ids: set[str] = set()
    cleaned: list[_OrderedItem] = []
    for item in parsed.items:
        if item.paper_id not in valid_ids or item.paper_id in seen_ids:
            continue
        seen_ids.add(item.paper_id)
        cleaned.append(item)

    if len(cleaned) < _EXPLORE_MIN_PAPERS:
        raise ValueError(f"LLM returned too few valid items ({len(cleaned)})")

    cleaned.sort(key=lambda i: i.learning_step)
    contiguous = [
        item.model_copy(update={"learning_step": position})
        for position, item in enumerate(cleaned, start=1)
    ]
    return parsed.model_copy(update={"items": contiguous}), model


def _fallback_ordering(buckets: list[_TopicBucket]) -> _OrderedPlanOut:
    """Stage-order, then Veros score within stage. Used when the LLM step fails."""
    flat: list[tuple[int, _Candidate, _StageSpec]] = []
    for stage_index, bucket in enumerate(buckets):
        sorted_candidates = sorted(
            bucket.candidates,
            key=lambda c: (
                float(c.score_row.score) if c.score_row else 0.0,
                c.pathway_score,
            ),
            reverse=True,
        )
        for cand in sorted_candidates:
            flat.append((stage_index, cand, bucket.stage))

    items: list[_OrderedItem] = []
    for position, (_, cand, stage) in enumerate(flat, start=1):
        items.append(
            _OrderedItem(
                paper_id=cand.paper.id,
                learning_step=position,
                why_now=stage.purpose,
            )
        )
    return _OrderedPlanOut(
        rationale="Deterministic fallback ordering: stages from foundations to frontier, top Veros score within each stage.",
        items=items,
    )


def _build_explore_items(
    *,
    ordered: _OrderedPlanOut,
    buckets: list[_TopicBucket],
) -> tuple[list[dict[str, Any]], dict[str, _Candidate]]:
    candidate_by_id: dict[str, _Candidate] = {
        cand.paper.id: cand for bucket in buckets for cand in bucket.candidates
    }
    bucket_by_paper_id: dict[str, _TopicBucket] = {
        cand.paper.id: bucket for bucket in buckets for cand in bucket.candidates
    }
    items: list[dict[str, Any]] = []
    for item in ordered.items:
        cand = candidate_by_id.get(item.paper_id)
        bucket = bucket_by_paper_id.get(item.paper_id)
        if cand is None or bucket is None:
            continue
        items.append(
            {
                "paper_id": cand.paper.id,
                "stage": bucket.stage.stage,
                "why_this_paper": bucket.stage.purpose,
                "read_focus": item.why_now,
                "match_quality": bucket.match_quality,
                "search_query": bucket.stage.search_query,
                "anchor_concepts": list(bucket.stage.anchor_concepts),
            }
        )
    return items, candidate_by_id


def generate_explore_path(
    db: Session,
    *,
    topic: str,
    user_id: str | None,
    per_topic: int = _EXPLORE_PER_TOPIC,
    force: bool = False,
) -> LearningPathwayOut:
    query = topic.strip()
    if not query:
        raise ValueError("topic must not be empty")

    cached = get_cached_pathway(db, seed_paper_id=None, query_text=query, user_id=user_id)
    if cached is not None and not force:
        out = build_learning_pathway_out(db, cached.id)
        assert out is not None
        return out

    global_anchors = _anchor_terms(_concept_map(query))
    model: str | None = None
    try:
        stage_plan, model = _infer_stage_plan(query, query, global_anchors)
    except Exception:
        logger.exception("explore stage planning fell back to deterministic stages for %s", query)
        stage_plan = _fallback_stage_plan(query, global_anchors)

    buckets = _pick_topic_buckets(
        db,
        stages=stage_plan.stages,
        seed_label=query,
        global_anchors=global_anchors,
        reference_year=None,
        per_topic=per_topic,
    )
    distinct_papers = {cand.paper.id for bucket in buckets for cand in bucket.candidates}
    if len(distinct_papers) < _EXPLORE_MIN_PAPERS:
        raise ValueError(
            "local corpus is too sparse to build a learning sequence for this topic yet"
        )

    ordering_source = "llm"
    try:
        ordered, order_model = _order_papers_for_learning(query, buckets)
        if order_model:
            model = order_model
    except Exception:
        logger.exception("explore ordering fell back to deterministic ordering for %s", query)
        ordered = _fallback_ordering(buckets)
        ordering_source = "fallback"

    items, candidate_lookup = _build_explore_items(ordered=ordered, buckets=buckets)
    if len(items) < _EXPLORE_MIN_PAPERS:
        # LLM dropped too many — fall back so the user always sees a usable sequence.
        ordered = _fallback_ordering(buckets)
        ordering_source = "fallback"
        items, candidate_lookup = _build_explore_items(ordered=ordered, buckets=buckets)

    title = stage_plan.title
    rationale_parts = [stage_plan.rationale.strip(), ordered.rationale.strip()]
    rationale = "\n\n".join(part for part in rationale_parts if part)

    weak_or_missing = sum(1 for bucket in buckets if bucket.match_quality != "strong")
    notes: dict[str, Any] = {
        "topic_count": len(buckets),
        "paper_count": len(items),
        "ordering_source": ordering_source,
        "strong_stage_count": len(buckets) - weak_or_missing,
        "weak_or_missing_stage_count": weak_or_missing,
        "needs_enrichment": False,
    }

    pathway = _persist_pathway(
        db,
        pathway_id=str(uuid4()),
        user_id=user_id,
        seed_paper_id=None,
        query_text=query,
        title=title,
        rationale=rationale,
        items=items,
        model=model,
        status="ready",
        enrichment_notes=notes,
        candidate_lookup=candidate_lookup,
    )
    out = build_learning_pathway_out(db, pathway.id)
    assert out is not None
    return out
