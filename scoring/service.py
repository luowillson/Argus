from __future__ import annotations

from pathlib import Path
from typing import Any

from .formatting import score_summary_payload
from .openreview_client import (
    build_client,
    fetch_reviews,
    parse_forum_id,
    resolve_forum_id_from_title,
    search_papers_by_title,
)
from .parsing import cache_scores_from_markdown_files
from .storage import (
    DEFAULT_SCORE_CACHE_PATH,
    DEFAULT_SCORE_DB_PATH,
    add_score_scale,
    add_score_scales,
    get_cached_score_payload,
    load_score_cache,
    load_score_db,
    save_score_payload,
)


def get_score_summary(
    *,
    paper_id: str | None = None,
    title: str | None = None,
    conference: str | None = None,
    match_index: int = 1,
    search_limit: int = 10,
    api_version: str = "v2",
    username: str | None = None,
    password: str | None = None,
    score_db_path: Path = DEFAULT_SCORE_DB_PATH,
    score_cache_path: Path = DEFAULT_SCORE_CACHE_PATH,
    use_cache: bool = True,
    fetch_schema_scales: bool = True,
) -> dict[str, Any]:
    """Return a JSON-safe score summary for a paper.

    This is the primary function a future web backend should call.
    """
    if use_cache:
        cached_payload = get_cached_score_payload(
            score_cache_path, paper_id, title, parse_forum_id
        )
        if cached_payload:
            return cached_payload

    client = build_client(api_version, username, password)
    if title:
        forum_id = resolve_forum_id_from_title(
            client, title, conference, match_index, search_limit
        )
    elif paper_id:
        forum_id = parse_forum_id(paper_id)
    else:
        raise ValueError("Either paper_id or title is required.")

    paper, reviews, scales = fetch_reviews(
        client, forum_id, score_db_path, fetch_schema_scales
    )
    payload = score_summary_payload(paper, reviews, scales)
    save_score_payload(score_cache_path, payload, "openreview")
    return payload


def get_reviews_for_paper(
    *,
    paper_id: str | None = None,
    title: str | None = None,
    conference: str | None = None,
    match_index: int = 1,
    search_limit: int = 10,
    api_version: str = "v2",
    username: str | None = None,
    password: str | None = None,
    score_db_path: Path = DEFAULT_SCORE_DB_PATH,
    fetch_schema_scales: bool = True,
) -> tuple[Any, list[Any], dict[str, Any]]:
    """Fetch raw paper/review objects plus scales for full JSON/Markdown rendering."""
    client = build_client(api_version, username, password)
    if title:
        forum_id = resolve_forum_id_from_title(
            client, title, conference, match_index, search_limit
        )
    elif paper_id:
        forum_id = parse_forum_id(paper_id)
    else:
        raise ValueError("Either paper_id or title is required.")

    return fetch_reviews(client, forum_id, score_db_path, fetch_schema_scales)


def list_title_matches(
    *,
    title: str,
    conference: str,
    api_version: str = "v2",
    username: str | None = None,
    password: str | None = None,
    search_limit: int = 10,
) -> list[dict[str, Any]]:
    client = build_client(api_version, username, password)
    return [
        candidate.__dict__
        for candidate in search_papers_by_title(client, title, conference, search_limit)
    ]


def cache_parsed_scores(
    markdown_paths: list[Path],
    score_db_path: Path = DEFAULT_SCORE_DB_PATH,
    score_cache_path: Path = DEFAULT_SCORE_CACHE_PATH,
) -> int:
    return cache_scores_from_markdown_files(
        markdown_paths, score_db_path, score_cache_path
    )


def list_cached_scores(
    score_cache_path: Path = DEFAULT_SCORE_CACHE_PATH,
) -> dict[str, Any]:
    return load_score_cache(score_cache_path)


def list_score_scales(score_db_path: Path = DEFAULT_SCORE_DB_PATH) -> dict[str, Any]:
    return load_score_db(score_db_path)


__all__ = [
    "add_score_scale",
    "add_score_scales",
    "cache_parsed_scores",
    "get_reviews_for_paper",
    "get_score_summary",
    "list_cached_scores",
    "list_score_scales",
    "list_title_matches",
]

