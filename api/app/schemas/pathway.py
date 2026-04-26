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
