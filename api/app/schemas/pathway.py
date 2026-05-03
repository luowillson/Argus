from pydantic import BaseModel

from app.schemas.paper import PaperOut


class PathwayItem(BaseModel):
    position: int
    stage: str
    why_this_paper: str
    read_focus: str
    match_quality: str
    search_query: str | None
    anchor_concepts: list[str]
    paper: PaperOut | None


class LearningPathwayOut(BaseModel):
    id: str
    title: str
    rationale: str
    status: str
    enrichment_notes: dict[str, object]
    seed_paper_id: str | None
    query_text: str | None
    items: list[PathwayItem]


class TopicPathwayRequest(BaseModel):
    topic: str
    limit: int = 8


class LocalExploreCandidate(BaseModel):
    paper_id: str
    title: str
    stage: str
    year: int | None = None
    veros_score: float | None = None
    pagerank: float | None = None
    tldr: str | None = None
    anchor_concepts: list[str] = []


class LocalExploreOrderRequest(BaseModel):
    topic: str
    candidates: list[LocalExploreCandidate]


class LocalExploreOrderedItem(BaseModel):
    paper_id: str
    learning_step: int
    why_now: str


class LocalExploreOrderResponse(BaseModel):
    rationale: str
    items: list[LocalExploreOrderedItem]
    model: str | None = None
