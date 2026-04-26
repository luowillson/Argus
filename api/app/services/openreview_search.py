"""Look up papers by title across OpenReview when they're not in our DB.

OpenReview's API doesn't expose a reliable title-only search, so we iterate a
configurable list of recent venues (see ``settings.openreview_search_venues``)
and pick the candidate whose normalized title best matches the query.

The matching helpers below are vendored from the standalone ``scoring`` package
so the api can import them without depending on the repo-root sibling module.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.config import get_settings
from app.services.openreview_client import build_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperCandidate:
    id: str
    title: str
    venue: str | None


@dataclass(frozen=True)
class TitleMatch:
    candidate: PaperCandidate
    similarity: float


def _normalize_content(content: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, raw in (content or {}).items():
        if isinstance(raw, dict) and set(raw.keys()) == {"value"}:
            out[key] = raw["value"]
        else:
            out[key] = raw
    return out


def _invitation_names(note: Any) -> list[str]:
    invitations = getattr(note, "invitations", None)
    if invitations:
        return list(invitations)
    invitation = getattr(note, "invitation", None)
    return [invitation] if invitation else []


def _title_from_note(note: Any) -> str:
    content = _normalize_content(getattr(note, "content", {}) or {})
    title = content.get("title")
    return title.strip() if isinstance(title, str) else ""


def _venue_from_note(note: Any) -> str | None:
    content = _normalize_content(getattr(note, "content", {}) or {})
    for key in ("venueid", "venue"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return getattr(note, "domain", None)


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _note_matches_conference(note: Any, conference: str) -> bool:
    domain = getattr(note, "domain", None)
    if isinstance(domain, str) and domain == conference:
        return True
    if _venue_from_note(note) == conference:
        return True
    return any(
        inv == conference or inv.startswith(f"{conference}/")
        for inv in _invitation_names(note)
    )


def _dedupe(notes: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for note in notes:
        nid = getattr(note, "id", None)
        if not nid or nid in seen:
            continue
        seen.add(nid)
        out.append(note)
    return out


def _title_similarity(query: str, candidate_title: str) -> float:
    a = _normalize_title(query)
    b = _normalize_title(candidate_title)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _search_venue(client: Any, title: str, conference: str, limit: int) -> list[PaperCandidate]:
    """Mirror scoring.openreview_client.search_papers_by_title for one venue."""
    notes: list[Any] = []
    attempts: list[dict[str, Any]] = [
        {"invitation": f"{conference}/-/Submission"},
        {"invitation": f"{conference}/-/Post_Submission"},
        {"content": {"venueid": conference}},
    ]
    for params in attempts:
        try:
            if hasattr(client, "get_all_notes"):
                notes.extend(client.get_all_notes(**params))
            else:
                notes.extend(client.get_notes(limit=1000, **params))
        except Exception:
            continue

    normalized_query = _normalize_title(title)
    exact = [
        n
        for n in _dedupe(notes)
        if _title_from_note(n)
        and _note_matches_conference(n, conference)
        and _normalize_title(_title_from_note(n)) == normalized_query
    ]
    pool = exact or [
        n
        for n in _dedupe(notes)
        if _title_from_note(n)
        and _note_matches_conference(n, conference)
        and normalized_query in _normalize_title(_title_from_note(n))
    ]
    pool.sort(key=lambda n: getattr(n, "cdate", 0) or 0, reverse=True)
    return [
        PaperCandidate(id=n.id, title=_title_from_note(n), venue=_venue_from_note(n))
        for n in pool[:limit]
    ]


def search_openreview_by_title(title: str, per_venue_limit: int = 5) -> list[TitleMatch]:
    """Return candidates across all configured venues, sorted by similarity desc."""
    qn = title.strip()
    if not qn:
        return []

    settings = get_settings()
    venues = settings.openreview_search_venue_list
    if not venues:
        return []

    try:
        client = build_client(
            api_version="v2",
            username=settings.openreview_username or None,
            password=settings.openreview_password or None,
        )
    except Exception:
        logger.exception("Failed to build OpenReview client for title search")
        return []

    seen_ids: set[str] = set()
    matches: list[TitleMatch] = []
    for venue in venues:
        try:
            candidates = _search_venue(client, qn, venue, per_venue_limit)
        except Exception:
            logger.warning(
                "OpenReview title search failed for venue %s", venue, exc_info=True
            )
            continue
        for candidate in candidates:
            if candidate.id in seen_ids:
                continue
            seen_ids.add(candidate.id)
            matches.append(
                TitleMatch(
                    candidate=candidate,
                    similarity=_title_similarity(qn, candidate.title),
                )
            )

    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches


def find_best_openreview_match(title: str) -> TitleMatch | None:
    """Return the top OpenReview match if its similarity clears the ingest threshold."""
    matches = search_openreview_by_title(title)
    if not matches:
        return None
    threshold = get_settings().search_openreview_ingest_threshold
    top = matches[0]
    return top if top.similarity >= threshold else None
