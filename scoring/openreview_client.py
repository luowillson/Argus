from __future__ import annotations

import getpass
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import openreview

from .models import PaperCandidate, Review, ScoreScale
from .scoring import SCORE_VALUE_FIELDS, parse_number
from .storage import load_database_scales


REVIEW_INVITATION_PATTERN = re.compile(
    r"(^|/)(Official_Review|Review)$", re.IGNORECASE
)
MIN_KEYS = {"min", "minimum", "minimumvalue", "minimum_value"}
MAX_KEYS = {"max", "maximum", "maximumvalue", "maximum_value"}
CHOICE_KEYS = {"enum", "options", "choices"}


def parse_forum_id(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc:
        query_id = parse_qs(parsed.query).get("id", [None])[0]
        if query_id:
            return query_id

    return value.strip()


def build_client(api_version: str, username: str | None, password: str | None) -> Any:
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
    return any(is_review_invitation(invitation) for invitation in invitation_names(note))


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


def title_from_note(note: Any) -> str:
    content = normalize_content(getattr(note, "content", {}) or {})
    title = content.get("title")
    return title.strip() if isinstance(title, str) else ""


def venue_from_note(note: Any) -> str | None:
    content = normalize_content(getattr(note, "content", {}) or {})
    for key in ("venueid", "venue"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return getattr(note, "domain", None)


def normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def note_matches_conference(note: Any, conference: str | None) -> bool:
    if not conference:
        return True

    conference = conference.strip()
    if not conference:
        return True

    domain = getattr(note, "domain", None)
    if isinstance(domain, str) and domain == conference:
        return True

    venue = venue_from_note(note)
    if venue == conference:
        return True

    return any(
        invitation == conference or invitation.startswith(f"{conference}/")
        for invitation in invitation_names(note)
    )


def note_to_candidate(note: Any) -> PaperCandidate:
    return PaperCandidate(
        id=note.id,
        title=title_from_note(note),
        venue=venue_from_note(note),
        domain=getattr(note, "domain", None),
        invitations=invitation_names(note),
        created=timestamp_to_iso(getattr(note, "cdate", None)),
    )


def dedupe_candidates(notes: list[Any]) -> list[Any]:
    seen_ids: set[str] = set()
    deduped: list[Any] = []
    for note in notes:
        note_id = getattr(note, "id", None)
        if not note_id or note_id in seen_ids:
            continue
        seen_ids.add(note_id)
        deduped.append(note)

    return deduped


def search_papers_by_title(
    client: Any, title: str, conference: str | None, limit: int
) -> list[PaperCandidate]:
    query_title = title.strip()
    if not query_title:
        raise ValueError("--title cannot be empty.")
    if not conference:
        raise ValueError(
            "--conference is required with --title because OpenReview does not "
            "support reliable title-only search."
        )

    notes: list[Any] = []
    search_attempts: list[dict[str, Any]] = [
        {"invitation": f"{conference}/-/Submission"},
        {"invitation": f"{conference}/-/Post_Submission"},
        {"content": {"venueid": conference}},
    ]

    for params in search_attempts:
        try:
            if hasattr(client, "get_all_notes"):
                notes.extend(client.get_all_notes(**params))
            else:
                notes.extend(client.get_notes(limit=1000, **params))
        except Exception:
            continue

    normalized_query = normalize_title(query_title)
    candidates = [
        note
        for note in dedupe_candidates(notes)
        if title_from_note(note)
        and note_matches_conference(note, conference)
        and normalize_title(title_from_note(note)) == normalized_query
    ]

    if not candidates:
        candidates = [
            note
            for note in dedupe_candidates(notes)
            if title_from_note(note)
            and note_matches_conference(note, conference)
            and normalized_query in normalize_title(title_from_note(note))
        ]

    candidates.sort(key=lambda note: getattr(note, "cdate", 0) or 0, reverse=True)
    return [note_to_candidate(note) for note in candidates[:limit]]


def resolve_forum_id_from_title(
    client: Any,
    title: str,
    conference: str | None,
    match_index: int,
    search_limit: int,
) -> str:
    candidates = search_papers_by_title(client, title, conference, search_limit)
    if not candidates:
        venue_hint = f" in {conference}" if conference else ""
        raise ValueError(f"No OpenReview paper found for title '{title}'{venue_hint}.")
    if match_index < 1 or match_index > len(candidates):
        candidate_lines = "\n".join(
            f"{index}. {candidate.title} [{candidate.id}]"
            for index, candidate in enumerate(candidates, start=1)
        )
        raise ValueError(
            f"--match-index must be between 1 and {len(candidates)}.\n{candidate_lines}"
        )

    return candidates[match_index - 1].id


def object_to_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: object_to_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [object_to_dict(item) for item in value]
    if hasattr(value, "to_json"):
        return object_to_dict(value.to_json())
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: object_to_dict(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }

    return value


def normalize_schema_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def collect_choice_numbers(value: Any) -> list[float]:
    numbers: list[float] = []
    if isinstance(value, dict):
        for item in value.values():
            numbers.extend(collect_choice_numbers(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                label = item.get("value") or item.get("label") or item.get("description")
                number = parse_number(label)
            else:
                number = parse_number(item)
            if number is not None:
                numbers.append(number)

    return numbers


def collect_numeric_bounds(value: Any) -> tuple[float | None, float | None]:
    found_min: float | None = None
    found_max: float | None = None

    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = normalize_schema_key(key)
            number = parse_number(item)
            if normalized_key in MIN_KEYS and number is not None:
                found_min = number if found_min is None else min(found_min, number)
            elif normalized_key in MAX_KEYS and number is not None:
                found_max = number if found_max is None else max(found_max, number)

            child_min, child_max = collect_numeric_bounds(item)
            if child_min is not None:
                found_min = child_min if found_min is None else min(found_min, child_min)
            if child_max is not None:
                found_max = child_max if found_max is None else max(found_max, child_max)
    elif isinstance(value, list) and len(value) == 2:
        first = parse_number(value[0])
        second = parse_number(value[1])
        if first is not None and second is not None:
            found_min = min(first, second)
            found_max = max(first, second)

    return found_min, found_max


def infer_scale_from_schema(field_schema: Any, source: str) -> ScoreScale | None:
    minimum, maximum = collect_numeric_bounds(field_schema)
    if minimum is not None and maximum is not None and minimum < maximum:
        return ScoreScale(min=minimum, max=maximum, source=source)

    choice_numbers = collect_choice_numbers(field_schema)
    if len(choice_numbers) >= 2:
        minimum = min(choice_numbers)
        maximum = max(choice_numbers)
        if minimum < maximum:
            return ScoreScale(min=minimum, max=maximum, source=source)

    return None


def extract_scales_from_schema(schema: Any, source: str) -> dict[str, ScoreScale]:
    scales: dict[str, ScoreScale] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = key.lower()
                if normalized_key in SCORE_VALUE_FIELDS and normalized_key not in scales:
                    scale = infer_scale_from_schema(item, source)
                    if scale:
                        scales[normalized_key] = scale
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(schema)
    return scales


def fetch_review_scales(client: Any, reviews: list[Review]) -> dict[str, ScoreScale]:
    scales: dict[str, ScoreScale] = {}
    invitation_ids = sorted(
        {review.invitation for review in reviews if review.invitation}
    )

    for invitation_id in invitation_ids:
        try:
            invitation = client.get_invitation(id=invitation_id)
        except Exception:
            try:
                invitation = client.get_invitation(invitation_id)
            except Exception:
                continue

        invitation_scales = extract_scales_from_schema(
            object_to_dict(invitation), invitation_id
        )
        for field, scale in invitation_scales.items():
            scales.setdefault(field, scale)

    return scales


def fetch_reviews(
    client: Any, forum_id: str, score_db_path, fetch_schema_scales: bool = True
) -> tuple[Any, list[Review], dict[str, ScoreScale]]:
    paper = client.get_note(id=forum_id)
    notes = client.get_notes(forum=forum_id)
    reviews = [
        note_to_review(note)
        for note in notes
        if getattr(note, "id", None) != forum_id and looks_like_official_review(note)
    ]
    reviews.sort(key=lambda review: review.created or "")
    scales = fetch_review_scales(client, reviews) if fetch_schema_scales else {}
    scales.update(load_database_scales(score_db_path, reviews))
    return paper, reviews, scales


def paper_title(paper: Any) -> str:
    content = normalize_content(getattr(paper, "content", {}) or {})
    title = content.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return paper.id

