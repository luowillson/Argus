from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.pool import NullPool
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import Paper, Review
from app.services.scoring import compute_and_store_score
from app.utils.ratings import parse_numeric, parse_recommendation


@dataclass
class ImportStats:
    seen_rows: int = 0
    imported_papers: int = 0
    skipped_existing: int = 0
    imported_reviews: int = 0
    scored_papers: int = 0


def make_import_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"prepare_threshold": None},
        poolclass=NullPool,
        future=True,
    )


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_value(item) for key, item in value.items()}
    return value


def acceptance_from_venue(venue: str | None) -> str | None:
    text = (venue or "").lower()
    if "reject" in text:
        return "reject"
    if "oral" in text or "spotlight" in text:
        return "oral"
    if "poster" in text or "accept" in text or "notable" in text:
        return "poster"
    return None


def year_from_text(*values: object) -> int | None:
    for value in values:
        if not isinstance(value, str):
            continue
        for year in range(2035, 1999, -1):
            if str(year) in value:
                return year
    return None


def venue_from_paper(raw_paper: dict[str, Any]) -> str | None:
    venue = raw_paper.get("venue")
    if isinstance(venue, str) and venue.strip():
        return venue.strip()
    raw_content = raw_paper.get("raw_content")
    if isinstance(raw_content, dict):
        raw_venue = raw_content.get("venue") or raw_content.get("venueid")
        if isinstance(raw_venue, str) and raw_venue.strip():
            return raw_venue.strip()
    venue_id = raw_paper.get("venueid")
    return venue_id.strip() if isinstance(venue_id, str) and venue_id.strip() else None


def paper_row(raw_paper: dict[str, Any]) -> dict[str, Any]:
    raw_paper = sanitize_value(raw_paper)
    paper_id = str(raw_paper["id"])
    venue = venue_from_paper(raw_paper)
    authors = raw_paper.get("authors")
    raw_content = raw_paper.get("raw_content") if isinstance(raw_paper.get("raw_content"), dict) else {}
    abstract = raw_paper.get("abstract") or raw_content.get("abstract")
    return {
        "id": paper_id,
        "title": str(raw_paper.get("title") or paper_id),
        "authors": [str(author) for author in authors] if isinstance(authors, list) else [],
        "venue": venue,
        "year": year_from_text(venue, raw_paper.get("venueid")),
        "abstract": abstract if isinstance(abstract, str) else None,
        "openreview_url": str(
            raw_paper.get("url") or f"https://openreview.net/forum?id={paper_id}"
        ),
        "acceptance": raw_paper.get("acceptance")
        if isinstance(raw_paper.get("acceptance"), str)
        else acceptance_from_venue(venue),
        "ingested_at": datetime.now(UTC),
    }


def review_row(paper_id: str, raw_review: dict[str, Any]) -> dict[str, Any]:
    raw_review = sanitize_value(raw_review)
    content = raw_review.get("content")
    if not isinstance(content, dict):
        content = {}
    signatures = raw_review.get("signatures")
    return {
        "id": str(raw_review["id"]),
        "paper_id": paper_id,
        "invitation": raw_review.get("invitation")
        if isinstance(raw_review.get("invitation"), str)
        else None,
        "signatures": [str(signature) for signature in signatures]
        if isinstance(signatures, list)
        else [],
        "rating": parse_numeric(content.get("rating")),
        "confidence": parse_numeric(content.get("confidence")),
        "recommendation": parse_recommendation(content.get("recommendation") or content.get("rating")),
        "content": content,
        "created_at": parse_datetime(raw_review.get("created")),
    }


def iter_jsonl(source: Path):
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def upsert_papers(db: Session, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = insert(Paper).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Paper.__table__.c.id],
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


def upsert_reviews(db: Session, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = insert(Review).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Review.__table__.c.id],
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


