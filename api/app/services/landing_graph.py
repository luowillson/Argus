from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging
from math import fsum
import re
from typing import Any, cast

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text as sa_text
from sqlmodel import Session

from app.config import get_settings
from app.db.models import PaperEmbedding
from app.schemas.graph import LandingGraph, LandingGraphEdge, LandingGraphNode
from app.schemas.paper import Verdict

logger = logging.getLogger(__name__)

_SEED_POOL_SIZE = 500
_TOPIC_NODE_COUNT = 500
_LOCAL_SIMILARITY_WINDOW = 32
_MAX_EXTRA_NEIGHBORS_PER_NODE = 3
_EXTRA_EDGE_SIMILARITY = 0.5
_FALLBACK_EXTRA_EDGE_SIMILARITY = 0.34
_MIN_EMBEDDING_COUNT = 500
_EMBED_BATCH_SIZE = 64
_VALID_VERDICTS: set[Verdict] = {
    "Strong Accept",
    "Accept",
    "Weak Accept",
    "Borderline",
    "Reject",
    "Insufficient reviews",
}


def build_landing_graph(db: Session) -> LandingGraph:
    _ensure_landing_graph_embeddings(db)

    seed = _pick_seed_paper(db)
    if seed is None:
        return LandingGraph(generated_at=datetime.now(timezone.utc), nodes=[], edges=[])

    raw_nodes = _fetch_topic_cluster(db, seed["paper_id"])
    if not raw_nodes:
        return LandingGraph(
            generated_at=datetime.now(timezone.utc),
            topic_paper_id=seed["paper_id"],
            topic_title=seed["title"],
            topic_venue=seed["venue"],
            nodes=[],
            edges=[],
        )

    nodes: list[LandingGraphNode] = []
    embeddings: dict[str, list[float]] = {}

    for row in raw_nodes:
        paper_id = cast(str, row["id"])
        verdict = _coerce_verdict(row.get("verdict"))
        score = row.get("score")
        nodes.append(
            LandingGraphNode(
                id=paper_id,
                title=cast(str, row["title"]),
                venue=cast(str | None, row.get("venue")),
                score=float(score) if score is not None else None,
                verdict=verdict,
            )
        )
        embeddings[paper_id] = _parse_embedding(row["embedding"])

    edges = _build_connected_edges(nodes, embeddings)
    topic_node = next((node for node in nodes if node.id == seed["paper_id"]), nodes[0])
    return LandingGraph(
        generated_at=datetime.now(timezone.utc),
        topic_paper_id=topic_node.id,
        topic_title=topic_node.title,
        topic_venue=topic_node.venue,
        nodes=nodes,
        edges=edges,
    )


def _ensure_landing_graph_embeddings(db: Session) -> None:
    current = db.execute(sa_text("SELECT COUNT(*) FROM paper_embeddings"), {}).scalar_one()
    if current >= _MIN_EMBEDDING_COUNT:
        return

    missing = _MIN_EMBEDDING_COUNT - current
    rows = list(
        db.execute(
            sa_text(
                """
                SELECT
                  p.id,
                  p.title,
                  p.abstract,
                  ai.tldr
                FROM papers p
                LEFT JOIN ai_insights ai ON ai.paper_id = p.id
                LEFT JOIN veros_scores s ON s.paper_id = p.id
                LEFT JOIN paper_embeddings pe ON pe.paper_id = p.id
                WHERE pe.paper_id IS NULL
                ORDER BY
                  s.score DESC NULLS LAST,
                  p.analyzed_at DESC NULLS LAST,
                  p.created_at DESC
                LIMIT :lim
                """
            ),
            {"lim": missing},
        ).mappings()
    )
    if not rows:
        return

    from app.services.embeddings.factory import get_embedding_provider

    provider = get_embedding_provider()
    settings = get_settings()
    logger.info("landing_graph: backfilling %d missing embeddings for homepage graph", len(rows))

    for start in range(0, len(rows), _EMBED_BATCH_SIZE):
        batch = rows[start : start + _EMBED_BATCH_SIZE]
        texts = [_embedding_text(row) for row in batch]
        vectors = provider.encode(texts)
        for row, vector in zip(batch, vectors, strict=True):
            stmt = pg_insert(PaperEmbedding).values(
                paper_id=cast(str, row["id"]),
                embedding=vector,
                source="landing_graph_backfill",
                model=settings.embedding_model,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[PaperEmbedding.__table__.c.paper_id],
                set_={
                    "embedding": stmt.excluded.embedding,
                    "source": stmt.excluded.source,
                    "model": stmt.excluded.model,
                },
            )
            db.exec(stmt)

    db.commit()


