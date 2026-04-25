#!/usr/bin/env python3
"""CLI wrapper for Argus OpenReview scoring tools.

Examples:
    python openreview_reviews.py "https://openreview.net/forum?id=abc123"
    python openreview_reviews.py abc123 --format markdown --output reviews.md
    python openreview_reviews.py --title "Paper title" --conference ICLR.cc/2026/Conference
    python openreview_reviews.py --add-score-scale ICLR.cc/2026/Conference rating 10
    python openreview_reviews.py --add-score-scales NeurIPS.cc/2025/Conference quality=4 clarity=4 significance=4 originality=4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from argus_openreview.formatting import (
    format_json,
    format_markdown,
    format_scores_text_payload,
)
from argus_openreview.service import (
    add_score_scale,
    add_score_scales,
    cache_parsed_scores,
    get_reviews_for_paper,
    get_score_summary,
    list_cached_scores,
    list_score_scales,
    list_title_matches,
)
from argus_openreview.storage import DEFAULT_SCORE_CACHE_PATH, DEFAULT_SCORE_DB_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve visible OpenReview reviews and compute standardized scores."
    )
    parser.add_argument(
        "paper",
        nargs="?",
        help=(
            "OpenReview forum id or URL, for example "
            "https://openreview.net/forum?id=abc123. Omit when using --title."
        ),
    )
    parser.add_argument(
        "--title",
        help="Find the paper by exact title before fetching reviews.",
    )
    parser.add_argument(
        "--conference",
        "--venue",
        dest="conference",
        help=(
            "Conference/venue key used with --title, for example "
            "NeurIPS.cc/2025/Conference."
        ),
    )
    parser.add_argument(
        "--match-index",
        type=int,
        default=1,
        help="When --title finds multiple matches, select this 1-based candidate.",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=10,
        help="Maximum title-search candidates to consider. Defaults to 10.",
    )
    parser.add_argument(
        "--list-title-matches",
        action="store_true",
        help="List title-search matches and exit without fetching reviews.",
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
        help="Output format for full review output. Defaults to json.",
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Output only the aggregate score and scoring sections as clean text.",
    )
    parser.add_argument(
        "--scores-json",
        action="store_true",
        help="Output only the aggregate score and scoring sections as JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. Defaults to stdout.",
    )
    parser.add_argument(
        "--score-db",
        type=Path,
        default=DEFAULT_SCORE_DB_PATH,
        help=f"Local score scale database. Defaults to {DEFAULT_SCORE_DB_PATH.name}.",
    )
    parser.add_argument(
        "--score-cache",
        type=Path,
        default=DEFAULT_SCORE_CACHE_PATH,
        help=f"Local paper score cache. Defaults to {DEFAULT_SCORE_CACHE_PATH.name}.",
    )
    parser.add_argument(
        "--cache-parsed-scores",
        nargs="+",
        type=Path,
        metavar="REVIEWS_MD",
        help="Parse generated review Markdown files and cache their score summaries.",
    )
    parser.add_argument(
        "--list-cached-scores",
        action="store_true",
        help="Print cached paper score summaries and exit.",
    )
    parser.add_argument(
        "--refresh-score-cache",
        action="store_true",
        help="Ignore cached score-only results and refresh from OpenReview.",
    )
    parser.add_argument(
        "--list-score-scales",
        action="store_true",
        help="Print the local score scale database and exit.",
    )
    parser.add_argument(
        "--add-score-scale",
        nargs=3,
        metavar=("VENUE", "FIELD", "MAX_SCORE"),
        help=(
            "Add or update a score scale in the local database, for example: "
            "--add-score-scale ICLR.cc/2026/Conference rating 10"
        ),
    )
    parser.add_argument(
        "--add-score-scales",
        nargs="+",
        metavar=("VENUE", "FIELD=MAX"),
        help=(
            "Add or update multiple score scales for one venue, for example: "
            "--add-score-scales NeurIPS.cc/2025/Conference quality=4 clarity=4"
        ),
    )
    parser.add_argument(
        "--scale-min",
        type=float,
        default=1.0,
        help="Minimum score for --add-score-scale/--add-score-scales. Defaults to 1.",
    )
    return parser.parse_args()


def write_output(output: str, output_path: Path | None) -> None:
    if output_path:
        output_path.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


def main() -> int:
    args = parse_args()

    if args.add_score_scale:
        venue, field, max_score = args.add_score_scale
        add_score_scale(
            args.score_db,
            venue,
            field,
            args.scale_min,
            float(max_score),
        )
        print(
            f"Saved score scale for {venue} field '{field.lower()}' "
            f"as {args.scale_min:g}-{float(max_score):g} in {args.score_db}."
        )
        return 0

    if args.add_score_scales:
        if len(args.add_score_scales) < 2:
            raise ValueError(
                "--add-score-scales requires a venue and at least one FIELD=MAX value."
            )
        venue = args.add_score_scales[0]
        saved_scales = add_score_scales(
            args.score_db,
            venue,
            args.add_score_scales[1:],
            args.scale_min,
        )
        scale_summary = ", ".join(
            f"{field}={minimum:g}-{maximum:g}"
            for field, minimum, maximum in saved_scales
        )
        print(f"Saved score scales for {venue}: {scale_summary} in {args.score_db}.")
        return 0

    if args.list_score_scales:
        print(json.dumps(list_score_scales(args.score_db), indent=2, sort_keys=True))
        return 0

    if args.cache_parsed_scores:
        cached_count = cache_parsed_scores(
            args.cache_parsed_scores, args.score_db, args.score_cache
        )
        print(f"Cached score summaries for {cached_count} paper(s) in {args.score_cache}.")
        return 0

    if args.list_cached_scores:
        print(json.dumps(list_cached_scores(args.score_cache), indent=2, sort_keys=True))
        return 0

    if args.list_title_matches:
        if not args.title or not args.conference:
            raise ValueError("--list-title-matches requires --title and --conference.")
        matches = list_title_matches(
            title=args.title,
            conference=args.conference,
            api_version=args.api_version,
            username=args.username,
            password=args.password,
            search_limit=args.search_limit,
        )
        if not matches:
            print(f"No OpenReview paper found for title '{args.title}'.")
            return 1
        for index, candidate in enumerate(matches, start=1):
            print(
                f"{index}. {candidate['title']} [{candidate['id']}] "
                f"venue={candidate.get('venue') or 'unknown'} "
                f"domain={candidate.get('domain') or 'unknown'}"
            )
        return 0

    if args.scores_only or args.scores_json:
        payload = get_score_summary(
            paper_id=args.paper,
            title=args.title,
            conference=args.conference,
            match_index=args.match_index,
            search_limit=args.search_limit,
            api_version=args.api_version,
            username=args.username,
            password=args.password,
            score_db_path=args.score_db,
            score_cache_path=args.score_cache,
            use_cache=not args.refresh_score_cache,
        )
        output = (
            json.dumps(payload, indent=2, ensure_ascii=False)
            if args.scores_json
            else format_scores_text_payload(payload)
        )
        write_output(output, args.output)
        return 0

    paper, reviews, scales = get_reviews_for_paper(
        paper_id=args.paper,
        title=args.title,
        conference=args.conference,
        match_index=args.match_index,
        search_limit=args.search_limit,
        api_version=args.api_version,
        username=args.username,
        password=args.password,
        score_db_path=args.score_db,
    )
    output = (
        format_markdown(paper, reviews, scales)
        if args.format == "markdown"
        else format_json(paper, reviews, scales)
    )
    write_output(output, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