def flush_chunk(
    db: Session,
    paper_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    upsert_papers(db, paper_rows)
    upsert_reviews(db, review_rows)
    db.commit()
    paper_rows.clear()
    review_rows.clear()


def import_jsonl(
    source: Path,
    *,
    limit: int | None,
    force: bool,
    chunk_size: int,
    chunk_delay: float,
    score: bool,
    score_delay: float,
) -> ImportStats:
    stats = ImportStats()
    engine = make_import_engine()
    imported_ids: list[str] = []
    with Session(engine) as db:
        db.execute(sa_text("SET statement_timeout = 60000"))
        existing_ids = set() if force else set(db.exec(select(Paper.id)).all())
        print(f"Loaded {len(existing_ids)} existing paper id(s).", flush=True)

        paper_rows: list[dict[str, Any]] = []
        review_rows: list[dict[str, Any]] = []
        for row in iter_jsonl(source):
            if limit is not None and stats.imported_papers >= limit:
                break
            stats.seen_rows += 1

            raw_paper = row.get("paper")
            raw_reviews = row.get("reviews", [])
            if not isinstance(raw_paper, dict) or "id" not in raw_paper:
                continue
            if not isinstance(raw_reviews, list):
                raw_reviews = []

            paper_id = str(raw_paper["id"])
            if paper_id in existing_ids:
                stats.skipped_existing += 1
                continue

            paper_rows.append(paper_row(raw_paper))
            for raw_review in raw_reviews:
                if isinstance(raw_review, dict) and "id" in raw_review:
                    review_rows.append(review_row(paper_id, raw_review))
                    stats.imported_reviews += 1

            existing_ids.add(paper_id)
            imported_ids.append(paper_id)
            stats.imported_papers += 1
            if len(paper_rows) >= chunk_size:
                flush_chunk(db, paper_rows, review_rows)
                print(
                    f"Imported {stats.imported_papers} paper(s), "
                    f"{stats.imported_reviews} review(s)...",
                    flush=True,
                )
                if chunk_delay:
                    time.sleep(chunk_delay)

        flush_chunk(db, paper_rows, review_rows)

    if score and imported_ids:
        with Session(engine) as db:
            db.execute(sa_text("SET statement_timeout = 60000"))
            for paper_id in imported_ids:
                compute_and_store_score(db, paper_id)
                stats.scored_papers += 1
                if stats.scored_papers % 100 == 0:
                    print(f"Scored {stats.scored_papers} paper(s)...", flush=True)
                if score_delay:
                    time.sleep(score_delay)

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a local OpenReview JSONL file into the API database."
    )
    parser.add_argument("--source", required=True, help="Path to the local OpenReview JSONL file.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of papers to import.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Number of papers to upsert per database transaction.",
    )
    parser.add_argument(
        "--chunk-delay",
        type=float,
        default=0.0,
        help="Seconds to sleep after each bulk database transaction.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reimport and update papers that already exist in the database.",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Compute Veros scores after the fast paper/review upload.",
    )
    parser.add_argument(
        "--score-delay",
        type=float,
        default=0.0,
        help="Seconds to sleep after each score write when --score is enabled.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.chunk_delay < 0:
        raise ValueError("--chunk-delay cannot be negative.")
    if args.score_delay < 0:
        raise ValueError("--score-delay cannot be negative.")
    result = import_jsonl(
        Path(args.source),
        limit=args.limit,
        force=args.force,
        chunk_size=args.chunk_size,
        chunk_delay=args.chunk_delay,
        score=args.score,
        score_delay=args.score_delay,
    )

    print(
        "Imported OpenReview JSONL: "
        f"seen_rows={result.seen_rows}, "
        f"imported_papers={result.imported_papers}, "
        f"skipped_existing={result.skipped_existing}, "
        f"imported_reviews={result.imported_reviews}, "
        f"scored_papers={result.scored_papers}, "
        f"source={args.source}"
    )


if __name__ == "__main__":
    main()
