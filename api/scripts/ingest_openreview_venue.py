from __future__ import annotations

import argparse
import signal
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import Paper
from app.db.session import get_engine
from app.services.ingest import ingest_paper
from app.services.openreview_client import build_client


@dataclass(frozen=True)
class OpenReviewSubmission:
    id: str
    title: str


class PaperTimeoutError(TimeoutError):
    pass


@contextmanager
def paper_timeout(seconds: int):
    if seconds <= 0:
        yield
        return

    def _raise_timeout(_signum: int, _frame: Any) -> None:
        raise PaperTimeoutError(f"paper ingest exceeded {seconds}s")

    previous_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _content_value(content: dict[str, Any], key: str) -> Any:
    raw = content.get(key)
    if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
        return raw["value"]
    return raw


def _invitation_names(note: Any) -> list[str]:
    invitations = getattr(note, "invitations", None)
    if invitations:
        return [str(invitation) for invitation in invitations]
    invitation = getattr(note, "invitation", None)
    return [str(invitation)] if invitation else []


def _venue_from_note(note: Any) -> str | None:
    content = getattr(note, "content", {}) or {}
    if not isinstance(content, dict):
        return getattr(note, "domain", None)
    for key in ("venueid", "venue"):
        value = _content_value(content, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return getattr(note, "domain", None)


def _title_from_note(note: Any) -> str:
    content = getattr(note, "content", {}) or {}
    if not isinstance(content, dict):
        return ""
    title = _content_value(content, "title")
    return title.strip() if isinstance(title, str) else ""


def _note_matches_venue(note: Any, venue: str) -> bool:
    domain = getattr(note, "domain", None)
    if isinstance(domain, str) and domain == venue:
        return True
    if _venue_from_note(note) == venue:
        return True
    return any(inv == venue or inv.startswith(f"{venue}/") for inv in _invitation_names(note))


def fetch_openreview_submissions(client: Any, venue: str) -> list[OpenReviewSubmission]:
    notes: list[Any] = []
    attempts: list[dict[str, Any]] = [
        {"invitation": f"{venue}/-/Submission"},
        {"invitation": f"{venue}/-/Post_Submission"},
        {"content": {"venueid": venue}},
    ]

    for params in attempts:
        try:
            if hasattr(client, "get_all_notes"):
                notes.extend(client.get_all_notes(**params))
            else:
                notes.extend(client.get_notes(limit=1000, **params))
        except Exception as exc:
            print(f"OpenReview lookup skipped for {params}: {type(exc).__name__}: {exc}")

    submissions: list[OpenReviewSubmission] = []
    seen_ids: set[str] = set()
    for note in notes:
        note_id = getattr(note, "id", None)
        if not note_id or note_id in seen_ids or not _note_matches_venue(note, venue):
            continue
        title = _title_from_note(note)
        if not title:
            continue
        seen_ids.add(str(note_id))
        submissions.append(OpenReviewSubmission(id=str(note_id), title=title))

    submissions.sort(key=lambda submission: submission.title.casefold())
    return submissions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch OpenReview venue submissions and ingest them into the Veros database."
    )
    parser.add_argument(
        "--venue",
        required=True,
        help="OpenReview venue id, for example ICLR.cc/2025/Conference.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of new papers to ingest. Use this for a small test run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch papers that already exist in the database.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to sleep between paper ingests. Defaults to 0.5.",
    )
    parser.add_argument(
        "--start-after",
        help="Skip submissions until after this OpenReview forum id.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching submissions without writing to the database.",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Ingest papers and scores only; do not call the LLM analysis step.",
    )
    parser.add_argument(
        "--paper-timeout",
        type=int,
        default=180,
        help="Maximum seconds to spend on one paper before skipping it. Use 0 to disable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.delay < 0:
        raise ValueError("--delay cannot be negative.")

    settings = get_settings()
    client = build_client(
        api_version="v2",
        username=settings.openreview_username or None,
        password=settings.openreview_password or None,
    )
    submissions = fetch_openreview_submissions(client, args.venue)
    print(f"Found {len(submissions)} OpenReview submissions for {args.venue}.")

    seen_start = args.start_after is None
    ingested = 0
    skipped_existing = 0
    skipped_before_start = 0
    failed = 0
    existing_paper_ids: set[str] = set()
    if not args.force:
        with Session(get_engine()) as db:
            existing_paper_ids = set(db.exec(select(Paper.id)).all())
        print(f"Loaded {len(existing_paper_ids)} existing paper id(s) for skip checks.")

    for submission in submissions:
        if not seen_start:
            skipped_before_start += 1
            seen_start = submission.id == args.start_after
            continue

        if args.limit is not None and ingested >= args.limit:
            break

        if submission.id in existing_paper_ids:
            skipped_existing += 1
            continue

        if args.dry_run:
            print(f"would ingest {submission.id}: {submission.title}")
            ingested += 1
            continue

        print(f"ingesting {submission.id}: {submission.title}", flush=True)
        try:
            with Session(get_engine()) as db, paper_timeout(args.paper_timeout):
                result = ingest_paper(
                    db,
                    submission.id,
                    run_analysis=not args.skip_analysis,
                )
            existing_paper_ids.add(submission.id)
            ingested += 1
            print(
                f"[{ingested}] {result['paper_id']}: "
                f"{result['title']} "
                f"(reviews={result['review_count']}, score={result['score']}, "
                f"analysis={result['analyze_status']})",
                flush=True,
            )
        except Exception as exc:
            failed += 1
            print(f"FAILED {submission.id}: {type(exc).__name__}: {exc}", flush=True)

        if args.delay:
            time.sleep(args.delay)

    print(
        "Done: "
        f"ingested={ingested}, "
        f"skipped_existing={skipped_existing}, "
        f"skipped_before_start={skipped_before_start}, "
        f"failed={failed}, "
        f"venue={args.venue}"
    )


if __name__ == "__main__":
    main()
