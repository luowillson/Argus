from __future__ import annotations

import argparse
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import create_engine, exists, text as sa_text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.pool import NullPool
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import Paper, Review, VerosScore
from app.services.scoring import (
    iclr_section_breakdown,
    is_iclr_2025_paper,
    is_neurips_2025_paper,
    neurips_section_breakdown,
    rating_scale_max_for_paper,
)
from app.services.veros_score import ReviewSignal, compute_score


@dataclass
class ScoreStats:
    seen: int = 0
    scored: int = 0
    insufficient: int = 0
    failed: int = 0


def make_engine():
    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"prepare_threshold": None},
        poolclass=NullPool,
        future=True,
    )


def matching_paper_ids(
    db: Session,
    *,
    year: int | None,
    venue_contains: str | None,
    force: bool,
    limit: int | None,
) -> list[str]:
    stmt = select(Paper.id).order_by(Paper.id)
    if year is not None:
        stmt = stmt.where(Paper.year == year)
    if venue_contains:
        stmt = stmt.where(Paper.venue.ilike(f"%{venue_contains}%"))
    if not force:
        stmt = stmt.where(~exists().where(VerosScore.paper_id == Paper.id))
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.exec(stmt).all())


def chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def score_rows_for_batch(db: Session, paper_ids: list[str]) -> tuple[list[dict], int, int, int]:
    papers = {
        paper.id: paper
        for paper in db.exec(select(Paper).where(Paper.id.in_(paper_ids))).all()
    }
    reviews_by_paper: dict[str, list[Review]] = defaultdict(list)
    for review in db.exec(select(Review).where(Review.paper_id.in_(paper_ids))).all():
        reviews_by_paper[review.paper_id].append(review)

    scored_rows: list[dict] = []
    insufficient = 0
    failed = 0
    for paper_id in paper_ids:
        paper = papers.get(paper_id)
        if paper is None:
            failed += 1
            continue

        review_rows = reviews_by_paper.get(paper_id, [])
        signals = [
            ReviewSignal(
                rating=float(review.rating),
                confidence=float(review.confidence) if review.confidence is not None else 3.0,
            )
            for review in review_rows
            if review.rating is not None
        ]
        rating_scale_max = rating_scale_max_for_paper(paper)
        result = compute_score(
            signals,
            acceptance=paper.acceptance,
            rating_scale_max=rating_scale_max,
        )
        if result.status != "ok" or result.score is None:
            insufficient += 1
            continue

        breakdown = {
            **result.breakdown,
            "consensus_strength": result.consensus_strength,
            "rating_scale_max": rating_scale_max,
        }
        if is_iclr_2025_paper(paper):
            breakdown.update(iclr_section_breakdown(review_rows))
        elif is_neurips_2025_paper(paper):
            breakdown.update(neurips_section_breakdown(review_rows))

        scored_rows.append(
            {
                "paper_id": paper_id,
                "score": result.score,
                "grade": result.grade,
                "verdict": result.verdict,
                "breakdown": breakdown,
                "computed_at": datetime.now(UTC),
            }
        )

    return scored_rows, len(scored_rows), insufficient, failed


def upsert_score_rows(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(VerosScore).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[VerosScore.__table__.c.paper_id],
        set_={
            "score": stmt.excluded.score,
            "grade": stmt.excluded.grade,
            "verdict": stmt.excluded.verdict,
            "breakdown": stmt.excluded.breakdown,
            "computed_at": stmt.excluded.computed_at,
        },
    )
    db.exec(stmt)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing Veros scores for already-imported papers."
    )
    parser.add_argument("--year", type=int, default=None, help="Only score papers from this year.")
    parser.add_argument(
        "--venue-contains",
        default=None,
        help="Only score papers whose venue contains this text, case-insensitive.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum papers to score.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Number of papers to score per database transaction.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Seconds to sleep after each batch commit.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=30_000,
        help="Postgres statement timeout for each scoring session.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rescore matching papers even if they already have a Veros score.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive.")
    engine = make_engine()
    with Session(engine) as db:
        paper_ids = matching_paper_ids(
            db,
            year=args.year,
            venue_contains=args.venue_contains,
            force=args.force,
            limit=args.limit,
        )

    stats = ScoreStats()
    print(f"Found {len(paper_ids)} paper(s) to score.", flush=True)
    with Session(engine) as db:
        db.execute(sa_text(f"SET statement_timeout = {args.statement_timeout_ms}"))
        db.execute(sa_text("SET idle_in_transaction_session_timeout = 60000"))
        for batch in chunks(paper_ids, args.batch_size):
            try:
                rows, scored, insufficient, failed = score_rows_for_batch(db, batch)
                upsert_score_rows(db, rows)
                db.commit()
            except Exception as exc:
                db.rollback()
                stats.seen += len(batch)
                stats.failed += len(batch)
                print(f"Failed scoring batch starting at {batch[0]}: {exc}", flush=True)
            else:
                stats.seen += len(batch)
                stats.scored += scored
                stats.insufficient += insufficient
                stats.failed += failed

            print(
                "Progress: "
                f"seen={stats.seen}, "
                f"scored={stats.scored}, "
                f"insufficient={stats.insufficient}, "
                f"failed={stats.failed}",
                flush=True,
            )
            if args.delay:
                time.sleep(args.delay)

    print(
        "Finished score backfill: "
        f"seen={stats.seen}, "
        f"scored={stats.scored}, "
        f"insufficient={stats.insufficient}, "
        f"failed={stats.failed}",
        flush=True,
    )


if __name__ == "__main__":
    main()
