from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.openreview_client import (
    FetchedPaper,
    FetchedReview,
    build_client,
    fetch_paper_and_reviews,
)

DecisionFilter = str
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "openreview_venue_reviews.jsonl"


def _content_value(content: dict[str, Any], key: str) -> Any:
    raw = content.get(key)
    if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
        return raw["value"]
    return raw


def _content_from_note(note: Any) -> dict[str, Any]:
    content = getattr(note, "content", {}) or {}
    return content if isinstance(content, dict) else {}


def _invitation_names(note: Any) -> list[str]:
    invitations = getattr(note, "invitations", None)
    if invitations:
        return [str(invitation) for invitation in invitations]
    invitation = getattr(note, "invitation", None)
    return [str(invitation)] if invitation else []


def _venue_from_note(note: Any) -> str | None:
    content = _content_from_note(note)
    for key in ("venueid", "venue"):
        value = _content_value(content, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    domain = getattr(note, "domain", None)
    return domain if isinstance(domain, str) else None


def _title_from_note(note: Any) -> str:
    title = _content_value(_content_from_note(note), "title")
    return title.strip() if isinstance(title, str) else ""


def _decision_text_from_note(note: Any) -> str:
    content = _content_from_note(note)
    values = [
        _content_value(content, key)
        for key in ("venue", "decision", "recommendation", "Decision")
    ]
    return " ".join(value for value in values if isinstance(value, str)).strip().casefold()


def _matches_venue(note: Any, venue: str) -> bool:
    domain = getattr(note, "domain", None)
    if isinstance(domain, str) and domain == venue:
        return True
    if _venue_from_note(note) == venue:
        return True
    return any(inv == venue or inv.startswith(f"{venue}/") for inv in _invitation_names(note))


def _matches_decision(note: Any, decision: DecisionFilter) -> bool:
    if decision == "all":
        return True

    text = _decision_text_from_note(note)
    is_rejected = any(word in text for word in ("reject", "withdraw", "desk reject"))
    is_accepted = (
        not is_rejected
        and (
            "accept" in text
            or "poster" in text
            or "oral" in text
            or "spotlight" in text
            or "notable" in text
        )
    )
    if decision == "accepted":
        return is_accepted
    if decision == "rejected":
        return is_rejected
    return True


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _read_processed_ids(output: Path) -> set[str]:
    if not output.exists():
        return set()

    processed: set[str] = set()
    with output.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            paper_id = payload.get("paper", {}).get("id")
            if isinstance(paper_id, str):
                processed.add(paper_id)
    return processed


def _write_jsonl(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n")


def _paper_payload(paper: FetchedPaper) -> dict[str, Any]:
    return {
        **asdict(paper),
        "url": f"https://openreview.net/forum?id={paper.id}",
    }


def _review_payload(review: FetchedReview) -> dict[str, Any]:
    return asdict(review)


def fetch_submissions(client: Any, venue: str, decision: DecisionFilter) -> list[Any]:
    notes: list[Any] = []
    for params in (
        {"invitation": f"{venue}/-/Submission"},
        {"invitation": f"{venue}/-/Post_Submission"},
        {"content": {"venueid": venue}},
    ):
        try:
            if hasattr(client, "get_all_notes"):
                notes.extend(client.get_all_notes(**params))
            else:
                notes.extend(client.get_notes(limit=1000, **params))
        except Exception as exc:
            print(f"OpenReview lookup skipped for {params}: {type(exc).__name__}: {exc}")

    seen: set[str] = set()
    submissions: list[Any] = []
    for note in notes:
        note_id = getattr(note, "id", None)
        if (
            not note_id
            or note_id in seen
            or not _matches_venue(note, venue)
            or not _matches_decision(note, decision)
            or not _title_from_note(note)
        ):
            continue
        seen.add(str(note_id))
        submissions.append(note)

    submissions.sort(key=lambda note: (getattr(note, "number", 0) or 0, _title_from_note(note)))
    return submissions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch OpenReview venue papers/reviews into a local JSONL file."
    )
    parser.add_argument("--venue", required=True, help="OpenReview venue id.")
    parser.add_argument(
        "--decision",
        choices=("all", "accepted", "rejected"),
        default="accepted",
        help="Filter submissions by decision status. Defaults to accepted.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSONL output path. Defaults to {DEFAULT_OUTPUT}.",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of new papers to fetch.")
    parser.add_argument("--start-after", help="Skip papers until after this OpenReview forum id.")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between paper fetches.")
    parser.add_argument("--no-resume", action="store_true", help="Do not skip existing JSONL rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        raise ValueError("--delay cannot be negative.")

    settings = get_settings()
    client = build_client(
        "v2",
        username=settings.openreview_username or None,
        password=settings.openreview_password or None,
    )
    submissions = fetch_submissions(client, args.venue, args.decision)
    processed_ids = set() if args.no_resume else _read_processed_ids(args.output)
    print(
        f"Found {len(submissions)} OpenReview submissions for {args.venue} "
        f"(decision={args.decision})."
    )
    print(f"Loaded {len(processed_ids)} existing local row(s) from {args.output}.")

    seen_start = args.start_after is None
    fetched = 0
    skipped = 0
    failed = 0
    for note in submissions:
        note_id = str(note.id)
        if not seen_start:
            skipped += 1
            seen_start = note_id == args.start_after
            continue
        if note_id in processed_ids:
            skipped += 1
            continue
        if args.limit is not None and fetched >= args.limit:
            break

        try:
            paper, reviews = fetch_paper_and_reviews(
                note_id,
                username=settings.openreview_username or None,
                password=settings.openreview_password or None,
            )
            payload = {
                "paper": _paper_payload(paper),
                "review_count": len(reviews),
                "reviews": [_review_payload(review) for review in reviews],
            }
            _write_jsonl(args.output, payload)
            processed_ids.add(note_id)
            fetched += 1
            print(f"[{fetched}] {note_id}: {paper.title} ({len(reviews)} reviews)", flush=True)
        except Exception as exc:
            failed += 1
            print(f"FAILED {note_id}: {type(exc).__name__}: {exc}", flush=True)

        if args.delay:
            time.sleep(args.delay)

    print(f"Done. fetched={fetched}, skipped={skipped}, failed={failed}, output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
