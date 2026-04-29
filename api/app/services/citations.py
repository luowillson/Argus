from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import AIInsight, Paper, PaperEdge, PaperIdentifier, VerosScore
from app.schemas.citation import CitationGraph, CitationGraphEdge, CitationPaper
from app.schemas.paper import ConsensusStrength
from app.services.citation_providers import (
    CitationFetchResult,
    CitationProviderError,
    CrossrefProvider,
    ExternalPaper,
    OpenAlexProvider,
    SemanticScholarProvider,
    make_default_providers,
    normalize_arxiv,
    normalize_doi,
)
from app.services.dimensions import standardized_dimensions

logger = logging.getLogger(__name__)

SUPPORTED_IDENTIFIER_NAMESPACES = {
    "openreview",
    "semantic_scholar",
    "openalex",
    "doi",
    "arxiv",
    "corpus_id",
    "pmid",
    "pmcid",
}

CitationDirection = Literal["references"]


def citation_graph_status(paper: Paper) -> Literal["not_enriched", "enriched", "failed"]:
    metadata = dict(paper.citation_metadata or {})
    if metadata.get("error"):
        return "failed"
    if paper.citation_enriched_at is not None:
        return "enriched"
    return "not_enriched"


def upsert_paper_identifiers(
    db: Session,
    paper_id: str,
    identifiers: dict[str, str | None],
    *,
    source: str,
    confidence: float = 1.0,
) -> None:
    for namespace, raw_value in identifiers.items():
        if namespace not in SUPPORTED_IDENTIFIER_NAMESPACES or raw_value is None:
            continue
        value = _normalize_identifier(namespace, raw_value)
        if not value:
            continue
        stmt = pg_insert(PaperIdentifier).values(
            paper_id=paper_id,
            namespace=namespace,
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            source=source,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                PaperIdentifier.__table__.c.namespace,
                PaperIdentifier.__table__.c.value,
            ]
        )
        db.exec(stmt)


def enrich_paper_citations(
    db: Session,
    paper_id: str,
    *,
    providers: tuple[SemanticScholarProvider, OpenAlexProvider, CrossrefProvider] | None = None,
    max_references: int | None = None,
) -> dict[str, object]:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise ValueError(f"paper {paper_id!r} not found")

    settings = get_settings()
    max_refs = max_references or settings.citation_max_references
    semantic, openalex, crossref = providers or make_default_providers()

    seed_ids = _identifiers_for_paper(db, paper_id)
    doi = normalize_doi(seed_ids.get("doi") or _extract_identifier_from_metadata(paper, "doi"))
    arxiv_id = normalize_arxiv(seed_ids.get("arxiv") or _extract_identifier_from_metadata(paper, "arxiv"))

    result: CitationFetchResult | None = None
    provider_used = ""
    provider_errors: list[str] = []
    provider_order: tuple[tuple[str, SemanticScholarProvider | OpenAlexProvider], ...]
    if settings.semantic_scholar_api_key:
        provider_order = (("semantic_scholar", semantic), ("openalex", openalex))
    elif doi or arxiv_id:
        provider_order = (("openalex", openalex), ("semantic_scholar", semantic))
    else:
        # Anonymous Semantic Scholar title search shares a public rate-limit
        # pool. Until Veros has a dedicated S2 key, do title-only resolution via
        # OpenAlex and reserve anonymous S2 calls for exact DOI/arXiv lookups.
        provider_order = (("openalex", openalex),)

    for provider_name, provider in provider_order:
        try:
            result = provider.fetch(
                title=paper.title,
                authors=list(paper.authors or []),
                year=paper.year,
                doi=doi,
                arxiv_id=arxiv_id,
                max_references=max_refs,
            )
        except CitationProviderError as exc:
            provider_errors.append(f"{provider_name}: {exc}")
            result = None
        if result is None and not (
            provider_errors and provider_errors[-1].startswith(f"{provider_name}:")
        ):
            provider_errors.append(f"{provider_name}: no confident match")
            continue
        if result is not None:
            provider_used = provider_name
            break

    if result is None and doi:
        fallback = crossref.lookup_doi(doi)
        if fallback is not None:
            result = CitationFetchResult(seed=fallback, references=[])
            provider_used = "crossref"
        else:
            provider_errors.append("crossref: no DOI match")

    if result is None:
        metadata = dict(paper.citation_metadata or {})
        metadata.update(
            {
                "error": "No citation provider matched this paper",
                "provider_errors": provider_errors,
                "last_attempted_at": datetime.now(tz=UTC).isoformat(),
            }
        )
        paper.citation_metadata = metadata
        db.add(paper)
        db.commit()
        return {
            "paper_id": paper_id,
            "status": "not_found",
            "reference_count": 0,
            "provider": None,
        }

    now = datetime.now(tz=UTC)
    _update_paper_from_external(
        paper,
        result.seed,
        provider=provider_used,
        enriched_at=now,
        preserve_title=True,
    )
    db.add(paper)
    upsert_paper_identifiers(db, paper_id, result.seed.external_ids, source=provider_used)
    upsert_paper_identifiers(db, paper_id, {"openreview": paper_id}, source="openreview")

    reference_ids: list[str] = []
    for reference in result.references[:max_refs]:
        ref_id = _upsert_external_paper(db, reference)
        reference_ids.append(ref_id)
        stmt = pg_insert(PaperEdge).values(
            src_paper_id=paper_id,
            dst_paper_id=ref_id,
            edge_type="cites",
            weight=1.0,
            edge_metadata={
                "provider": provider_used,
                "source_paper_provider": result.seed.provider,
                "target_paper_provider": reference.provider,
                "fetched_at": now.isoformat(),
                "external_ids": reference.external_ids,
            },
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                PaperEdge.__table__.c.src_paper_id,
                PaperEdge.__table__.c.dst_paper_id,
                PaperEdge.__table__.c.edge_type,
            ],
            set_={
                "weight": stmt.excluded.weight,
                "edge_metadata": stmt.excluded.edge_metadata,
                "created_at": stmt.excluded.created_at,
            },
        )
        db.exec(stmt)

    paper.references_count = result.seed.references_count or len(reference_ids) or paper.references_count
    metadata = dict(paper.citation_metadata or {})
    metadata.update(
        {
            "provider": provider_used,
            "reference_nodes_stored": len(reference_ids),
            "last_enriched_at": now.isoformat(),
        }
    )
    metadata.pop("error", None)
    paper.citation_metadata = metadata
    paper.citation_enriched_at = now
    db.add(paper)
    db.commit()

    return {
        "paper_id": paper_id,
        "status": "enriched",
        "reference_count": len(reference_ids),
        "provider": provider_used,
    }


