from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import text as sa_text
from sqlmodel import Session, select

from app.db.models import PaperGraphMetric

DEFAULT_DAMPING = 0.85
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_TOLERANCE = 1e-8
DEFAULT_BATCH_SIZE = 5_000


@dataclass(frozen=True)
class PageRankResult:
    ranks: dict[str, float]
    in_degree: dict[str, int]
    out_degree: dict[str, int]
    edge_count: int
    iterations: int
    converged: bool
    total_delta: float


@dataclass(frozen=True)
class PageRankSummary:
    node_count: int
    edge_count: int
    iterations: int
    converged: bool
    total_delta: float
    damping: float
    tolerance: float
    persisted: bool
    computed_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def calculate_pagerank(
    edges: Iterable[tuple[str, str]],
    *,
    damping: float = DEFAULT_DAMPING,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    tolerance: float = DEFAULT_TOLERANCE,
) -> PageRankResult:
    """Compute PageRank over directed citation edges.

    Edges use the existing project convention: ``src`` cites ``dst``. Rank
    therefore flows from a citing paper to the paper it references.
    """
    if not 0 < damping < 1:
        raise ValueError("damping must be between 0 and 1")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")

    nodes: set[str] = set()
    outlinks: dict[str, set[str]] = {}
    inlinks: dict[str, set[str]] = {}

    for raw_src, raw_dst in edges:
        src = str(raw_src).strip()
        dst = str(raw_dst).strip()
        if not src or not dst:
            continue
        nodes.add(src)
        nodes.add(dst)
        targets = outlinks.setdefault(src, set())
        if dst not in targets:
            targets.add(dst)
            inlinks.setdefault(dst, set()).add(src)

    for node in nodes:
        outlinks.setdefault(node, set())
        inlinks.setdefault(node, set())

    node_count = len(nodes)
    edge_count = sum(len(targets) for targets in outlinks.values())
    if node_count == 0:
        return PageRankResult(
            ranks={},
            in_degree={},
            out_degree={},
            edge_count=0,
            iterations=0,
            converged=True,
            total_delta=0.0,
        )

    rank = {node: 1.0 / node_count for node in nodes}
    total_delta = 0.0

    for iteration in range(1, max_iterations + 1):
        dangling_sum = sum(rank[node] for node in nodes if not outlinks[node])
        base_rank = (1.0 - damping) / node_count
        dangling_rank = damping * dangling_sum / node_count
        next_rank: dict[str, float] = {}

        for node in nodes:
            incoming_rank = sum(
                rank[src] / len(outlinks[src])
                for src in inlinks[node]
                if outlinks[src]
            )
            next_rank[node] = base_rank + dangling_rank + damping * incoming_rank

        total = sum(next_rank.values())
        if total:
            next_rank = {node: value / total for node, value in next_rank.items()}

        total_delta = sum(abs(next_rank[node] - rank[node]) for node in nodes)
        rank = next_rank
        if total_delta < tolerance:
            return PageRankResult(
                ranks=rank,
                in_degree={node: len(inlinks[node]) for node in nodes},
                out_degree={node: len(outlinks[node]) for node in nodes},
                edge_count=edge_count,
                iterations=iteration,
                converged=True,
                total_delta=total_delta,
            )

    return PageRankResult(
        ranks=rank,
        in_degree={node: len(inlinks[node]) for node in nodes},
        out_degree={node: len(outlinks[node]) for node in nodes},
        edge_count=edge_count,
        iterations=max_iterations,
        converged=False,
        total_delta=total_delta,
    )


def load_citation_edges(db: Session) -> list[tuple[str, str]]:
    rows = db.execute(
        sa_text(
            """
            SELECT src_paper_id, dst_paper_id
            FROM paper_edges
            WHERE edge_type = 'cites'
            """
        )
    ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


def replace_graph_metrics(
    db: Session,
    result: PageRankResult,
    *,
    computed_at: datetime | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> None:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    computed = computed_at or datetime.now(UTC)
    db.execute(PaperGraphMetric.__table__.delete())

    rows = [
        {
            "paper_id": paper_id,
            "pagerank": score,
            "in_degree": result.in_degree.get(paper_id, 0),
            "out_degree": result.out_degree.get(paper_id, 0),
            "computed_at": computed,
        }
        for paper_id, score in sorted(result.ranks.items())
    ]

    table = PaperGraphMetric.__table__
    for start in range(0, len(rows), batch_size):
        db.execute(table.insert(), rows[start : start + batch_size])
    db.commit()


def compute_pagerank(
    db: Session,
    *,
    damping: float = DEFAULT_DAMPING,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    tolerance: float = DEFAULT_TOLERANCE,
    persist: bool = True,
) -> PageRankSummary:
    result = calculate_pagerank(
        load_citation_edges(db),
        damping=damping,
        max_iterations=max_iterations,
        tolerance=tolerance,
    )
    computed_at = datetime.now(UTC)
    if persist:
        replace_graph_metrics(db, result, computed_at=computed_at)

    return PageRankSummary(
        node_count=len(result.ranks),
        edge_count=result.edge_count,
        iterations=result.iterations,
        converged=result.converged,
        total_delta=result.total_delta,
        damping=damping,
        tolerance=tolerance,
        persisted=persist,
        computed_at=computed_at.isoformat(),
    )


def load_graph_metrics(db: Session, paper_ids: list[str]) -> dict[str, PaperGraphMetric]:
    unique_ids = list(dict.fromkeys(pid for pid in paper_ids if pid))
    if not unique_ids:
        return {}
    rows = db.exec(
        select(PaperGraphMetric).where(PaperGraphMetric.paper_id.in_(unique_ids))
    ).all()
    return {row.paper_id: row for row in rows}
