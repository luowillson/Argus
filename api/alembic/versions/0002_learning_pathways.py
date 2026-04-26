"""learning pathway tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE paper_concepts (
            paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            concept         TEXT NOT NULL,
            weight          NUMERIC(4,3) NOT NULL,
            source          TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (paper_id, concept)
        )
        """
    )
    op.execute("CREATE INDEX paper_concepts_concept_idx ON paper_concepts(concept)")

    op.execute(
        """
        CREATE TABLE paper_edges (
            src_paper_id    TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            dst_paper_id    TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            edge_type       TEXT NOT NULL,
            weight          NUMERIC(4,3) NOT NULL,
            edge_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (src_paper_id, dst_paper_id, edge_type)
        )
        """
    )
    op.execute("CREATE INDEX paper_edges_dst_idx ON paper_edges(dst_paper_id)")

    op.execute(
        """
        CREATE TABLE learning_pathways (
            id              TEXT PRIMARY KEY,
            user_id         TEXT,
            seed_paper_id   TEXT REFERENCES papers(id) ON DELETE SET NULL,
            query_text      TEXT,
            title           TEXT NOT NULL,
            rationale       TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'ready',
            model           TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            generated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX learning_pathways_seed_idx ON learning_pathways(seed_paper_id)")

    op.execute(
        """
        CREATE TABLE learning_pathway_items (
            pathway_id       TEXT NOT NULL REFERENCES learning_pathways(id) ON DELETE CASCADE,
            position         INT NOT NULL,
            paper_id         TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            stage            TEXT NOT NULL,
            why_this_paper   TEXT NOT NULL,
            read_focus       TEXT NOT NULL,
            score            NUMERIC(4,3),
            PRIMARY KEY (pathway_id, position)
        )
        """
    )
    op.execute("CREATE INDEX learning_pathway_items_paper_idx ON learning_pathway_items(paper_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS learning_pathway_items")
    op.execute("DROP TABLE IF EXISTS learning_pathways")
    op.execute("DROP TABLE IF EXISTS paper_edges")
    op.execute("DROP TABLE IF EXISTS paper_concepts")
