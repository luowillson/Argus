from datetime import datetime

from pydantic import BaseModel

from app.schemas.paper import Verdict


class LandingGraphNode(BaseModel):
    id: str
    title: str
    venue: str | None
    score: float | None
    verdict: Verdict


class LandingGraphEdge(BaseModel):
    source: str
    target: str
    weight: float


class LandingGraph(BaseModel):
    generated_at: datetime
    topic_paper_id: str | None = None
    topic_title: str | None = None
    topic_venue: str | None = None
    nodes: list[LandingGraphNode]
    edges: list[LandingGraphEdge]
