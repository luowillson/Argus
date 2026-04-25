"""initial schema: extensions + 6 tables

Revision ID: 0001
Revises:
Create Date: 2026-04-25
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        CREATE TABLE papers (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            authors         TEXT[] NOT NULL DEFAULT '{}',
            venue           TEXT,
            year            INT,
            citations       INT,
            abstract        TEXT,
            openreview_url  TEXT NOT NULL,
            acceptance      TEXT,
            ingested_at     TIMESTAMPTZ,
            analyzed_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX papers_title_trgm ON papers USING gin (title gin_trgm_ops)"
    )

    op.execute(
        """
        CREATE TABLE reviews (
            id              TEXT PRIMARY KEY,
            paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            invitation      TEXT,
            signatures      TEXT[] NOT NULL DEFAULT '{}',
            rating          NUMERIC(3,1),
            confidence      NUMERIC(3,1),
            recommendation  TEXT,
            content         JSONB NOT NULL,
            created_at      TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX reviews_paper_id_idx ON reviews(paper_id)")

    op.execute(
        """
        CREATE TABLE ai_insights (
            paper_id        TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
            tldr            TEXT NOT NULL,
            deep            TEXT[] NOT NULL,
            skim            TEXT[] NOT NULL,
            reviewer_voices JSONB NOT NULL,
            novelty         INT NOT NULL,
            technical       INT NOT NULL,
            clarity         INT NOT NULL,
            impact          INT NOT NULL,
            consensus       TEXT NOT NULL,
            model           TEXT NOT NULL,
            prompt_version  INT NOT NULL DEFAULT 1,
            generated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE veros_scores (
            paper_id        TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
            score           NUMERIC(3,1) NOT NULL,
            grade           TEXT NOT NULL,
            verdict         TEXT NOT NULL,
            breakdown       JSONB NOT NULL,
            computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE saved_papers (
            user_id         TEXT NOT NULL,
            paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            saved_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, paper_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE paper_embeddings (
            paper_id        TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
            embedding       vector(384) NOT NULL,
            source          TEXT NOT NULL,
            model           TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX paper_embeddings_ivf
            ON paper_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paper_embeddings")
    op.execute("DROP TABLE IF EXISTS saved_papers")
    op.execute("DROP TABLE IF EXISTS veros_scores")
    op.execute("DROP TABLE IF EXISTS ai_insights")
    op.execute("DROP TABLE IF EXISTS reviews")
    op.execute("DROP TABLE IF EXISTS papers")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
