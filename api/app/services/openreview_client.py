"""Wrapper around openreview-py that abstracts v1/v2 differences.

Lifted from the standalone CLI at repo root (`openreview_reviews.py`). Preserve
the v1/v2 branching, content-flattening, and review-detection heuristics — they
were established against real venues with non-standard invitation names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import openreview

REVIEW_INVITATION_PATTERN = re.compile(
    r"(^|/)(Official_Review|Review|.*Review)$", re.IGNORECASE
)
DECISION_INVITATION_PATTERN = re.compile(r"(^|/).*Decision$", re.IGNORECASE)


@dataclass(frozen=True)
class FetchedReview:
    id: str
    invitation: str | None
    signatures: list[str]
    created: datetime | None
    modified: datetime | None
    content: dict[str, Any]


@dataclass(frozen=True)
class FetchedPaper:
    id: str
    title: str
    authors: list[str]
    venue: str | None
    abstract: str | None
    publication_date: datetime | None
    acceptance: str | None  # 'oral' | 'poster' | 'reject' | None
    raw_content: dict[str, Any]


def parse_forum_id(value: str) -> str:
    """Accept either a raw OpenReview forum id or a forum URL."""
    parsed = urlparse(value)
    if parsed.netloc:
        query_id = parse_qs(parsed.query).get("id", [None])[0]
        if query_id:
            return query_id
    return value.strip()


def build_client(
    api_version: str = "v2",
    username: str | None = None,
    password: str | None = None,
) -> Any:
    if api_version == "v1":
        client_class = openreview.Client
        kwargs: dict[str, str] = {"baseurl": "https://api.openreview.net"}
    else:
        client_class = openreview.api.OpenReviewClient
        kwargs = {"baseurl": "https://api2.openreview.net"}
    if username:
        kwargs["username"] = username
        kwargs["password"] = password or ""
    return client_class(**kwargs)


def _ts_to_dt(ts_ms: int | None) -> datetime | None:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC)


def _normalize_content(content: dict[str, Any]) -> dict[str, Any]:
    """Flatten OpenReview v2 content where each value is wrapped as {'value': ...}."""
    normalized: dict[str, Any] = {}
    for key, raw in content.items():
        if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
            normalized[key] = raw["value"]
        else:
            normalized[key] = raw
    return normalized


def _invitations(note: Any) -> list[str]:
    invitations = getattr(note, "invitations", None)
    if invitations:
        return list(invitations)
    invitation = getattr(note, "invitation", None)
    return [invitation] if invitation else []


def _looks_like_official_review(note: Any) -> bool:
    invitations = _invitations(note)
    if any(REVIEW_INVITATION_PATTERN.search(inv) for inv in invitations):
        return True
    content = _normalize_content(getattr(note, "content", {}) or {})
    reviewish = {"review", "summary", "strengths", "weaknesses", "rating"}
    return bool(reviewish.intersection(content.keys()))


def _looks_like_decision(note: Any) -> bool:
    return any(DECISION_INVITATION_PATTERN.search(inv) for inv in _invitations(note))


def _note_to_review(note: Any) -> FetchedReview:
    invitations = _invitations(note)
    return FetchedReview(
        id=note.id,
        invitation=invitations[0] if invitations else None,
        signatures=list(getattr(note, "signatures", []) or []),
        created=_ts_to_dt(getattr(note, "cdate", None)),
        modified=_ts_to_dt(getattr(note, "mdate", None)),
        content=_normalize_content(getattr(note, "content", {}) or {}),
    )


def _extract_acceptance(notes: list[Any]) -> str | None:
    """Look for a Decision note and infer oral/poster/reject from its recommendation."""
    for note in notes:
        if not _looks_like_decision(note):
            continue
        content = _normalize_content(getattr(note, "content", {}) or {})
        decision = (
            content.get("decision")
            or content.get("recommendation")
            or content.get("Decision")
            or ""
        )
        if not isinstance(decision, str):
            continue
        text = decision.lower()
        if "oral" in text:
            return "oral"
        if "spotlight" in text or "highlight" in text:
            return "oral"
        if "accept" in text or "poster" in text:
            return "poster"
        if "reject" in text:
            return "reject"
    return None


def _to_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _venue(content: dict[str, Any]) -> str | None:
    for key in ("venue", "venueid"):
        v = content.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _build_paper(note: Any) -> FetchedPaper:
    content = _normalize_content(getattr(note, "content", {}) or {})
    title = content.get("title")
    if not isinstance(title, str) or not title.strip():
        title = note.id
    return FetchedPaper(
        id=note.id,
        title=title.strip(),
        authors=_to_str_list(content.get("authors")),
        venue=_venue(content),
        abstract=(content.get("abstract") if isinstance(content.get("abstract"), str) else None),
        publication_date=_ts_to_dt(getattr(note, "pdate", None)),
        acceptance=None,  # filled by caller after seeing all notes
        raw_content=content,
    )


def _is_not_found(exc: Exception) -> bool:
    """Detect a NotFoundError from openreview-py without importing internal modules."""
    msg = str(exc)
    return (
        "NotFoundError" in msg
        or "'status': 404" in msg
        or '"status": 404' in msg
    )


def _fetch_paper_and_reviews_at(
    forum_id: str,
    *,
    api_version: str,
    username: str | None,
    password: str | None,
) -> tuple[FetchedPaper, list[FetchedReview]]:
    client = build_client(api_version, username, password)
    paper_note = client.get_note(id=forum_id)
    forum_notes = client.get_notes(forum=forum_id)

    paper = _build_paper(paper_note)
    paper = FetchedPaper(
        id=paper.id,
        title=paper.title,
        authors=paper.authors,
        venue=paper.venue,
        abstract=paper.abstract,
        publication_date=paper.publication_date,
        acceptance=_extract_acceptance(forum_notes),
        raw_content=paper.raw_content,
    )

    reviews = [
        _note_to_review(n)
        for n in forum_notes
        if getattr(n, "id", None) != forum_id and _looks_like_official_review(n)
    ]
    reviews.sort(key=lambda r: r.created or datetime.min.replace(tzinfo=UTC))
    return paper, reviews


def fetch_paper_and_reviews(
    forum_id: str,
    *,
    api_version: str = "v2",
    username: str | None = None,
    password: str | None = None,
) -> tuple[FetchedPaper, list[FetchedReview]]:
    """Return (paper, reviews) for the given forum id.

    Tries the v2 API first (covers ~all venues from 2023+). Older venues live on
    v1 only — if v2 returns NotFound, fall back to v1 before giving up.

    Caller should consider an empty review list a soft failure (auth-gated venue
    or paper not yet reviewed) — not an exception.
    """
    try:
        return _fetch_paper_and_reviews_at(
            forum_id,
            api_version=api_version,
            username=username,
            password=password,
        )
    except Exception as exc:
        if api_version == "v2" and _is_not_found(exc):
            return _fetch_paper_and_reviews_at(
                forum_id,
                api_version="v1",
                username=username,
                password=password,
            )
        raise