def build_citation_graph(
    db: Session,
    paper_id: str,
    *,
    direction: CitationDirection = "references",
    limit: int = 60,
) -> CitationGraph:
    if direction != "references":
        raise ValueError("only references direction is supported")
    seed = db.get(Paper, paper_id)
    if seed is None:
        raise ValueError(f"paper {paper_id!r} not found")

    rows = db.exec(
        select(PaperEdge)
        .where(PaperEdge.src_paper_id == paper_id, PaperEdge.edge_type == "cites")
        .order_by(PaperEdge.created_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    node_ids = [paper_id] + [edge.dst_paper_id for edge in rows]
    papers = {
        p.id: p
        for p in db.exec(select(Paper).where(Paper.id.in_(node_ids))).all()
    }
    scores = {
        s.paper_id: s
        for s in db.exec(select(VerosScore).where(VerosScore.paper_id.in_(node_ids))).all()
    }
    insights = {
        i.paper_id: i
        for i in db.exec(select(AIInsight).where(AIInsight.paper_id.in_(node_ids))).all()
    }
    nodes = [
        _citation_paper(papers[pid], scores.get(pid), insights.get(pid))
        for pid in node_ids
        if pid in papers
    ]
    edges = [
        CitationGraphEdge(
            source=edge.src_paper_id,
            target=edge.dst_paper_id,
            edge_type=edge.edge_type,
            weight=float(edge.weight),
        )
        for edge in rows
    ]
    return CitationGraph(
        paper_id=paper_id,
        direction=direction,
        status=citation_graph_status(seed),
        generated_at=datetime.now(tz=UTC),
        nodes=nodes,
        edges=edges,
    )


def _upsert_external_paper(db: Session, external: ExternalPaper) -> str:
    existing_id = _find_existing_paper_id(db, external.external_ids)
    paper_id = existing_id or _local_external_paper_id(external)
    now = datetime.now(tz=UTC)
    stmt = pg_insert(Paper).values(
        id=paper_id,
        title=external.title or paper_id,
        authors=external.authors,
        venue=external.venue,
        year=external.year,
        citations=external.citations,
        references_count=external.references_count,
        abstract=external.abstract,
        openreview_url=None,
        acceptance=None,
        citation_metadata={
            "provider": external.provider,
            "provider_url": external.provider_url,
            "external_ids": external.external_ids,
            "graph_only": True,
            "last_seen_at": now.isoformat(),
        },
        citation_enriched_at=None,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Paper.__table__.c.id],
        set_={
            "citations": stmt.excluded.citations,
            "references_count": stmt.excluded.references_count,
            "citation_metadata": Paper.__table__.c.citation_metadata.op("||")(
                stmt.excluded.citation_metadata
            ),
        },
    )
    db.exec(stmt)
    upsert_paper_identifiers(db, paper_id, external.external_ids, source=external.provider)
    return paper_id


def _update_paper_from_external(
    paper: Paper,
    external: ExternalPaper,
    *,
    provider: str,
    enriched_at: datetime,
    preserve_title: bool,
) -> None:
    if not preserve_title and external.title:
        paper.title = external.title
    if not paper.authors and external.authors:
        paper.authors = external.authors
    if paper.venue is None and external.venue:
        paper.venue = external.venue
    if paper.year is None and external.year:
        paper.year = external.year
    if paper.abstract is None and external.abstract:
        paper.abstract = external.abstract
    paper.citations = external.citations if external.citations is not None else paper.citations
    paper.references_count = (
        external.references_count if external.references_count is not None else paper.references_count
    )
    metadata = dict(paper.citation_metadata or {})
    metadata.update(
        {
            "provider": provider,
            "provider_url": external.provider_url,
            "external_ids": external.external_ids,
            "last_seen_at": enriched_at.isoformat(),
        }
    )
    paper.citation_metadata = metadata


def _citation_paper(
    paper: Paper,
    score_row: VerosScore | None,
    insight: AIInsight | None,
) -> CitationPaper:
    breakdown = dict(score_row.breakdown) if score_row else {}
    cs_raw = breakdown.get("consensus_strength", "split")
    consensus_strength: ConsensusStrength = (
        cs_raw if cs_raw in {"strong", "moderate", "mixed", "split"} else "split"
    )  # type: ignore[assignment]
    dimensions = standardized_dimensions(score_row, insight)
    metadata = dict(paper.citation_metadata or {})
    return CitationPaper(
        id=paper.id,
        title=paper.title,
        authors=", ".join(paper.authors) if paper.authors else "Unknown",
        venue=paper.venue,
        year=paper.year,
        citations=paper.citations,
        references_count=paper.references_count,
        openreview_url=paper.openreview_url,
        provider_url=metadata.get("provider_url") if isinstance(metadata.get("provider_url"), str) else None,
        score=float(score_row.score) if score_row else None,
        grade=score_row.grade if score_row else "—",
        verdict=score_row.verdict if score_row else "Insufficient reviews",  # type: ignore[arg-type]
        novelty=dimensions["novelty"],
        technical=dimensions["technical"],
        clarity=dimensions["clarity"],
        impact=dimensions["impact"],
        consensus_strength=consensus_strength,
        reviewer_count=int(breakdown.get("n_reviews", 0)),
        graph_only=score_row is None,
    )


def _find_existing_paper_id(db: Session, identifiers: dict[str, str]) -> str | None:
    normalized = {
        namespace: _normalize_identifier(namespace, value)
        for namespace, value in identifiers.items()
        if namespace in SUPPORTED_IDENTIFIER_NAMESPACES
    }
    values = [(namespace, value) for namespace, value in normalized.items() if value]
    if not values:
        return None
    rows = db.exec(
        select(PaperIdentifier).where(
            PaperIdentifier.namespace.in_([namespace for namespace, _ in values]),
            PaperIdentifier.value.in_([value for _, value in values]),
        )
    ).all()
    lookup = set(values)
    for row in rows:
        if (row.namespace, row.value) in lookup:
            return row.paper_id
    return None


def _identifiers_for_paper(db: Session, paper_id: str) -> dict[str, str]:
    rows = db.exec(select(PaperIdentifier).where(PaperIdentifier.paper_id == paper_id)).all()
    return {row.namespace: row.value for row in rows}


def _extract_identifier_from_metadata(paper: Paper, namespace: str) -> str | None:
    metadata = dict(paper.citation_metadata or {})
    ids = metadata.get("external_ids")
    if isinstance(ids, dict) and isinstance(ids.get(namespace), str):
        return ids[namespace]
    return None


def _local_external_paper_id(external: ExternalPaper) -> str:
    ids = external.external_ids
    if ids.get("semantic_scholar"):
        return f"s2:{ids['semantic_scholar']}"
    if ids.get("openalex"):
        return f"oa:{ids['openalex']}"
    if ids.get("corpus_id"):
        return f"corpus:{ids['corpus_id']}"
    if ids.get("doi"):
        digest = hashlib.sha1(ids["doi"].encode("utf-8")).hexdigest()[:14]
        return f"doi:{digest}"
    basis = f"{external.title}|{external.year or ''}|{','.join(external.authors[:3])}"
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:14]
    return f"ext:{digest}"


def _normalize_identifier(namespace: str, value: str) -> str | None:
    if namespace == "doi":
        return normalize_doi(value)
    if namespace == "arxiv":
        return normalize_arxiv(value)
    if namespace == "openalex":
        return value.removeprefix("https://openalex.org/").strip() or None
    stripped = str(value).strip()
    return stripped or None
