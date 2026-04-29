"""Merge a local Veros Postgres database into the configured shared database.

Source defaults to the local Docker database. Target defaults to api/.env
DATABASE_URL via app.config.Settings. Rows are merged with Postgres upserts so
overlapping papers/reviews/scores update instead of failing on primary keys.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.config import get_settings

LOCAL_DATABASE_URL = "postgresql+psycopg://veros:veros@localhost:5432/veros"


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: Sequence[str]
    conflict_columns: Sequence[str]
    jsonb_columns: frozenset[str] = frozenset()
    vector_columns: frozenset[str] = frozenset()


TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        name="papers",
        columns=(
            "id",
            "title",
            "authors",
            "venue",
            "year",
            "citations",
            "references_count",
            "abstract",
            "openreview_url",
            "acceptance",
            "citation_metadata",
            "citation_enriched_at",
            "ingested_at",
            "analyzed_at",
            "created_at",
        ),
        conflict_columns=("id",),
        jsonb_columns=frozenset({"citation_metadata"}),
    ),
    TableSpec(
        name="paper_identifiers",
        columns=("paper_id", "namespace", "value", "confidence", "source", "created_at"),
        conflict_columns=("namespace", "value"),
    ),
    TableSpec(
        name="reviews",
        columns=(
            "id",
            "paper_id",
            "invitation",
            "signatures",
            "rating",
            "confidence",
            "recommendation",
            "content",
            "created_at",
        ),
        conflict_columns=("id",),
        jsonb_columns=frozenset({"content"}),
    ),
    TableSpec(
        name="ai_insights",
        columns=(
            "paper_id",
            "tldr",
            "deep",
            "skim",
            "reviewer_voices",
            "novelty",
            "technical",
            "clarity",
            "impact",
            "consensus",
            "model",
            "prompt_version",
            "generated_at",
        ),
        conflict_columns=("paper_id",),
        jsonb_columns=frozenset({"reviewer_voices"}),
    ),
    TableSpec(
        name="veros_scores",
        columns=("paper_id", "score", "grade", "verdict", "breakdown", "computed_at"),
        conflict_columns=("paper_id",),
        jsonb_columns=frozenset({"breakdown"}),
    ),
    TableSpec(
        name="saved_papers",
        columns=("user_id", "paper_id", "saved_at"),
        conflict_columns=("user_id", "paper_id"),
    ),
    TableSpec(
        name="paper_embeddings",
        columns=("paper_id", "embedding", "source", "model"),
        conflict_columns=("paper_id",),
        vector_columns=frozenset({"embedding"}),
    ),
    TableSpec(
        name="paper_edges",
        columns=(
            "src_paper_id",
            "dst_paper_id",
            "edge_type",
            "weight",
            "edge_metadata",
            "created_at",
        ),
        conflict_columns=("src_paper_id", "dst_paper_id", "edge_type"),
        jsonb_columns=frozenset({"edge_metadata"}),
    ),
    TableSpec(
        name="api_rate_limits",
        columns=("provider", "last_request_at"),
        conflict_columns=("provider",),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge rows from a local Veros Postgres database into the shared "
            "database configured by DATABASE_URL."
        )
    )
    parser.add_argument(
        "--source-url",
        default=LOCAL_DATABASE_URL,
        help=f"Source database URL. Defaults to local Docker Postgres: {LOCAL_DATABASE_URL}",
    )
    parser.add_argument(
        "--target-url",
        default=get_settings().database_url,
        help="Target database URL. Defaults to DATABASE_URL from api/.env.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows to read and write per batch.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip paper_embeddings. Useful if local embeddings were generated with another model.",
    )
    parser.add_argument(
        "--rewrite-saved-user-id",
        help=(
            "Rewrite saved_papers.user_id while merging. Use this if local saves "
            "were stored under demo-user but should belong to a specific teammate."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print source row counts without writing to the target database.",
    )
    return parser.parse_args()


def select_sql(spec: TableSpec) -> str:
    columns = [
        f"{column}::text AS {column}"
        if column in spec.vector_columns | spec.jsonb_columns
        else column
        for column in spec.columns
    ]
    return f"SELECT {', '.join(columns)} FROM {spec.name} ORDER BY {', '.join(spec.conflict_columns)}"


def insert_sql(spec: TableSpec) -> str:
    values = [
        f"CAST(:{column} AS vector)"
        if column in spec.vector_columns
        else f"CAST(:{column} AS jsonb)"
        if column in spec.jsonb_columns
        else f":{column}"
        for column in spec.columns
    ]
    update_columns = [
        column for column in spec.columns if column not in set(spec.conflict_columns)
    ]
    update_clause = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in update_columns
    )
    if not update_clause:
        update_clause = "NOTHING"
    else:
        update_clause = f"UPDATE SET {update_clause}"

    return (
        f"INSERT INTO {spec.name} ({', '.join(spec.columns)}) "
        f"VALUES ({', '.join(values)}) "
        f"ON CONFLICT ({', '.join(spec.conflict_columns)}) DO {update_clause}"
    )


def batched(rows: Sequence[dict[str, Any]], size: int) -> Iterable[Sequence[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def read_rows(source: Connection, spec: TableSpec) -> list[dict[str, Any]]:
    rows = [dict(row) for row in source.execute(text(select_sql(spec))).mappings().all()]
    for row in rows:
        for column in spec.jsonb_columns:
            if row[column] is not None and not isinstance(row[column], str):
                row[column] = json.dumps(row[column])
    return rows


def merge_table(
    source: Connection,
    target: Connection,
    spec: TableSpec,
    *,
    batch_size: int,
    rewrite_saved_user_id: str | None,
    dry_run: bool,
) -> int:
    rows = read_rows(source, spec)
    if spec.name == "saved_papers" and rewrite_saved_user_id:
        rows = [{**row, "user_id": rewrite_saved_user_id} for row in rows]

    if dry_run or not rows:
        return len(rows)

    statement = text(insert_sql(spec))
    for batch in batched(rows, batch_size):
        target.execute(statement, list(batch))
    return len(rows)


def assert_distinct_databases(source_url: str, target_url: str) -> None:
    if source_url == target_url:
        raise SystemExit("Source and target URLs are identical; refusing to merge.")


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")
    assert_distinct_databases(args.source_url, args.target_url)

    source_engine = create_engine(args.source_url, pool_pre_ping=True, future=True)
    target_engine = create_engine(args.target_url, pool_pre_ping=True, future=True)

    specs = [
        spec
        for spec in TABLES
        if not (args.skip_embeddings and spec.name == "paper_embeddings")
    ]

    total = 0
    with source_engine.connect() as source, target_engine.begin() as target:
        for spec in specs:
            count = merge_table(
                source,
                target,
                spec,
                batch_size=args.batch_size,
                rewrite_saved_user_id=args.rewrite_saved_user_id,
                dry_run=args.dry_run,
            )
            total += count
            action = "would merge" if args.dry_run else "merged"
            print(f"{action} {count:>5} rows from {spec.name}")

    suffix = " checked" if args.dry_run else " merged"
    print(f"{total} total rows{suffix}.")


if __name__ == "__main__":
    main()