def _pick_seed_paper(db: Session) -> dict[str, str | None] | None:
    row = db.execute(
        sa_text(
            """
            WITH eligible_seed AS (
              SELECT
                p.id AS paper_id,
                p.title,
                p.venue
              FROM papers p
              JOIN paper_embeddings pe ON pe.paper_id = p.id
              LEFT JOIN veros_scores s ON s.paper_id = p.id
              WHERE p.title IS NOT NULL
              ORDER BY
                s.score DESC NULLS LAST,
                p.analyzed_at DESC NULLS LAST,
                p.created_at DESC
              LIMIT :pool
            )
            SELECT paper_id, title, venue
            FROM eligible_seed
            ORDER BY random()
            LIMIT 1
            """
        ),
        {"pool": _SEED_POOL_SIZE},
    ).mappings().first()
    if row is None:
        return None
    return {
        "paper_id": cast(str, row["paper_id"]),
        "title": cast(str | None, row["title"]),
        "venue": cast(str | None, row["venue"]),
    }


def _fetch_topic_cluster(db: Session, seed_paper_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        sa_text(
            """
            WITH seed AS (
              SELECT embedding
              FROM paper_embeddings
              WHERE paper_id = :seed_paper_id
            )
            SELECT
              p.id,
              p.title,
              p.venue,
              s.score,
              s.verdict,
              pe.embedding
            FROM seed
            JOIN paper_embeddings pe ON TRUE
            JOIN papers p ON p.id = pe.paper_id
            LEFT JOIN veros_scores s ON s.paper_id = p.id
            ORDER BY pe.embedding <=> seed.embedding, s.score DESC NULLS LAST
            LIMIT :lim
            """
        ),
        {"seed_paper_id": seed_paper_id, "lim": _TOPIC_NODE_COUNT},
    ).mappings()
    return [dict(row) for row in rows]


def _build_connected_edges(
    nodes: list[LandingGraphNode],
    embeddings: dict[str, list[float]],
) -> list[LandingGraphEdge]:
    if len(nodes) < 2:
        return []

    ranked_lookup = _local_ranked_similarities(nodes, embeddings)
    node_index = {node.id: index for index, node in enumerate(nodes)}
    deduped: dict[tuple[str, str], float] = {}

    # Guarantee connectivity by wiring each node to its nearest already-added paper.
    for index, node in enumerate(nodes[1:], start=1):
        parent = next(
            (
                (target, similarity)
                for target, similarity in ranked_lookup[node.id]
                if node_index.get(target, len(nodes)) < index
            ),
            None,
        )
        if parent is not None:
            _remember_edge(deduped, node.id, parent[0], parent[1])

    _add_extra_edges(deduped, ranked_lookup, threshold=_EXTRA_EDGE_SIMILARITY)
    if len(deduped) < len(nodes) - 1:
        _add_extra_edges(deduped, ranked_lookup, threshold=_FALLBACK_EXTRA_EDGE_SIMILARITY)

    return [
        LandingGraphEdge(source=source, target=target, weight=round(weight, 3))
        for (source, target), weight in sorted(
            deduped.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


def _local_ranked_similarities(
    nodes: list[LandingGraphNode],
    embeddings: dict[str, list[float]],
) -> dict[str, list[tuple[str, float]]]:
    similarities: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for index, left in enumerate(nodes):
        left_embedding = embeddings[left.id]
        start = max(0, index - _LOCAL_SIMILARITY_WINDOW)
        stop = min(len(nodes), index + _LOCAL_SIMILARITY_WINDOW + 1)
        for candidate_index in range(start, stop):
            if candidate_index == index:
                continue
            right = nodes[candidate_index]
            similarity = _dot(left_embedding, embeddings[right.id])
            similarities[left.id].append((right.id, similarity))
    return {
        node.id: sorted(similarities[node.id], key=lambda item: item[1], reverse=True)
        for node in nodes
    }


def _add_extra_edges(
    deduped: dict[tuple[str, str], float],
    ranked_lookup: dict[str, list[tuple[str, float]]],
    *,
    threshold: float,
) -> None:
    for source, neighbors in ranked_lookup.items():
        added = 0
        for target, similarity in neighbors:
            if similarity < threshold:
                break
            key = tuple(sorted((source, target)))
            if key not in deduped:
                deduped[key] = similarity
                added += 1
            if added >= _MAX_EXTRA_NEIGHBORS_PER_NODE:
                break


def _remember_edge(
    deduped: dict[tuple[str, str], float],
    source: str,
    target: str,
    similarity: float,
) -> None:
    key = tuple(sorted((source, target)))
    deduped[key] = max(deduped.get(key, 0.0), similarity)


def _dot(left: list[float], right: list[float]) -> float:
    return fsum(a * b for a, b in zip(left, right, strict=False))


def _embedding_text(row: Any) -> str:
    title = cast(str | None, row.get("title")) or ""
    tldr = cast(str | None, row.get("tldr")) or ""
    abstract = cast(str | None, row.get("abstract")) or ""
    body = tldr or abstract
    return f"{title}\n{body}".strip()


def _parse_embedding(value: Any) -> list[float]:
    if isinstance(value, str):
        matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)
        return [float(match) for match in matches]
    return [float(item) for item in cast(list[Any], value)]


def _coerce_verdict(value: Any) -> Verdict:
    if isinstance(value, str) and value in _VALID_VERDICTS:
        return cast(Verdict, value)
    return "Borderline"
