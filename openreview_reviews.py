#!/usr/bin/env python3
"""Fetch official reviews for a selected OpenReview paper.

Install the dependency first:
    python -m pip install openreview-py

Examples:
    python openreview_reviews.py "https://openreview.net/forum?id=abc123"
    python openreview_reviews.py abc123 --format markdown --output reviews.md

Some venues require authentication before reviews are visible:
    python openreview_reviews.py abc123 --username you@example.com

Older venues may still use OpenReview API V1:
    python openreview_reviews.py abc123 --api-version v1 --username you@example.com
"""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    import openreview
except ImportError:  # pragma: no cover - only hit before dependency install
    print(
        "Missing dependency: openreview-py\n"
        "Install it with: python -m pip install openreview-py",
        file=sys.stderr,
    )
    raise SystemExit(1)


REVIEW_INVITATION_PATTERN = re.compile(
    r"(^|/)(Official_Review|Review)$", re.IGNORECASE
)
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Review:
    id: str
    invitation: str | None
    signatures: list[str]
    created: str | None
    modified: str | None
    content: dict[str, Any]


@dataclass(frozen=True)
class ReviewScore:
    confidence_weighted_rating: float | None
    average_rating: float | None
    average_confidence: float | None
    scored_review_count: int
    skipped_review_count: int


def parse_forum_id(value: str) -> str:
    """Accept either a raw OpenReview forum id or a forum URL."""
    parsed = urlparse(value)
    if parsed.netloc:
        query_id = parse_qs(parsed.query).get("id", [None])[0]
        if query_id:
            return query_id

    return value.strip()


def build_client(
    api_version: str, username: str | None, password: str | None
) -> Any:
    """Create an OpenReview client using the requested API version."""
    if api_version == "v1":
        client_class = openreview.Client
        client_kwargs: dict[str, str] = {"baseurl": "https://api.openreview.net"}
    else:
        client_class = openreview.api.OpenReviewClient
        client_kwargs = {"baseurl": "https://api2.openreview.net"}

    if username:
        client_kwargs["username"] = username
        client_kwargs["password"] = password or getpass.getpass("OpenReview password: ")

    return client_class(**client_kwargs)


