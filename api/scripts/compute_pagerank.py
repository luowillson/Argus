from __future__ import annotations

import argparse
import json

from sqlmodel import Session

from app.db.session import get_engine
from app.services.graph_metrics import (
    DEFAULT_DAMPING,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TOLERANCE,
    compute_pagerank,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute citation-graph PageRank from paper_edges(edge_type='cites')."
    )
    parser.add_argument(
        "--damping",
        type=float,
        default=DEFAULT_DAMPING,
        help="PageRank damping factor.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help="Maximum PageRank iterations.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help="Stop once total rank delta falls below this value.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute metrics and print a summary without replacing paper_graph_metrics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with Session(get_engine()) as db:
        summary = compute_pagerank(
            db,
            damping=args.damping,
            max_iterations=args.max_iterations,
            tolerance=args.tolerance,
            persist=not args.dry_run,
        )
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
