from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Paper(SQLModel, table=True):
    __tablename__ = "papers"

    id: str = Field(primary_key=True)
    title: str
    authors: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=False))
    venue: str | None = None
    year: int | None = None
    citations: int | None = None
    abstract: str | None = None
    openreview_url: str
    acceptance: str | None = None
    ingested_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    analyzed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    __table_args__ = (Index("reviews_paper_id_idx", "paper_id"),)

    id: str = Field(primary_key=True)
    paper_id: str = Field(sa_column=Column(String, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False))
    invitation: str | None = None
    signatures: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=False))
    rating: float | None = Field(default=None, sa_column=Column(Numeric(3, 1)))
    confidence: float | None = Field(default=None, sa_column=Column(Numeric(3, 1)))
    recommendation: str | None = None
    content: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    created_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class AIInsight(SQLModel, table=True):
    __tablename__ = "ai_insights"

    paper_id: str = Field(
        sa_column=Column(
            String, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    tldr: str
    deep: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=False))
    skim: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String), nullable=False))
    reviewer_voices: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    novelty: int
    technical: int
    clarity: int
    impact: int
    consensus: str
    model: str
    prompt_version: int = 1
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class VerosScore(SQLModel, table=True):
    __tablename__ = "veros_scores"

    paper_id: str = Field(
        sa_column=Column(
            String, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    score: float = Field(sa_column=Column(Numeric(3, 1), nullable=False))
    grade: str
    verdict: str
    breakdown: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class SavedPaper(SQLModel, table=True):
    __tablename__ = "saved_papers"

    user_id: str = Field(primary_key=True)
    paper_id: str = Field(
        sa_column=Column(
            String, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    saved_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class PaperEmbedding(SQLModel, table=True):
    __tablename__ = "paper_embeddings"

    paper_id: str = Field(
        sa_column=Column(
            String, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True
        ),
    )
    embedding: list[float] = Field(sa_column=Column(Vector(384), nullable=False))
    source: str
    model: str


class OpenReviewIngestFailure(SQLModel, table=True):
    __tablename__ = "openreview_ingest_failures"

    paper_id: str = Field(primary_key=True)
    attempts: int
    error: str = Field(sa_column=Column(Text, nullable=False))
    failed_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
