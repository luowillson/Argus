#!/usr/bin/env python3
"""Parse reviews for every accepted ICLR 2025 paper.

The script writes one JSON object per accepted paper to a JSONL file. Each row
contains paper metadata, the standardized score summary, and the parsed review
contents. It is resumable by default: if the output file already contains a
paper id, that paper is skipped on later runs.

Examples:
    python scripts/parse_iclr_2025_accepted.py --limit 5
    python scripts/parse_iclr_2025_accepted.py --delay 1.0 --output data/iclr_2025_accepted_reviews.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.formatting import score_summary_payload
from scoring.openreview_client import (  # noqa: E402
    build_client,
    fetch_reviews,
    normalize_content,
)
from scoring.storage import (  # noqa: E402
    DEFAULT_SCORE_CACHE_PATH,
    DEFAULT_SCORE_DB_PATH,
    save_score_payload,
)


CONFERENCE = "ICLR.cc/2025/Conference"
SUBMISSION_INVITATION = f"{CONFERENCE}/-/Submission"
DEFAULT_OUTPUT = ROOT / "data" / "iclr_2025_accepted_reviews.jsonl"
DEFAULT_DELAY_SECONDS = 0.5
ACCEPTED_VENUES = {
    "iclr 2025 oral",
    "iclr 2025 spotlight",
    "iclr 2025 poster",
    "iclr 2025 notable-top-25%",
}


def is_accepted_iclr_2025_submission(note: Any) -> bool:
    content = normalize_content(getattr(note, "content", {}) or {})
    venueid = content.get("venueid")
    venue = content.get("venue")
    if venueid != CONFERENCE:
        return False
    if not isinstance(venue, str):
        return False

    venue_text = venue.strip().lower()
    return venue_text in ACCEPTED_VENUES or (
        venue_text.startswith("iclr 2025") and "reject" not in venue_text
    )


def paper_metadata(note: Any) -> dict[str, Any]:
    content = normalize_content(getattr(note, "content", {}) or {})
    return {
        "id": note.id,
        "title": content.get("title"),
        "venue": content.get("venue"),
        "venueid": content.get("venueid"),
        "url": f"https://openreview.net/forum?id={note.id}",
        "authors": content.get("authors"),
        "authorids": content.get("authorids"),
    }


def read_processed_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()

    processed_ids: set[str] = set()
    with output_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            paper_id = payload.get("paper", {}).get("id")
            if isinstance(paper_id, str):
                processed_ids.add(paper_id)

    return processed_ids


def write_jsonl(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse every accepted ICLR 2025 paper's OpenReview reviews."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"JSONL output path. Defaults to {DEFAULT_OUTPUT}.",
    )
    parser.add_argument(
        "--score-db",
        type=Path,
        default=DEFAULT_SCORE_DB_PATH,
        help=f"Score scale database. Defaults to {DEFAULT_SCORE_DB_PATH.name}.",
    )
    parser.add_argument(
        "--score-cache",
        type=Path,
        default=DEFAULT_SCORE_CACHE_PATH,
        help=f"Paper score cache to update. Defaults to {DEFAULT_SCORE_CACHE_PATH.name}.",
    )
    parser.add_argument(
        "--username",
        help="OpenReview username/email if authenticated access is needed.",
    )
    parser.add_argument(
        "--password",
        help="OpenReview password. If omitted with --username, you will be prompted.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of accepted papers to parse, useful for testing.",
    )
    parser.add_argument(
        "--start-after",
        help="Skip accepted papers until after this paper id.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=(
            "Seconds to sleep between paper review requests. "
            f"Defaults to {DEFAULT_DELAY_SECONDS} to reduce rate-limit risk."
        ),
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip paper ids already present in the output JSONL.",
    )
    parser.add_argument(
        "--no-score-cache",
        action="store_true",
        help="Do not update paper_scores.json while parsing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        raise ValueError("--delay cannot be negative.")

    client = build_client("v2", args.username, args.password)
    submissions = client.get_all_notes(invitation=SUBMISSION_INVITATION)
    accepted_submissions = [
        note for note in submissions if is_accepted_iclr_2025_submission(note)
    ]
    accepted_submissions.sort(key=lambda note: getattr(note, "number", 0) or 0)

    processed_ids = set() if args.no_resume else read_processed_ids(args.output)
    seen_start = args.start_after is None
    parsed_count = 0
    skipped_count = 0

    print(
        f"Found {len(accepted_submissions)} accepted ICLR 2025 papers. "
        f"Sleeping {args.delay:g}s between paper requests."
    )
    for note in accepted_submissions:
        if not seen_start:
            seen_start = note.id == args.start_after
            skipped_count += 1
            continue

        if note.id in processed_ids:
            skipped_count += 1
            continue

        if args.limit is not None and parsed_count >= args.limit:
            break

        paper, reviews, scales = fetch_reviews(
            client, note.id, args.score_db, fetch_schema_scales=False
        )
        score_payload = score_summary_payload(paper, reviews, scales)
        output_payload = {
            "paper": paper_metadata(note),
            "score": score_payload,
            "review_count": len(reviews),
            "reviews": [asdict(review) for review in reviews],
        }
        write_jsonl(args.output, output_payload)

        if not args.no_score_cache:
            save_score_payload(args.score_cache, score_payload, "iclr_2025_bulk")

        parsed_count += 1
        print(
            f"[{parsed_count}] {note.id}: {output_payload['paper']['title']} "
            f"({len(reviews)} reviews)",
            flush=True,
        )

        if args.delay > 0:
            time.sleep(args.delay)

    print(
        f"Done. Parsed {parsed_count} paper(s), skipped {skipped_count}. "
        f"Output: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
