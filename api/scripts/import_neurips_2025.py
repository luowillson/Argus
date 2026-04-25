from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_engine
from app.services.neurips_import import import_neurips_2025_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the local NeurIPS 2025 JSONL dataset into the API database."
    )
    parser.add_argument(
        "--source",
        default="../data/neurips_2025_accepted_reviews.jsonl",
        help="Path to the NeurIPS JSONL source file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of papers to import.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Resume without rewriting papers that already exist in the database.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    with Session(get_engine()) as db:
        result = import_neurips_2025_jsonl(
            db,
            source,
            limit=args.limit,
            skip_existing=args.skip_existing,
        )

    print(
        "Imported NeurIPS 2025 data: "
        f"seen_rows={result.seen_rows}, "
        f"imported_papers={result.imported_papers}, "
        f"skipped_existing={result.skipped_existing}, "
        f"imported_reviews={result.imported_reviews}, "
        f"scored_papers={result.scored_papers}, "
        f"source={result.source}"
    )


if __name__ == "__main__":
    main()
