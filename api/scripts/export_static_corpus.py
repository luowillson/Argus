"""Export the database-backed paper corpus for browser-side search.

Usage:
    uv run python scripts/export_static_corpus.py

The frontend reads the generated JSON from /data/papers.json and performs
search, sort, saved-page hydration, and paper-detail reads locally.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_engine
from app.services.static_corpus import build_static_corpus_payload

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "web" / "public" / "data" / "papers.json"


def export_corpus(output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    with Session(get_engine()) as db:
        payload = build_static_corpus_payload(db)

    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return int(payload["paper_count"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path. Defaults to {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    count = export_corpus(args.output)
    print(f"Exported {count} papers to {args.output}")


if __name__ == "__main__":
    main()
