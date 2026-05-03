#!/usr/bin/env python3
"""Recursive citation crawler using the Semantic Scholar API.

Usage
-----
    # By Semantic Scholar paper ID
    python scripts/crawl_citations.py 649def34f8be52c8b66281af98ae884c09aef38b

    # By DOI
    python scripts/crawl_citations.py --doi 10.48550/arXiv.1706.03762

    # By ArXiv ID
    python scripts/crawl_citations.py --arxiv 1706.03762

    # Control depth and output
    python scripts/crawl_citations.py 649def34f8be52c8b66281af98ae884c09aef38b \
        --max-depth 3 \
        --max-papers 500 \
        --output citations.json

    # Use an API key for higher rate limits
    python scripts/crawl_citations.py 649def34f8be52c8b66281af98ae884c09aef38b \
        --api-key YOUR_KEY

The script performs a breadth-first crawl: starting from the seed paper, it
fetches all references, then all references of those references, and so on.
It respects the Semantic Scholar rate limit (1 request per second by default)
and deduplicates papers by their S2 paper ID.

Output is a JSON file containing:
  - papers: dict mapping paper_id → paper metadata
  - edges:  list of {source, target} citation edges
  - stats:  crawl statistics (depth reached, papers found, etc.)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

S2_BASE = "https://api.semanticscholar.org/graph/v1"

PAPER_FIELDS = ",".join([
    "paperId", "corpusId", "title", "authors", "year", "venue",
    "citationCount", "referenceCount", "externalIds", "url",
])

REFERENCE_FIELDS = ",".join([
    "citedPaper.paperId", "citedPaper.corpusId", "citedPaper.title",
    "citedPaper.authors", "citedPaper.year", "citedPaper.venue",
    "citedPaper.citationCount", "citedPaper.referenceCount",
    "citedPaper.externalIds", "citedPaper.url",
])


@dataclass
class PaperNode:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    depth: int = 0  # BFS depth from the seed


@dataclass
class Edge:
    source: str  # paper that cites
    target: str  # paper being cited


class SemanticScholarCrawler:
    """BFS citation crawler with rate limiting."""

    def __init__(
        self,
        *,
        api_key: str = "",
        min_interval: float = 1.05,
        timeout: float = 15.0,
        max_refs_per_paper: int = 500,
    ) -> None:
        self._api_key = api_key
        self._min_interval = min_interval
        self._timeout = timeout
        self._last_request_at = 0.0
        self._request_count = 0
        self._max_refs = max_refs_per_paper

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        self._rate_limit()
        self._last_request_at = time.monotonic()
        self._request_count += 1
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url)
        if self._api_key:
            req.add_header("x-api-key", self._api_key)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read())
                return data if isinstance(data, dict) else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code == 429:
                wait = float(exc.headers.get("Retry-After", "5"))
                logger.warning("Rate limited — waiting %.1fs", wait)
                time.sleep(wait)
                return self._get_json(url, params)  # retry
            logger.warning("HTTP %d: %s", exc.code, exc)
            return None
        except Exception as exc:
            logger.warning("Request failed: %s", exc)
            return None

    def resolve_paper(self, identifier: str) -> dict[str, Any] | None:
        """Look up a paper by S2 ID, DOI:xxx, or ARXIV:xxx."""
        return self._get_json(
            f"{S2_BASE}/paper/{identifier}",
            params={"fields": PAPER_FIELDS},
        )

    def search_paper(self, title: str) -> dict[str, Any] | None:
        """Search for a paper by title and return the best match."""
        data = self._get_json(
            f"{S2_BASE}/paper/search",
            params={"query": title, "fields": PAPER_FIELDS, "limit": 1},
        )
        if not data:
            return None
        papers = data.get("data", [])
        return papers[0] if papers else None

    def fetch_references(self, paper_id: str) -> list[dict[str, Any]]:
        """Fetch all references for a paper, paginating if needed."""
        all_refs: list[dict[str, Any]] = []
        offset = 0
        limit = min(self._max_refs, 1000)

        while True:
            data = self._get_json(
                f"{S2_BASE}/paper/{paper_id}/references",
                params={
                    "fields": REFERENCE_FIELDS,
                    "limit": limit,
                    "offset": offset,
                },
            )
            if not data:
                break

            batch = data.get("data", [])
            if not batch:
                break

            for row in batch:
                cited = row.get("citedPaper")
                if isinstance(cited, dict) and cited.get("paperId"):
                    all_refs.append(cited)

            # Check if there are more pages
            total = data.get("total", 0)
            offset += len(batch)
            if offset >= total or offset >= self._max_refs:
                break

        return all_refs

    def crawl(
        self,
        seed_id: str,
        *,
        max_depth: int = -1,
        max_papers: int = -1,
    ) -> tuple[dict[str, PaperNode], list[Edge]]:
        """BFS crawl starting from seed_id.

        Args:
            seed_id: Semantic Scholar paper ID (or DOI:/ARXIV: prefixed).
            max_depth: Maximum BFS depth. -1 means unlimited.
            max_papers: Maximum papers to discover. -1 means unlimited.

        Returns:
            (papers dict, edges list)
        """
        papers: dict[str, PaperNode] = {}
        edges: list[Edge] = []
        queue: deque[tuple[str, int]] = deque()  # (paper_id, depth)

        # Resolve the seed paper
        logger.info("Resolving seed paper: %s", seed_id)
        if seed_id.startswith("TITLE:"):
            seed_data = self.search_paper(seed_id[6:])
        else:
            seed_data = self.resolve_paper(seed_id)
        if not seed_data or not seed_data.get("paperId"):
            logger.error("Could not resolve seed paper: %s", seed_id)
            return papers, edges

        seed_paper_id = seed_data["paperId"]
        seed_node = _to_node(seed_data, depth=0)
        papers[seed_paper_id] = seed_node
        queue.append((seed_paper_id, 0))

        logger.info(
            "Seed: %s — \"%s\" (%d references reported)",
            seed_paper_id,
            seed_node.title,
            seed_node.reference_count or 0,
        )

        try:
            while queue:
                paper_id, depth = queue.popleft()
                next_depth = depth + 1

                if max_depth >= 0 and next_depth > max_depth:
                    continue

                logger.info(
                    "[depth=%d] Fetching references for %s (%d papers found, %d in queue)",
                    depth, paper_id, len(papers), len(queue),
                )

                refs = self.fetch_references(paper_id)
                new_count = 0

                for ref_data in refs:
                    ref_id = ref_data.get("paperId")
                    if not ref_id:
                        continue

                    # Record edge
                    edges.append(Edge(source=paper_id, target=ref_id))

                    # Skip if already visited
                    if ref_id in papers:
                        continue

                    # Check paper cap
                    if max_papers >= 0 and len(papers) >= max_papers:
                        logger.info("Reached max papers limit (%d)", max_papers)
                        # Drain the queue — we still record edges but stop expanding
                        queue.clear()
                        break

                    # Add new paper
                    node = _to_node(ref_data, depth=next_depth)
                    papers[ref_id] = node
                    new_count += 1

                    # Only expand papers that have references
                    ref_count = ref_data.get("referenceCount") or 0
                    if ref_count > 0:
                        queue.append((ref_id, next_depth))

                logger.info(
                    "  → %d references fetched, %d new papers (total: %d)",
                    len(refs), new_count, len(papers),
                )
        except KeyboardInterrupt:
            logger.warning("Crawl interrupted by user. Saving progress so far...")

        logger.info(
            "Crawl complete: %d papers, %d edges, %d API requests",
            len(papers), len(edges), self._request_count,
        )
        return papers, edges


def _to_node(data: dict[str, Any], depth: int) -> PaperNode:
    authors = []
    for a in (data.get("authors") or []):
        if isinstance(a, dict) and a.get("name"):
            authors.append(a["name"])

    external_ids: dict[str, str] = {}
    raw_ids = data.get("externalIds") or {}
    if isinstance(raw_ids, dict):
        for key in ("DOI", "ArXiv", "CorpusId"):
            if raw_ids.get(key):
                external_ids[key.lower()] = str(raw_ids[key])

    return PaperNode(
        paper_id=data.get("paperId") or "",
        title=data.get("title") or "",
        authors=authors,
        year=data.get("year"),
        venue=data.get("venue") or None,
        citation_count=data.get("citationCount"),
        reference_count=data.get("referenceCount"),
        external_ids=external_ids,
        url=data.get("url"),
        depth=depth,
    )


import signal

def _handle_sigterm(signum, frame):
    raise KeyboardInterrupt()

def main() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    parser = argparse.ArgumentParser(
        description="Recursively crawl citation references via Semantic Scholar.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "paper_id",
        nargs="?",
        help="Semantic Scholar paper ID (hex hash). Omit if using --doi or --arxiv.",
    )
    parser.add_argument("--doi", help="Resolve the seed paper by DOI.")
    parser.add_argument("--arxiv", help="Resolve the seed paper by ArXiv ID.")
    parser.add_argument("--title", help="Resolve the seed paper by title search.")
    parser.add_argument(
        "--max-depth", type=int, default=-1,
        help="Maximum BFS depth (-1 = unlimited). Default: unlimited.",
    )
    parser.add_argument(
        "--max-papers", type=int, default=-1,
        help="Maximum papers to discover (-1 = unlimited). Default: unlimited.",
    )
    parser.add_argument(
        "--max-refs-per-paper", type=int, default=500,
        help="Max references to fetch per paper. Default: 500.",
    )
    parser.add_argument(
        "--output", "-o", default="citations_crawl.json",
        help="Output JSON file. Default: citations_crawl.json",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        help="Semantic Scholar API key. Default: $SEMANTIC_SCHOLAR_API_KEY env var.",
    )
    parser.add_argument(
        "--rate-limit", type=float, default=1.05,
        help="Minimum seconds between API requests. Default: 1.05",
    )
    args = parser.parse_args()

    # Resolve the seed identifier
    if args.doi:
        seed_id = f"DOI:{args.doi}"
    elif args.arxiv:
        seed_id = f"ARXIV:{args.arxiv}"
    elif args.title:
        seed_id = f"TITLE:{args.title}"
    elif args.paper_id:
        seed_id = args.paper_id
    else:
        parser.error("Provide a paper_id, --doi, --arxiv, or --title.")
        return

    crawler = SemanticScholarCrawler(
        api_key=args.api_key,
        min_interval=args.rate_limit,
        max_refs_per_paper=args.max_refs_per_paper,
    )

    start = time.monotonic()
    papers, edges = crawler.crawl(
        seed_id,
        max_depth=args.max_depth,
        max_papers=args.max_papers,
    )
    elapsed = time.monotonic() - start

    # Build output
    output = {
        "metadata": {
            "seed_id": seed_id,
            "crawled_at": datetime.now(tz=timezone.utc).isoformat(),
            "max_depth": args.max_depth,
            "max_papers": args.max_papers,
            "elapsed_seconds": round(elapsed, 1),
        },
        "stats": {
            "total_papers": len(papers),
            "total_edges": len(edges),
            "max_depth_reached": max((p.depth for p in papers.values()), default=0),
            "papers_by_depth": _count_by_depth(papers),
        },
        "papers": {pid: asdict(node) for pid, node in papers.items()},
        "edges": [asdict(e) for e in edges],
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    logger.info("Output written to %s", out_path)

    # Summary
    print(f"\n{'='*60}")
    print(f"  Crawl Summary")
    print(f"{'='*60}")
    print(f"  Seed:           {seed_id}")
    if papers:
        seed_node = next(iter(papers.values()))
        print(f"  Title:          {seed_node.title}")
    print(f"  Papers found:   {len(papers):,}")
    print(f"  Citation edges: {len(edges):,}")
    print(f"  Max depth:      {output['stats']['max_depth_reached']}")
    print(f"  Elapsed:        {elapsed:.1f}s")
    print(f"  Output:         {out_path}")
    print(f"{'='*60}")

    # Depth breakdown
    depth_counts = output["stats"]["papers_by_depth"]
    if depth_counts:
        print(f"\n  Papers by depth:")
        for depth_str in sorted(depth_counts, key=int):
            count = depth_counts[depth_str]
            bar = "█" * min(count, 60)
            print(f"    depth {depth_str:>2}: {count:>6,}  {bar}")
        print()


def _count_by_depth(papers: dict[str, PaperNode]) -> dict[str, int]:
    counts: dict[int, int] = {}
    for p in papers.values():
        counts[p.depth] = counts.get(p.depth, 0) + 1
    return {str(k): v for k, v in sorted(counts.items())}


if __name__ == "__main__":
    main()
