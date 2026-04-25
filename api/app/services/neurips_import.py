from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from app.db.models import Paper, Review
from app.services.scoring import compute_and_store_score
from app.utils.ratings import parse_numeric, parse_recommendation

_NEURIPS_2025_VENUE_ID = "NeurIPS.cc/2025/Conference"


@dataclass(frozen=True)
class NeuripsImportResult:
    source: str
    seen_rows: int
    imported_papers: int
    skipped_existing: int
    imported_reviews: int
    scored_papers: int


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _sanitize_value(item) for key, item in value.items()}
    return value


def _acceptance_from_venue(venue: str | None) -> str | None:
    text = (venue or "").lower()
    if "reject" in text:
        return "reject"
    if "oral" in text or "spotlight" in text:
        return "oral"
    if "poster" in text or "accept" in text:
        return "poster"
    return None


def _venue_from_paper(raw_paper: dict[str, Any]) -> str | None:
    venue = raw_paper.get("venue")
    if isinstance(venue, str) and venue.strip():
        return venue.strip()
    venue_id = raw_paper.get("venueid")
    if venue_id == _NEURIPS_2025_VENUE_ID:
        return "NeurIPS 2025"
    return None


def _openreview_url(raw_paper: dict[str, Any], paper_id: str) -> str:
    url = raw_paper.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return f"https://openreview.net/forum?id={paper_id}"


def _upsert_paper(db: Session, raw_paper: dict[str, Any]) -> None:
    raw_paper = _sanitize_value(raw_paper)
    paper_id = str(raw_paper["id"])
    venue = _venue_from_paper(raw_paper)
    authors = raw_paper.get("authors")
    stmt = insert(Paper).values(
        id=paper_id,
        title=str(raw_paper.get("title") or paper_id),
        authors=[str(author) for author in authors] if isinstance(authors, list) else [],
        venue=venue,
        year=2025,
        abstract=raw_paper.get("abstract") if isinstance(raw_paper.get("abstract"), str) else None,
        openreview_url=_openreview_url(raw_paper, paper_id),
        acceptance=_acceptance_from_venue(venue),
        ingested_at=datetime.now(UTC),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Paper.id],
        set_={
            "title": stmt.excluded.title,
            "authors": stmt.excluded.authors,
            "venue": stmt.excluded.venue,
            "year": stmt.excluded.year,
            "abstract": stmt.excluded.abstract,
            "openreview_url": stmt.excluded.openreview_url,
            "acceptance": stmt.excluded.acceptance,
            "ingested_at": stmt.excluded.ingested_at,
        },
    )
    db.exec(stmt)


def _upsert_review(db: Session, paper_id: str, raw_review: dict[str, Any]) -> None:
    raw_review = _sanitize_value(raw_review)
    content = raw_review.get("content")
    if not isinstance(content, dict):
        content = {}
    rating = parse_numeric(content.get("rating"))
    confidence = parse_numeric(content.get("confidence"))
    signatures = raw_review.get("signatures")

    stmt = insert(Review).values(
        id=str(raw_review["id"]),
        paper_id=paper_id,
        invitation=raw_review.get("invitation")
        if isinstance(raw_review.get("invitation"), str)
        else None,
        signatures=[str(signature) for signature in signatures]
        if isinstance(signatures, list)
        else [],
        rating=rating,
        confidence=confidence,
        recommendation=parse_recommendation(content.get("rating")),
        content=content,
        created_at=_parse_datetime(raw_review.get("created")),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Review.id],
        set_={
            "paper_id": stmt.excluded.paper_id,
            "invitation": stmt.excluded.invitation,
            "signatures": stmt.excluded.signatures,
            "rating": stmt.excluded.rating,
            "confidence": stmt.excluded.confidence,
            "recommendation": stmt.excluded.recommendation,
            "content": stmt.excluded.content,
            "created_at": stmt.excluded.created_at,
        },
    )
    db.exec(stmt)


def _iter_jsonl(source: Path) -> Any:
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def import_neurips_2025_jsonl(
    db: Session,
    source: str | Path,
    *,
    limit: int | None = None,
    skip_existing: bool = False,
) -> NeuripsImportResult:
    source_path = Path(source)
    seen_rows = 0
    imported_papers = 0
    skipped_existing = 0
    imported_reviews = 0
    scored_papers = 0

    for row in _iter_jsonl(source_path):
        if limit is not None and imported_papers >= limit:
            break
        seen_rows += 1

        raw_paper = row.get("paper")
        raw_reviews = row.get("reviews", [])
        if not isinstance(raw_paper, dict) or "id" not in raw_paper:
            continue
        if not isinstance(raw_reviews, list):
            raw_reviews = []

        paper_id = str(raw_paper["id"])
        if skip_existing and db.get(Paper, paper_id) is not None:
            skipped_existing += 1
            continue

        _upsert_paper(db, raw_paper)
        for raw_review in raw_reviews:
            if isinstance(raw_review, dict) and "id" in raw_review:
                _upsert_review(db, paper_id, raw_review)
                imported_reviews += 1
        db.commit()

        if compute_and_store_score(db, paper_id) is not None:
            scored_papers += 1
        imported_papers += 1

    return NeuripsImportResult(
        source=str(source_path),
        seen_rows=seen_rows,
        imported_papers=imported_papers,
        skipped_existing=skipped_existing,
        imported_reviews=imported_reviews,
        scored_papers=scored_papers,
    )
