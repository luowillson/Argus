from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.paper import ConsensusStrength, Verdict


CitationGraphStatus = Literal["not_enriched", "enriched", "failed"]
CitationDirection = Literal["references"]


class CitationPaper(BaseModel):
    id: str
    title: str
    authors: str
    venue: str | None
    year: int | None
    citations: int | None
    references_count: int | None
    openreview_url: str | None
    provider_url: str | None

    score: float | None
    grade: str
    verdict: Verdict
    novelty: int | None
    technical: int | None
    clarity: int | None
    impact: int | None
    consensus_strength: ConsensusStrength
    reviewer_count: int
    graph_only: bool


class CitationGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: Literal["cites"]
    weight: float


class CitationGraph(BaseModel):
    paper_id: str
    direction: CitationDirection
    status: CitationGraphStatus
    generated_at: datetime
    nodes: list[CitationPaper]
    edges: list[CitationGraphEdge]
