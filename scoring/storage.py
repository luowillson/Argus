from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Review, ScoreScale
from .scoring import parse_number


DEFAULT_SCORE_DB_PATH = Path(__file__).resolve().parent.parent / "score_scales.json"
DEFAULT_SCORE_CACHE_PATH = Path(__file__).resolve().parent.parent / "paper_scores.json"


def empty_score_db() -> dict[str, Any]:
    return {"venues": {}}


def load_score_db(path: Path = DEFAULT_SCORE_DB_PATH) -> dict[str, Any]:
    if not path.exists():
        return empty_score_db()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Could not parse score database {path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Score database {path} must contain a JSON object.")
    if not isinstance(data.get("venues", {}), dict):
        raise ValueError(f"Score database {path} must contain a 'venues' object.")

    data.setdefault("venues", {})
    return data


def save_score_db(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def empty_score_cache() -> dict[str, Any]:
    return {"papers": {}}


def load_score_cache(path: Path = DEFAULT_SCORE_CACHE_PATH) -> dict[str, Any]:
    if not path.exists():
        return empty_score_cache()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Could not parse score cache {path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"Score cache {path} must contain a JSON object.")
    if not isinstance(data.get("papers", {}), dict):
        raise ValueError(f"Score cache {path} must contain a 'papers' object.")

    data.setdefault("papers", {})
    return data


def save_score_cache(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_score_scale(
    db_path: Path, venue: str, field: str, minimum: float, maximum: float
) -> None:
    if minimum >= maximum:
        raise ValueError("--scale-min must be less than --scale-max.")

    data = load_score_db(db_path)
    venues = data.setdefault("venues", {})
    venue_entry = venues.setdefault(venue, {})
    venue_entry[field.lower()] = {
        "min": minimum,
        "max": maximum,
    }
    save_score_db(db_path, data)


def parse_field_scale(value: str, default_minimum: float) -> tuple[str, float, float]:
    if "=" not in value:
        raise ValueError(
            f"Expected FIELD=MAX or FIELD=MIN:MAX for score scale '{value}'."
        )

    field, scale = value.split("=", 1)
    field = field.strip().lower()
    if not field:
        raise ValueError(f"Missing field name in score scale '{value}'.")

    if ":" in scale:
        minimum_text, maximum_text = scale.split(":", 1)
        minimum = float(minimum_text)
    else:
        minimum = default_minimum
        maximum_text = scale

    maximum = float(maximum_text)
    if minimum >= maximum:
        raise ValueError(f"Minimum must be less than maximum in score scale '{value}'.")

    return field, minimum, maximum


def add_score_scales(
    db_path: Path, venue: str, field_scales: list[str], default_minimum: float
) -> list[tuple[str, float, float]]:
    data = load_score_db(db_path)
    venues = data.setdefault("venues", {})
    venue_entry = venues.setdefault(venue, {})
    saved_scales: list[tuple[str, float, float]] = []

    for field_scale in field_scales:
        field, minimum, maximum = parse_field_scale(field_scale, default_minimum)
        venue_entry[field] = {
            "min": minimum,
            "max": maximum,
        }
        saved_scales.append((field, minimum, maximum))

    save_score_db(db_path, data)
    return saved_scales


def venue_key_from_invitation(invitation: str | None) -> str | None:
    if not invitation:
        return None

    parts = invitation.split("/")
    for index, part in enumerate(parts):
        if re.fullmatch(r"(Submission|Paper)\d+", part) and index > 0:
            return "/".join(parts[:index])
        if part in {"Submission", "Paper"} and index > 0:
            return "/".join(parts[:index])

    if len(parts) >= 3 and parts[-2] == "-":
        return "/".join(parts[:-2])
    if parts:
        return parts[0]

    return None


def load_database_scales(
    db_path: Path, reviews: list[Review]
) -> dict[str, ScoreScale]:
    data = load_score_db(db_path)
    venues = data.get("venues", {})
    scales: dict[str, ScoreScale] = {}
    venue_keys = {
        venue_key
        for review in reviews
        if (venue_key := venue_key_from_invitation(review.invitation))
    }

    for venue_key in sorted(venue_keys):
        venue_entry = venues.get(venue_key)
        if not isinstance(venue_entry, dict):
            continue

        for field, scale_data in venue_entry.items():
            if not isinstance(scale_data, dict):
                continue
            minimum = parse_number(scale_data.get("min"))
            maximum = parse_number(scale_data.get("max"))
            if minimum is None or maximum is None or minimum >= maximum:
                continue
            scales.setdefault(
                field.lower(),
                ScoreScale(
                    min=minimum,
                    max=maximum,
                    source=f"{db_path.name}:{venue_key}",
                ),
            )

    return scales


def save_score_payload(cache_path: Path, payload: dict[str, Any], source: str) -> None:
    cache = load_score_cache(cache_path)
    paper_id = payload.get("paper", {}).get("id")
    if not isinstance(paper_id, str) or not paper_id:
        return

    payload = dict(payload)
    payload["cached_at"] = datetime.now(timezone.utc).isoformat()
    payload["source"] = source
    cache.setdefault("papers", {})[paper_id] = payload
    save_score_cache(cache_path, cache)


def cached_score_matches_title(payload: dict[str, Any], title: str) -> bool:
    cached_title = payload.get("paper", {}).get("title")
    normalized_cached = re.sub(r"\s+", " ", str(cached_title).casefold()).strip()
    normalized_title = re.sub(r"\s+", " ", title.casefold()).strip()
    return isinstance(cached_title, str) and normalized_cached == normalized_title


def get_cached_score_payload(
    cache_path: Path, paper: str | None, title: str | None, parse_forum_id
) -> dict[str, Any] | None:
    cache = load_score_cache(cache_path)
    papers = cache.get("papers", {})

    if paper:
        forum_id = parse_forum_id(paper)
        payload = papers.get(forum_id)
        if isinstance(payload, dict):
            return payload

    if title:
        for payload in papers.values():
            if isinstance(payload, dict) and cached_score_matches_title(payload, title):
                return payload

    return None

