from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .formatting import build_score_summary_payload
from .models import ParsedReviewDocument, Review
from .scoring import NUMBER_PATTERN, parse_number
from .storage import load_database_scales, load_score_cache, save_score_cache


def parse_markdown_score_value(value: str) -> Any:
    stripped = value.strip()
    number = parse_number(stripped)
    if number is not None and NUMBER_PATTERN.fullmatch(stripped):
        return number

    return stripped


def parse_markdown_reviews(path: Path) -> ParsedReviewDocument:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"(?m)^# Reviews for (.+)$", text)
    id_match = re.search(r"https://openreview\.net/forum\?id=([A-Za-z0-9_-]+)", text)
    if not title_match or not id_match:
        raise ValueError(f"{path} does not look like a generated reviews Markdown file.")

    title = title_match.group(1).strip()
    forum_id = id_match.group(1)
    reviews: list[Review] = []
    review_chunks = re.split(r"(?m)^## Review \d+\s*$", text)[1:]

    for chunk in review_chunks:
        review_id_match = re.search(r"(?m)^- id: `([^`]+)`", chunk)
        invitation_match = re.search(r"(?m)^- invitation: `([^`]+)`", chunk)
        signatures_match = re.search(r"(?m)^- signatures: (.+)$", chunk)
        created_match = re.search(r"(?m)^- created: (.+)$", chunk)
        content: dict[str, Any] = {}

        for field_match in re.finditer(
            r"(?ms)^### ([^\n]+)\n\n(.*?)(?=^### |\Z)", chunk
        ):
            field = field_match.group(1).strip().lower()
            value = field_match.group(2).strip()
            content[field] = parse_markdown_score_value(value)

        signatures: list[str] = []
        if signatures_match:
            signatures = re.findall(r"`([^`]+)`", signatures_match.group(1))

        reviews.append(
            Review(
                id=review_id_match.group(1) if review_id_match else "",
                invitation=invitation_match.group(1) if invitation_match else None,
                signatures=signatures,
                created=created_match.group(1).strip() if created_match else None,
                modified=None,
                content=content,
            )
        )

    return ParsedReviewDocument(id=forum_id, title=title, reviews=reviews)


def cache_scores_from_markdown_files(
    markdown_paths: list[Path], score_db_path: Path, cache_path: Path
) -> int:
    cache = load_score_cache(cache_path)
    papers = cache.setdefault("papers", {})
    cached_count = 0

    for markdown_path in markdown_paths:
        document = parse_markdown_reviews(markdown_path)
        scales = load_database_scales(score_db_path, document.reviews)
        payload = build_score_summary_payload(
            document.id, document.title, document.reviews, scales
        )
        payload["cached_at"] = datetime.now(timezone.utc).isoformat()
        payload["source_file"] = str(markdown_path)
        papers[document.id] = payload
        cached_count += 1

    save_score_cache(cache_path, cache)
    return cached_count