def timestamp_to_iso(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None

    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def normalize_content(content: dict[str, Any]) -> dict[str, Any]:
    """Flatten OpenReview content values while preserving unknown fields."""
    normalized: dict[str, Any] = {}
    for key, value in content.items():
        if isinstance(value, dict) and set(value.keys()) == {"value"}:
            normalized[key] = value["value"]
        else:
            normalized[key] = value
    return normalized


def invitation_names(note: Any) -> list[str]:
    invitations = getattr(note, "invitations", None)
    if invitations:
        return list(invitations)

    invitation = getattr(note, "invitation", None)
    return [invitation] if invitation else []


def is_review_invitation(invitation: str | None) -> bool:
    return bool(invitation and REVIEW_INVITATION_PATTERN.search(invitation))


def looks_like_official_review(note: Any) -> bool:
    invitations = invitation_names(note)
    if any(is_review_invitation(invitation) for invitation in invitations):
        return True

    return False


def note_to_review(note: Any) -> Review:
    invitations = invitation_names(note)
    return Review(
        id=note.id,
        invitation=invitations[0] if invitations else None,
        signatures=list(getattr(note, "signatures", []) or []),
        created=timestamp_to_iso(getattr(note, "cdate", None)),
        modified=timestamp_to_iso(getattr(note, "mdate", None)),
        content=normalize_content(getattr(note, "content", {}) or {}),
    )


def parse_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = NUMBER_PATTERN.search(value)
        if match:
            return float(match.group())

    return None


def calculate_review_score(reviews: list[Review]) -> ReviewScore:
    scored_reviews: list[tuple[float, float]] = []
    skipped_review_count = 0

    for review in reviews:
        rating = parse_number(review.content.get("rating"))
        confidence = parse_number(review.content.get("confidence"))
        if rating is None or confidence is None or confidence <= 0:
            skipped_review_count += 1
            continue

        scored_reviews.append((rating, confidence))

    if not scored_reviews:
        return ReviewScore(
            confidence_weighted_rating=None,
            average_rating=None,
            average_confidence=None,
            scored_review_count=0,
            skipped_review_count=skipped_review_count,
        )

    rating_total = sum(rating for rating, _ in scored_reviews)
    confidence_total = sum(confidence for _, confidence in scored_reviews)
    weighted_total = sum(rating * confidence for rating, confidence in scored_reviews)

    return ReviewScore(
        confidence_weighted_rating=weighted_total / confidence_total,
        average_rating=rating_total / len(scored_reviews),
        average_confidence=confidence_total / len(scored_reviews),
        scored_review_count=len(scored_reviews),
        skipped_review_count=skipped_review_count,
    )


def fetch_reviews(client: Any, forum_id: str) -> tuple[Any, list[Review]]:
    paper = client.get_note(id=forum_id)
    notes = client.get_notes(forum=forum_id)
    reviews = [
        note_to_review(note)
        for note in notes
        if getattr(note, "id", None) != forum_id and looks_like_official_review(note)
    ]
    reviews.sort(key=lambda review: review.created or "")
    return paper, reviews


def paper_title(paper: Any) -> str:
    content = normalize_content(getattr(paper, "content", {}) or {})
    title = content.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return paper.id


def format_json(paper: Any, reviews: list[Review]) -> str:
    score = calculate_review_score(reviews)
    payload = {
        "paper": {
            "id": paper.id,
            "title": paper_title(paper),
            "url": f"https://openreview.net/forum?id={paper.id}",
        },
        "score": score.__dict__,
        "reviews": [review.__dict__ for review in reviews],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def format_markdown(paper: Any, reviews: list[Review]) -> str:
    score = calculate_review_score(reviews)
    lines = [
        f"# Reviews for {paper_title(paper)}",
        "",
        f"Paper: https://openreview.net/forum?id={paper.id}",
        "",
        "## Score",
        "",
    ]

    if score.confidence_weighted_rating is None:
        lines.extend(
            [
                "No confidence-weighted score could be computed from visible official reviews.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- confidence-weighted rating: {score.confidence_weighted_rating:.2f}",
                f"- simple average rating: {score.average_rating:.2f}",
                f"- average confidence: {score.average_confidence:.2f}",
                f"- scored reviews: {score.scored_review_count}",
                f"- skipped reviews: {score.skipped_review_count}",
                "",
            ]
        )

    if not reviews:
        lines.append("No official reviews were found or visible to this account.")
        return "\n".join(lines)

    for index, review in enumerate(reviews, start=1):
        lines.extend(
            [
                f"## Review {index}",
                "",
                f"- id: `{review.id}`",
                f"- invitation: `{review.invitation or 'unknown'}`",
                f"- signatures: {', '.join(f'`{sig}`' for sig in review.signatures) or '`unknown`'}",
                f"- created: {review.created or 'unknown'}",
                "",
            ]
        )
        for key, value in review.content.items():
            lines.extend([f"### {key}", "", str(value), ""])

    return "\n".join(lines).rstrip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve visible official reviews for an OpenReview paper."
    )
    parser.add_argument(
        "paper",
        nargs="?",
        help="OpenReview forum id or URL, for example https://openreview.net/forum?id=abc123",
    )
    parser.add_argument(
        "--username",
        help="OpenReview username/email. Omit for public papers and reviews.",
    )
    parser.add_argument(
        "--password",
        help="OpenReview password. If omitted with --username, you will be prompted.",
    )
    parser.add_argument(
        "--api-version",
        choices=("v1", "v2"),
        default="v2",
        help="OpenReview API version to use. Defaults to v2.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format. Defaults to json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. Defaults to stdout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_paper = args.paper or input("OpenReview paper URL or forum id: ").strip()
    forum_id = parse_forum_id(selected_paper)

    client = build_client(args.api_version, args.username, args.password)
    paper, reviews = fetch_reviews(client, forum_id)

    output = (
        format_markdown(paper, reviews)
        if args.format == "markdown"
        else format_json(paper, reviews)
    )

    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
